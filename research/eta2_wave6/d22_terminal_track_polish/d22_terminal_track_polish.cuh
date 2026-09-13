#pragma once
#include "../../eta2_wave5/targeted_triangulation.cuh"
#include <chrono>

struct D22TerminalTrackPolish {
  int nc,np,no;unsigned char*flags=nullptr;unsigned long long*counts=nullptr;
  double*improvement=nullptr,*step=nullptr;long calls=0;double seconds=0.;
  D22TerminalTrackPolish(int ncam,int npt,int nobs):nc(ncam),np(npt),no(nobs){
    CUDA_CHECK(cudaMalloc(&flags,(size_t)no));CUDA_CHECK(cudaMemset(flags,1,(size_t)no));
    CUDA_CHECK(cudaMalloc(&counts,5*sizeof(*counts)));CUDA_CHECK(cudaMalloc(&improvement,sizeof(*improvement)));
    CUDA_CHECK(cudaMalloc(&step,(9ul*nc+3ul*np)*sizeof(double)));
  }
  ~D22TerminalTrackPolish(){cudaFree(flags);cudaFree(counts);cudaFree(improvement);cudaFree(step);}
  eta2_w5_a1::Result Apply(const DeviceProblem&p,const DeviceState&old,const DeviceState&candidate){
    auto started=std::chrono::steady_clock::now();++calls;
    CUDA_CHECK(cudaMemset(counts,0,5*sizeof(*counts)));CUDA_CHECK(cudaMemset(improvement,0,sizeof(*improvement)));
    CUDA_CHECK(cudaMemset(step,0,(9ul*nc+3ul*np)*sizeof(double)));
    eta2_w5_a1::repair<<<GridSize(np),256>>>(p.point_obs_offsets,p.point_obs_list,p.cam_idx,p.uv,
      old.R,old.t,old.X,candidate.R,candidate.t,candidate.X,INTR_F(p,candidate),INTR_K1(p,candidate),
      INTR_K2(p,candidate),flags,np,nc,step,counts,improvement);
    eta2_w5_a1::Result result;unsigned long long h[5];
    CUDA_CHECK(cudaMemcpy(h,counts,5*sizeof(*counts),cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(&result.improvement,improvement,sizeof(*improvement),cudaMemcpyDeviceToHost));
    result.flagged=no;result.eligible=h[1];result.margin_rejects=h[2];result.algebra_failures=h[3];result.wins=h[4];
    seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();return result;
  }
  void Final(){std::printf("D22_SUMMARY calls=%ld seconds=%.9g\n",calls,seconds);}
};

