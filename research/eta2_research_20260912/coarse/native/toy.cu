#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <vector>
#define CUDA_CHECK(call) do{auto status=(call);if(status!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(status));}while(0)
#define CUBLAS_CHECK(call) do{if((call)!=CUBLAS_STATUS_SUCCESS)throw std::runtime_error("cublas failure");}while(0)
using Scalar=double;
struct DeviceProblem {int *point_obs_offsets,*point_obs_list,*cam_idx;};
struct DeviceState {double *R,*t;};
#include "native_primitives.cuh"
#include "coarse.cuh"

template<class T>T* upload(const std::vector<T>& v){T* p;CUDA_CHECK(cudaMalloc(&p,sizeof(T)*v.size()));CUDA_CHECK(cudaMemcpy(p,v.data(),sizeof(T)*v.size(),cudaMemcpyHostToDevice));return p;}
template<class T>std::vector<T> download(const T* p,size_t n){std::vector<T> v(n);CUDA_CHECK(cudaMemcpy(v.data(),p,sizeof(T)*n,cudaMemcpyDeviceToHost));return v;}
__global__ void scale(int n,const double* E,const double* x,double* y){int a=blockIdx.x*blockDim.x+threadIdx.x;if(a<n)y[a]=E[a]*x[a];}

int main(){
  const int nc=12,np=20,no=127,n=9*nc;const double lambda=1e-4;
  setenv("OCA_COARSE_ORACLE","1",1);
  cublasHandle_t blas;CUBLAS_CHECK(cublasCreate(&blas));
  std::vector<int> ci(no),pi(no),coff(nc+1,0),poff(np+1,0);
  for(int o=0;o<no;++o){ci[o]=(7*o+o/19)%nc;pi[o]=o%19;++coff[ci[o]+1];++poff[pi[o]+1];}
  for(int i=0;i<nc;++i)coff[i+1]+=coff[i];for(int j=0;j<np;++j)poff[j+1]+=poff[j];
  auto cc=coff,pp=poff;std::vector<int> plist(no),slots(no),scam(no),spt(no);
  for(int o=0;o<no;++o){int k=cc[ci[o]]++;slots[o]=k;scam[k]=ci[o];spt[k]=pi[o];plist[pp[pi[o]]++]=o;}
  std::vector<double> hR(9*nc,0),ht(3*nc),hE(n),hH(81*nc,0),hRf(6*np);
  for(int c=0;c<nc;++c){for(int i=0;i<3;++i){hR[9*c+4*i]=1;ht[3*c+i]=-std::sin((c+1.)*(i+1));}
    for(int i=0;i<9;++i){hE[9*c+i]=.7+.1*std::cos(c+i);hH[81*c+10*i]=10+.1*i;}}
  for(int j=0;j<np;++j){hRf[6*j]=2+.01*j;hRf[6*j+1]=.04;hRf[6*j+2]=-.02;hRf[6*j+3]=2.3;hRf[6*j+4]=.03;hRf[6*j+5]=2.7;}
  std::vector<float> hW(27*no);Eigen::MatrixXd W=Eigen::MatrixXd::Zero(n,3*np);
  for(int o=0;o<no;++o)for(int i=0;i<9;++i)for(int j=0;j<3;++j){float v=i==8?0:(float)(.07*std::sin((o+1.)*(i+1)*(j+1)));hW[(3*i+j)*no+slots[o]]=v;W(9*ci[o]+i,3*pi[o]+j)+=v;}
  DeviceProblem p{upload(poff),upload(plist),upload(ci)};DeviceState state{upload(hR),upload(ht)};
  double *E=upload(hE),*H=upload(hH),*Rf=upload(hRf);float* fragments=upload(hW);
  int *dslots=upload(slots),*dscam=upload(scam),*dspt=upload(spt),*dcoff=upload(coff);
  double *physical,*acc,*point;CUDA_CHECK(cudaMalloc(&physical,8*n));CUDA_CHECK(cudaMalloc(&acc,24*np));CUDA_CHECK(cudaMalloc(&point,24*np));
  auto product=[&](const double* x,double* y){
    scale<<<(n+255)/256,256>>>(n,E,x,physical);CUDA_CHECK(cudaMemset(acc,0,24*np));
    MFPass1<9,float><<<(no+255)/256,256>>>(fragments,dscam,dspt,physical,no,acc);
    MFVinvApply<<<(np+255)/256,256>>>(Rf,acc,np,point);
    MFPass2<9,float><<<nc,256>>>(fragments,dspt,dcoff,point,H,physical,no,y);
    scale<<<(n+255)/256,256>>>(n,E,y,y);
  };
  double coarse_error=0,apply_error=0,symmetry_error=0,linearity_error=0,energy=0;
  int final_rank=0;bool failed_fallback=false;
  {
    prism_coarse::Native native(nc,np,no);
    native.Prepare(p,state,E,H,fragments,dslots,Rf,lambda,8,0,8,1e-4,blas,product);
    if(!native.usable)throw std::runtime_error("toy coarse did not factor/pass native oracle");
    int rank=native.geometry.rank;final_rank=rank;
    Eigen::MatrixXd Z=Eigen::MatrixXd::Zero(n,rank),V=Eigen::MatrixXd::Zero(3*np,3*np),U=Eigen::MatrixXd::Zero(n,n);
    for(int c=0;c<nc;++c){int k=native.geometry.label[c];for(int i=0;i<9;++i){U(9*c+i,9*c+i)=hH[81*c+10*i];for(int a=0;a<native.geometry.local_rank[k];++a)Z(9*c+i,native.geometry.offset[k]+a)=native.geometry.Z[(9*c+i)*7+a];}}
    for(int j=0;j<np;++j){Eigen::Matrix3d r=Eigen::Matrix3d::Zero();r(0,0)=hRf[6*j];r(0,1)=hRf[6*j+1];r(0,2)=hRf[6*j+2];r(1,1)=hRf[6*j+3];r(1,2)=hRf[6*j+4];r(2,2)=hRf[6*j+5];V.block<3,3>(3*j,3*j)=r.transpose()*r;}
    Eigen::VectorXd e=Eigen::Map<Eigen::VectorXd>(hE.data(),n);
    Eigen::MatrixXd A=e.asDiagonal()*(U-W*V.llt().solve(W.transpose()))*e.asDiagonal()+lambda*Eigen::MatrixXd::Identity(n,n);
    Eigen::MatrixXd Ac=Z.transpose()*A*Z;coarse_error=(Ac-native.matrix).norm()/Ac.norm();
    if(coarse_error>1e-12)throw std::runtime_error("toy dense Ac mismatch");
    Eigen::MatrixXd BJ=e.asDiagonal()*U*e.asDiagonal()+lambda*Eigen::MatrixXd::Identity(n,n);
    auto apply=[&](const Eigen::VectorXd& r){
      Eigen::VectorXd z=BJ.llt().solve(r);std::vector<double> hr(r.data(),r.data()+n),hz(z.data(),z.data()+n);
      double* dr=upload(hr);double* dz=upload(hz);native.Apply(dr,dz);auto got=download(dz,n);cudaFree(dr);cudaFree(dz);
      Eigen::VectorXd result=Eigen::Map<Eigen::VectorXd>(got.data(),n);
      Eigen::VectorXd expected=z+Z*Ac.llt().solve(Z.transpose()*r);
      apply_error=std::max(apply_error,(result-expected).norm()/expected.norm());return result;
    };
    Eigen::VectorXd a(n),b(n);for(int i=0;i<n;++i){a[i]=std::sin(i+.3);b[i]=std::cos(2*i+.4);}
    Eigen::VectorXd aa=apply(a),bb=apply(b),ab=apply(a+b);
    symmetry_error=std::abs(a.dot(bb)-b.dot(aa));linearity_error=(ab-aa-bb).norm();energy=a.dot(aa);
    if(apply_error>1e-12||symmetry_error>1e-12||linearity_error>1e-12||!(energy>0))throw std::runtime_error("toy additive map failed");
    for(int i=0;i<nc;++i)for(int j=0;j<9;++j)hH[81*i+10*j]=-10;
    CUDA_CHECK(cudaMemcpy(H,hH.data(),8*hH.size(),cudaMemcpyHostToDevice));
    native.Prepare(p,state,E,H,fragments,dslots,Rf,lambda,8,1,8,1e-4,blas,product);
    failed_fallback=!native.usable&&native.fallbacks==1;
    std::vector<double> ha(a.data(),a.data()+n);double* dr=upload(ha);double* dz=upload(ha);native.Apply(dr,dz);auto after=download(dz,n);
    failed_fallback=failed_fallback&&after==ha;cudaFree(dr);cudaFree(dz);
    if(!failed_fallback)throw std::runtime_error("toy whole-attempt fallback failed");
  }
  for(double* q:{state.R,state.t,E,H,Rf,physical,acc,point})CUDA_CHECK(cudaFree(q));CUDA_CHECK(cudaFree(fragments));
  for(int* q:{p.point_obs_offsets,p.point_obs_list,p.cam_idx,dslots,dscam,dspt,dcoff})CUDA_CHECK(cudaFree(q));
  CUBLAS_CHECK(cublasDestroy(blas));
  std::printf("COARSE_TOY pass=1 rank=%d coarse_relative=%.17g apply_relative=%.17g symmetry=%.17g linearity=%.17g energy=%.17g fallback=%d\n",final_rank,coarse_error,apply_error,symmetry_error,linearity_error,energy,(int)failed_fallback);
}
