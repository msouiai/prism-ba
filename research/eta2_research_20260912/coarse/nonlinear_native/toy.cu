#include <cuda_runtime.h>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <vector>
#include <string>
#include <fstream>
#define CUDA_CHECK(call) do{auto status=(call);if(status!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(status));}while(0)
using Scalar=double;
struct DeviceProblem{int ncam,npt,nobs;int* cam_idx;int* pt_idx;double* uv;};
struct DeviceState{double* R;double* t;double* X;double* intr;int ncam_for_intr;};
__global__ void ToyCost(DeviceProblem p,DeviceState s,double* out){int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=p.nobs)return;int c=p.cam_idx[o],j=p.pt_idx[o];double Y[3];
 for(int a=0;a<3;++a)Y[a]=s.R[9*c+3*a]*s.X[3*j]+s.R[9*c+3*a+1]*s.X[3*j+1]+s.R[9*c+3*a+2]*s.X[3*j+2]+s.t[3*c+a];
 double u=-Y[0]/Y[2],v=-Y[1]/Y[2],scale=s.intr[c]*(1+s.intr[p.ncam+c]*(u*u+v*v));double a=scale*u-p.uv[2*o],b=scale*v-p.uv[2*o+1];atomicAdd(out,.5*(a*a+b*b));}
double ComputeCost(const DeviceProblem& p,const DeviceState& s){double* d;CUDA_CHECK(cudaMalloc(&d,8));CUDA_CHECK(cudaMemset(d,0,8));ToyCost<<<(p.nobs+127)/128,128>>>(p,s,d);double v;CUDA_CHECK(cudaMemcpy(&v,d,8,cudaMemcpyDeviceToHost));CUDA_CHECK(cudaFree(d));return v;}
void CopyState(const DeviceState& dst,const DeviceState& src,int nc,int np){CUDA_CHECK(cudaMemcpy(dst.R,src.R,72ul*nc,cudaMemcpyDeviceToDevice));CUDA_CHECK(cudaMemcpy(dst.t,src.t,24ul*nc,cudaMemcpyDeviceToDevice));CUDA_CHECK(cudaMemcpy(dst.X,src.X,24ul*np,cudaMemcpyDeviceToDevice));CUDA_CHECK(cudaMemcpy(dst.intr,src.intr,24ul*nc,cudaMemcpyDeviceToDevice));}
#include "passenger.cuh"
template<class T>std::vector<T> read(std::string path,size_t n){std::vector<T> v(n);std::ifstream f(path,std::ios::binary);f.read((char*)v.data(),n*sizeof(T));if(!f)throw std::runtime_error("toy input "+path);return v;}
template<class T>void write(std::string path,const T* v,size_t n){std::ofstream f(path,std::ios::binary);f.write((char*)v,n*sizeof(T));if(!f)throw std::runtime_error("toy output");}
int main(int argc,char** argv){if(argc!=2)return 2;std::string d=argv[1];int nc,np,no;std::ifstream(d+"/dims.txt")>>nc>>np>>no;
 prism_passenger::Native n(nc,np,no);auto upload=[&](std::string name,size_t count){return n.Upload(read<double>(d+"/"+name,count));};
 DeviceState s{upload("R.f64",9*nc),upload("t.f64",3*nc),upload("X.f64",3*np),upload("intr.f64",3*nc),nc};
 DeviceProblem p{nc,np,no,n.Upload(read<int>(d+"/ci.i32",no)),n.Upload(read<int>(d+"/pi.i32",no)),upload("uv.f64",2*no)};
 auto E=upload("E.f64",9*nc),Cdiag=upload("Cdiag.f64",3*np);n.Setup(p,s,E,Cdiag,.03,.03);auto hg=n.Assemble(p,s);
 auto& g=n.geometry;write(d+"/T.f64",g.T.data(),g.T.size());write(d+"/mu.f64",g.mu.data(),g.mu.size());write(d+"/labels.i32",g.cluster.label.data(),g.cluster.label.size());write(d+"/points.i32",g.point_label.data(),g.point_label.size());write(d+"/offset.i32",g.offset.data(),g.offset.size());write(d+"/ranks.i32",g.local_rank.data(),g.local_rank.size());
 Eigen::Matrix<double,Eigen::Dynamic,Eigen::Dynamic,Eigen::RowMajor> H=hg.first;write(d+"/H.f64",H.data(),H.size());write(d+"/g.f64",hg.second.data(),hg.second.size());
 std::vector<double> q(7*g.K);for(size_t i=0;i<q.size();++i)q[i]=.025*std::sin(.7*i+.3);write(d+"/q.f64",q.data(),q.size());n.Transform(s,q);
 auto R=n.Download(n.trial.R,9*nc),t=n.Download(n.trial.t,3*nc),X=n.Download(n.trial.X,3*np);write(d+"/newR.f64",R.data(),R.size());write(d+"/newt.f64",t.data(),t.size());write(d+"/newX.f64",X.data(),X.size());
 std::ofstream out(d+"/metadata.txt");out.precision(17);out<<"rank="<<g.rank<<"\ncost="<<ComputeCost(p,s)<<"\nnewcost="<<ComputeCost(p,n.trial)<<"\nwhitening="<<g.whitening_error<<"\n";
 printf("PASSENGER_TOY pass=1 rank=%d whitening=%.17g\n",g.rank,g.whitening_error);
}
