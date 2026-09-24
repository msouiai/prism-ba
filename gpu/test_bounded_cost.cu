#define OCA_CORE_LIBRARY
#include "oca_cuda.cu"

int main() {
  setenv("OCA_BOUNDED_BACKTRACK","1",1);
  setenv("OCA_BOUNDED_BACKTRACK_AUDIT","1",1);
  DeviceProblem p{}; DeviceState s{};
  p.ncam=p.npt=1; p.nobs=262147; // multiple waves plus a partial block
  std::vector<void*> allocations;
  auto upload=[&](auto values,auto** ptr){
    CUDA_CHECK(cudaMalloc(ptr,values.size()*sizeof(values[0])));
    allocations.push_back(*ptr);
    CUDA_CHECK(cudaMemcpy(*ptr,values.data(),values.size()*sizeof(values[0]),cudaMemcpyHostToDevice));
  };
  upload(std::vector<int>(p.nobs,0),&p.cam_idx);
  upload(std::vector<int>(p.nobs,0),&p.pt_idx);
  upload(std::vector<double>(2*p.nobs,0),&p.uv);
  upload(std::vector<double>{1,0,0,0,1,0,0,0,1},&s.R);
  upload(std::vector<double>{0,0,0},&s.t);
  upload(std::vector<double>{1,0,1},&s.X);
  upload(std::vector<double>{1},&p.f);
  upload(std::vector<double>{0},&p.k1);
  upload(std::vector<double>{0},&p.k2);
  const double expected=.5*p.nobs;
  BoundedCostStats stats;
  auto require=[](bool b){if(!b) throw std::runtime_error("bounded cost gate failed");};
  for(double bound:{expected*2,expected,expected-1e-7,expected*.001,0.,-1.}) {
    const double c=ComputeBacktrackCost(p,s,0,0,bound,expected*3,stats);
    require((std::isfinite(c)&&c<=bound)==(expected<=bound));
    if(c<=bound) require(c==expected);
  }
  require(stats.rejected>0 && stats.skipped>0 && stats.audit_calls==5);
  // Robust loss must bypass the bound and retain its full objective.
  long before=stats.calls;
  require(ComputeBacktrackCost(p,s,1,1,0,expected*3,stats)==ComputeCost(p,s,1,1));
  require(stats.calls==before);
  // Nonfinite projection must never turn into an accepted finite objective.
  double zero=0;CUDA_CHECK(cudaMemcpy(s.X+2,&zero,sizeof(double),cudaMemcpyHostToDevice));
  require(!std::isfinite(ComputeBacktrackCost(p,s,0,0,1,2,stats)));
  for(void* a:allocations)CUDA_CHECK(cudaFree(a));
  std::printf("bounded cost gate passed calls=%ld audited=%ld rejected=%ld skipped=%llu\n",
    stats.calls,stats.audit_calls,stats.rejected,stats.skipped);
}
