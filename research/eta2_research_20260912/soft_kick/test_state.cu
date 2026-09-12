#define OCA_CORE_LIBRARY
#include "build/prism_soft_kick.cu"
int main(){
 DeviceProblem p{};p.ncam=1;p.npt=1;p.nobs=1;DeviceState s{};AllocState(s,1,1,true);
 int zero=0;double uv[2]={0,0},r[9]={1,0,0,0,1,0,0,0,1},t[3]={0,0,0},x[3]={.2,.1,-3},intr[3]={500,.01,0};
 CUDA_CHECK(cudaMalloc(&p.cam_idx,4));CUDA_CHECK(cudaMalloc(&p.pt_idx,4));CUDA_CHECK(cudaMalloc(&p.uv,16));
 CUDA_CHECK(cudaMemcpy(p.cam_idx,&zero,4,cudaMemcpyHostToDevice));CUDA_CHECK(cudaMemcpy(p.pt_idx,&zero,4,cudaMemcpyHostToDevice));CUDA_CHECK(cudaMemcpy(p.uv,uv,16,cudaMemcpyHostToDevice));
 CUDA_CHECK(cudaMemcpy(s.R,r,72,cudaMemcpyHostToDevice));CUDA_CHECK(cudaMemcpy(s.t,t,24,cudaMemcpyHostToDevice));CUDA_CHECK(cudaMemcpy(s.X,x,24,cudaMemcpyHostToDevice));CUDA_CHECK(cudaMemcpy(s.intr,intr,24,cudaMemcpyHostToDevice));
 bool restored=false,kept=false;double pre=ComputeCost(p,s,0,0),post=0;
 size_t free_before=0,free_after=0,total=0;CUDA_CHECK(cudaMemGetInfo(&free_before,&total));
 {
  prism_soft::Native soft(1,1,1);AllocState(soft.snapshot,1,1,true);CopyState(soft.snapshot,s,1,1);soft.saved=true;soft.pre_cost=pre;
  double badx[3]={1,.5,-3},badt[3]={.01,.02,0},badintr[3]={600,.02,0};
  CUDA_CHECK(cudaMemcpy(s.X,badx,24,cudaMemcpyHostToDevice));CUDA_CHECK(cudaMemcpy(s.t,badt,24,cudaMemcpyHostToDevice));CUDA_CHECK(cudaMemcpy(s.intr,badintr,24,cudaMemcpyHostToDevice));
  double cost=ComputeCost(p,s,0,0);if(!(cost>pre))throw std::runtime_error("test must start uphill");
  restored=soft.RestoreBest(p,s,cost);post=cost;
  double hx[3],ht[3],hi[3],hr[9];CUDA_CHECK(cudaMemcpy(hx,s.X,24,cudaMemcpyDeviceToHost));CUDA_CHECK(cudaMemcpy(ht,s.t,24,cudaMemcpyDeviceToHost));CUDA_CHECK(cudaMemcpy(hi,s.intr,24,cudaMemcpyDeviceToHost));CUDA_CHECK(cudaMemcpy(hr,s.R,72,cudaMemcpyDeviceToHost));
  if(!restored||cost!=pre||memcmp(hx,x,24)||memcmp(ht,t,24)||memcmp(hi,intr,24)||memcmp(hr,r,72))throw std::runtime_error("full-state restoration mismatch");
  double goodx[3]={0,0,-3};CUDA_CHECK(cudaMemcpy(s.X,goodx,24,cudaMemcpyHostToDevice));cost=ComputeCost(p,s,0,0);
  kept=!soft.RestoreBest(p,s,cost);if(!kept||cost!=0)throw std::runtime_error("better current state was not kept");
 }
 CUDA_CHECK(cudaDeviceSynchronize());CUDA_CHECK(cudaMemGetInfo(&free_after,&total));
 if(free_after!=free_before)throw std::runtime_error("new state helper allocation not released");
 cudaFree(s.R);cudaFree(s.t);cudaFree(s.X);cudaFree(s.intr);cudaFree(p.cam_idx);cudaFree(p.pt_idx);cudaFree(p.uv);
 // Context teardown; the frozen ComputeCost scratch is process-static.
 printf("SOFT_STATE_MEMORY warm_free_before=%zu warm_free_after=%zu new_resident_bytes=%lld\n",free_before,free_after,(long long)free_before-(long long)free_after);
 CUDA_CHECK(cudaDeviceReset());
 printf("SOFT_STATE_TEST pass=1 restored=%d kept=%d pre=%.17g restored_cost=%.17g\n",(int)restored,(int)kept,pre,post);
}
