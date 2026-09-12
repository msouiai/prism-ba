#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <Eigen/Dense>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <stdexcept>
#include <vector>
#define CUDA_CHECK(call) do{auto status=(call);if(status!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(status));}while(0)
using Scalar=double;
static int GridSize(int n,int block=256){return (n+block-1)/block;}
struct DeviceProblem {int ncam,npt,nobs;int *cam_idx,*pt_idx,*obs2cslot,*point_obs_offsets,*point_obs_list,*mf_coff;double*uv;};
struct DeviceState {double *R,*t,*X,*f,*k1,*k2;};
#define INTR_F(p,s) (s).f
#define INTR_K1(p,s) (s).k1
#define INTR_K2(p,s) (s).k2
#include "bal_grad12_generated.cuh"
#include "native_primitives.cuh"
#include "frontload.cuh"
template<class T>T* upload(const std::vector<T>& v){T* p;CUDA_CHECK(cudaMalloc(&p,sizeof(T)*v.size()));CUDA_CHECK(cudaMemcpy(p,v.data(),sizeof(T)*v.size(),cudaMemcpyHostToDevice));return p;}
template<class T>std::vector<T> download(const T* p,size_t n){std::vector<T> v(n);CUDA_CHECK(cudaMemcpy(v.data(),p,sizeof(T)*n,cudaMemcpyDeviceToHost));return v;}

int main(){
  const int nc=3,np=5,no=15,n=27;const double lambda=.1;
  std::vector<double> hr(nc*9,0),ht(nc*3),hx(np*3),hf(nc),hk(nc),hzero(nc,0),huv(2*no),hE(n),cd(3*np,0),r2(nc,0),count(nc,0);
  std::vector<int> ci(no),pi(no),slot(no),poff(np+1),plist(no),coff(nc+1);
  for(int c=0;c<nc;++c){double a=.07*c;hr[9*c]=hr[9*c+4]=cos(a);hr[9*c+1]=-sin(a);hr[9*c+3]=sin(a);hr[9*c+8]=1;
    ht[3*c]=.8*(c-1);ht[3*c+1]=.1*c;ht[3*c+2]=.05*c;hf[c]=600+30*c;hk[c]=.01*(c-1);coff[c]=np*c;
    for(int k=0;k<9;++k)hE[9*c+k]=k==6?.01:(k==7?.002:.003);}
  coff[nc]=no;for(int j=0;j<np;++j){hx[3*j]=.3*sin(j+.2);hx[3*j+1]=.2*cos(j);hx[3*j+2]=-3-.3*j;poff[j]=3*j;}poff[np]=no;
  Eigen::MatrixXd Jc=Eigen::MatrixXd::Zero(2*no,n),Jp=Eigen::MatrixXd::Zero(2*no,3*np);Eigen::VectorXd residual(2*no);
  for(int o=0;o<no;++o){int j=o/3,c=o%3;ci[o]=c;pi[o]=j;slot[o]=c*np+j;plist[o]=o;
    Eigen::Map<Eigen::Matrix<double,3,3,Eigen::RowMajor>> R(hr.data()+9*c);Eigen::Map<Eigen::Vector3d> X(hx.data()+3*j),t(ht.data()+3*c);
    Eigen::Vector3d RX=R*X,Y=RX+t;double x=-Y[0]/Y[2],y=-Y[1]/Y[2],rr=x*x+y*y,f=hf[c],k=hk[c];
    Eigen::Matrix<double,2,3> dxy;dxy<<-1/Y[2],0,-x/Y[2],0,-1/Y[2],-y/Y[2];
    Eigen::Vector2d xy(x,y);Eigen::Matrix2d radial=f*((1+k*rr)*Eigen::Matrix2d::Identity()+2*k*xy*xy.transpose());
    Eigen::Matrix<double,2,3> dY=radial*dxy;Eigen::Matrix3d skew;skew<<0,-RX[2],RX[1],RX[2],0,-RX[0],-RX[1],RX[0],0;
    Jc.block<2,3>(2*o,9*c)=dY*(-skew);Jc.block<2,3>(2*o,9*c+3)=dY;
    Jc.block<2,1>(2*o,9*c+6)=(1+k*rr)*xy;Jc.block<2,1>(2*o,9*c+7)=f*rr*xy;
    Jp.block<2,3>(2*o,3*j)=dY*R;
    for(int q=0;q<3;++q)cd[3*j+q]+=Jp.block<2,1>(2*o,3*j+q).squaredNorm();
    residual[2*o]=.2*sin(o+.3);residual[2*o+1]=.15*cos(o+.2);
    huv[2*o]=f*(1+k*rr)*x-residual[2*o];huv[2*o+1]=f*(1+k*rr)*y-residual[2*o+1];r2[c]+=rr;count[c]+=1;
  }
  DeviceProblem p{nc,np,no,upload(ci),upload(pi),upload(slot),upload(poff),upload(plist),upload(coff),upload(huv)};
  DeviceState s{upload(hr),upload(ht),upload(hx),upload(hf),upload(hk),upload(hzero)};
  double *E=upload(hE),*Cdiag=upload(cd),*d_r2=upload(r2),*d_count=upload(count);
  cublasHandle_t blas;cublasCreate(&blas);FrontloadTotals totals;
  double row_error=0,rhs_error=0,product_error=0,point_error=0,normal_error=0,prediction_error=0;
  {
    FrontloadAttempt a(p,s,E,Cdiag,d_r2,d_count,lambda,0,0,totals);
    auto gotjc=download(a.Jc,18ul*no),gotjp=download(a.Jp,6ul*no),gotr=download(a.residual,2ul*no),gotrhs=download(a.rhs,n),gotq=download(a.Q,n);
    for(int o=0;o<no;++o)for(int q=0;q<2;++q){for(int k=0;k<9;++k)row_error=std::max(row_error,std::abs(gotjc[18*slot[o]+9*q+k]-Jc(2*o+q,9*ci[o]+k)));
      for(int k=0;k<3;++k)row_error=std::max(row_error,std::abs(gotjp[6*o+3*q+k]-Jp(2*o+q,3*pi[o]+k)));}
    Eigen::MatrixXd V=Jp.transpose()*Jp;for(int j=0;j<np;++j){double floor=lambda*(cd[3*j]+cd[3*j+1]+cd[3*j+2])/3;
      for(int k=0;k<3;++k)V(3*j+k,3*j+k)+=std::max(lambda*cd[3*j+k],1e-3*floor);}
    Eigen::VectorXd e=Eigen::Map<Eigen::VectorXd>(hE.data(),n),q=Eigen::Map<Eigen::VectorXd>(gotq.data(),n);
    Eigen::MatrixXd U=Jc.transpose()*Jc+q.asDiagonal().toDenseMatrix();Eigen::MatrixXd W=Jc.transpose()*Jp;
    Eigen::MatrixXd A=e.asDiagonal()*(U-W*V.llt().solve(W.transpose()))*e.asDiagonal()+lambda*Eigen::MatrixXd::Identity(n,n);
    Eigen::VectorXd b=e.asDiagonal()*(Jc.transpose()*residual-W*V.llt().solve(Jp.transpose()*residual));
    rhs_error=(Eigen::Map<Eigen::VectorXd>(gotrhs.data(),n)-b).norm()/b.norm();
    Eigen::VectorXd x=A.llt().solve(b);std::vector<double> xvec(x.data(),x.data()+n),physical(n);
    for(int k=0;k<n;++k)physical[k]=hE[k]*x[k];double*dx=upload(xvec),*xp=upload(physical),*out=upload(std::vector<double>(n,0)),*point=upload(std::vector<double>(3*np,0));
    a.ProductBase(dx,out);cublasDaxpy(blas,n,&lambda,dx,1,out,1);auto got=download(out,n);
    product_error=(Eigen::Map<Eigen::VectorXd>(got.data(),n)-A*x).norm()/(A*x).norm();
    a.CompletePhysical(xp,point);auto gotpoint=download(point,3*np);
    Eigen::VectorXd expected=V.llt().solve(Jp.transpose()*residual-W.transpose()*e.asDiagonal()*x);
    Eigen::VectorXd pt=Eigen::Map<Eigen::VectorXd>(gotpoint.data(),3*np);point_error=(pt-expected).norm()/expected.norm();
    Eigen::VectorXd fullx(n+3*np);fullx.head(n)=e.asDiagonal()*x;fullx.tail(3*np)=pt;
    Eigen::VectorXd fullgrad(n+3*np);fullgrad.head(n)=Jc.transpose()*residual;fullgrad.tail(3*np)=Jp.transpose()*residual;
    Eigen::MatrixXd H(n+3*np,n+3*np);H.topLeftCorner(n,n)=U;for(int k=0;k<n;++k)H(k,k)+=lambda/(hE[k]*hE[k]);H.topRightCorner(n,3*np)=W;H.bottomLeftCorner(3*np,n)=W.transpose();H.bottomRightCorner(3*np,3*np)=V;
    normal_error=(H*fullx-fullgrad).norm()/fullgrad.norm();
    Eigen::VectorXd jd=-Jc*(e.asDiagonal()*x)-Jp*pt;
    double pred=-residual.dot(jd)-.5*jd.squaredNorm();double model=.5*(residual+jd).squaredNorm();
    prediction_error=std::abs(pred-(.5*residual.squaredNorm()-model));
    long mv=0;a.EnsureFresh(blas,dx,b.norm(),mv);
    if(a.fresh_relative>1e-10||mv!=1||row_error>1e-10||rhs_error>1e-11||product_error>1e-11||point_error>1e-11||normal_error>1e-11||prediction_error>1e-12)
      throw std::runtime_error("frontload toy coherent row/operator/RHS/point/model check failed");
    for(double* v:{dx,xp,out,point})CUDA_CHECK(cudaFree(v));
  }
  for(double* v:{p.uv,s.R,s.t,s.X,s.f,s.k1,s.k2,E,Cdiag,d_r2,d_count})CUDA_CHECK(cudaFree(v));
  for(int* v:{p.cam_idx,p.pt_idx,p.obs2cslot,p.point_obs_offsets,p.point_obs_list,p.mf_coff})CUDA_CHECK(cudaFree(v));
  cublasDestroy(blas);totals.Print();
  std::printf("FRONTLOAD_TOY pass=1 row_max_abs=%.17g rhs_relative=%.17g product_relative=%.17g point_relative=%.17g normal_relative=%.17g prediction_abs=%.17g\n",row_error,rhs_error,product_error,point_error,normal_error,prediction_error);
}
