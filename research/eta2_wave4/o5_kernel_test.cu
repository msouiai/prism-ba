// Exercise the actual O5 prediction/rescue headers against independent Python
// finite differences. Minimal types match only fields consumed by these headers.
#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <stdexcept>
using Scalar=double;
#define CUDA_CHECK(x) do{auto e=(x);if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}while(0)
inline int GridSize(int n){return (n+255)/256;}
struct DeviceProblem{int nobs=1,ncam=1,npt=1;int *cam_idx,*pt_idx,*point_obs_offsets,*point_obs_list;double*uv;};
struct DeviceState{double *R,*t,*X,*intr;};
#define INTR_F(p,s) ((s).intr)
#define INTR_K1(p,s) ((s).intr+(p).ncam)
#define INTR_K2(p,s) ((s).intr+2*(p).ncam)
__host__ __device__ double OcaRho(int k,double a,double q){return k==2?a*log1p(q/a):q;}
__host__ __device__ double OcaRobustW(int k,double a,double q){return k==2?1/(1+q/a):1;}
#include "../eta2_champion/source/headers/bal_factored_grad.cuh"
#include "o5_headers/robust_stage.cuh"
#include "o5_headers/full_step_model.cuh"
#include "o5_headers/point_safeguard.cuh"
__global__ void TrackTest(DeviceProblem p,DeviceState s,double*out){
 if(threadIdx.x==0)*out=PrismTrackObservation(0,0,p.cam_idx,p.uv,s.R,s.t,s.X,INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s));
}
int main(int argc,char**argv){
 if(argc!=3)return 2;FILE*in=fopen(argv[1],"rb"),*out=fopen(argv[2],"wb");if(!in||!out)return 3;
 double*data;int*ids;CUDA_CHECK(cudaMalloc(&data,33*sizeof(double)));CUDA_CHECK(cudaMalloc(&ids,2*sizeof(int)));CUDA_CHECK(cudaMemset(ids,0,2*sizeof(int)));
 DeviceProblem p;p.cam_idx=ids;p.pt_idx=ids;p.uv=data+19;
 DeviceState s{data+1,data+10,data+13,data+16};double*result;CUDA_CHECK(cudaMalloc(&result,sizeof(double)));
 PrismFullModel model;double h[33];int count=0;
 while(fread(h,sizeof(double),33,in)==33){
   CUDA_CHECK(cudaMemcpy(data,h,sizeof(h),cudaMemcpyHostToDevice));
   for(int rk:{0,2}){W5SetRobust(rk,h[0]);auto r=model.Evaluate(p,s,data+21,0);
     TrackTest<<<1,32>>>(p,s,result);double cost;CUDA_CHECK(cudaMemcpy(&cost,result,sizeof(cost),cudaMemcpyDeviceToHost));
     double values[4]={r.slope,r.curvature,r.prediction,cost};if(fwrite(values,sizeof(double),4,out)!=4)return 4;}
   ++count;
 }
 CUDA_CHECK(cudaDeviceSynchronize());cudaFree(data);cudaFree(ids);cudaFree(result);fclose(in);fclose(out);printf("O5 kernel cases=%d\n",count);
}
