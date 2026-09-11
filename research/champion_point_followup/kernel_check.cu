#include <cuda_runtime.h>
#include <math_constants.h>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <stdexcept>
#define CUDA_CHECK(x) do{auto e=(x);if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}while(0)
struct DeviceProblem {int ncam,npt;int *point_obs_offsets,*point_obs_list,*cam_idx;double* uv;};
struct DeviceState {double *R,*t,*X,*intr;};
#define INTR_F(p,s) ((s).intr)
#define INTR_K1(p,s) ((s).intr+(p).ncam)
#define INTR_K2(p,s) ((s).intr+2*(p).ncam)
#include "point_overlay.cuh"
template<class T> T* read(FILE* f,size_t n){T* h=new T[n];if(fread(h,sizeof(T),n,f)!=n)throw std::runtime_error("short read");T* d;CUDA_CHECK(cudaMalloc(&d,n*sizeof(T)));CUDA_CHECK(cudaMemcpy(d,h,n*sizeof(T),cudaMemcpyHostToDevice));delete[] h;return d;}
DeviceState state(FILE* f,int nc,int np){DeviceState s;s.R=read<double>(f,9*nc);s.t=read<double>(f,3*nc);s.X=read<double>(f,3*np);s.intr=read<double>(f,3*nc);return s;}
int main(int argc,char** argv){
  FILE* f=fopen(argv[1],"rb");int dims[3];if(fread(dims,4,3,f)!=3)return 2;
  DeviceProblem p;p.ncam=dims[0];p.npt=dims[1];int no=dims[2],n=9*p.ncam+3*p.npt;
  p.point_obs_offsets=read<int>(f,p.npt+1);p.point_obs_list=read<int>(f,no);p.cam_idx=read<int>(f,no);p.uv=read<double>(f,2*no);
  auto old=state(f,p.ncam,p.npt),full=state(f,p.ncam,p.npt);auto diag=read<double>(f,3*p.npt),step=read<double>(f,n);double tau;if(fread(&tau,8,1,f)!=1)return 3;fclose(f);
  PrismPointOverlay overlay;auto changed=overlay.Choose(p,old,full,diag,tau,step,atoi(argv[3]));
  double* result=new double[n];CUDA_CHECK(cudaMemcpy(result,step,8*n,cudaMemcpyDeviceToHost));f=fopen(argv[2],"wb");fwrite(result,8,n,f);fclose(f);
  printf("{\"changed\":%llu}\n",changed);
}
