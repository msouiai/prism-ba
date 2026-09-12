#pragma once
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <stdexcept>
#include <vector>
#include "coherent_rows.cuh"

// The scoring tail receives the actual positive physical camera solve xcu;
// the native final negate makes the proposed camera direction -xcu.
__global__ void FrontPhysicalForward(const int* ci,const int* slot,const double* Jc,
    const double* xcu,int no,double* y){
  int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=no)return;int c=ci[o],a=slot[o];
  double x=0,z=0;for(int k=0;k<9;++k){x+=Jc[18ul*a+k]*xcu[9*c+k];z+=Jc[18ul*a+9+k]*xcu[9*c+k];}
  y[2ul*o]=x;y[2ul*o+1]=z;
}
__global__ void FrontCheckFactors(const double* R,const int* ok,int np,int* invalid){
  int j=blockIdx.x*blockDim.x+threadIdx.x;if(j>=np)return;bool bad=!ok[j];
  for(int k=0;k<6;++k)bad=bad||!isfinite(R[6ul*j+k]);
  if(bad)atomicAdd(invalid,1);
}

struct FrontloadTotals {
  long attempts=0,products=0,completions=0,fresh_checks=0,extra_fresh_products=0;
  size_t allocated_bytes=0,peak_attempt_bytes=0;
  double construction_seconds=0,destruction_seconds=0;
  void Print() const {
    std::printf("FRONTLOAD_SUMMARY attempts=%ld products=%ld point_completions=%ld fresh_checks=%ld extra_fresh_products=%ld allocated_bytes=%zu peak_attempt_bytes=%zu construction_seconds=%.9g destruction_seconds=%.9g\n",
      attempts,products,completions,fresh_checks,extra_fresh_products,allocated_bytes,peak_attempt_bytes,construction_seconds,destruction_seconds);
  }
};
struct FrontloadAttempt {
  const DeviceProblem& p;FrontloadTotals& totals;const double* E;const double lambda;
  const int nc,np,no,nc9,np3;int outer,retry;
  double *Jc,*Jp,*residual,*Q,*R,*Rtmp,*gp,*y,*g,*u,*rhs,*audit_r;
  int *order,*ok,*invalid;
  std::vector<double*> allocations;size_t bytes=0;
  long products=0,completions=0;
  bool fresh_recorded=false;double fresh_relative=INFINITY;
  using Clock=std::chrono::steady_clock;
  double* New(size_t n){double* a=nullptr;CUDA_CHECK(cudaMalloc(&a,8*n));allocations.push_back(a);bytes+=8*n;return a;}
  FrontloadAttempt(const DeviceProblem& problem,const DeviceState& state,const double* scaling,
      const double* Cdiag,const double* r2,const double* count,double lam,int k,int r,FrontloadTotals& counters)
      :p(problem),totals(counters),E(scaling),lambda(lam),nc(p.ncam),np(p.npt),no(p.nobs),nc9(9*nc),np3(3*np),outer(k),retry(r){
    auto start=Clock::now();
    Jc=New(18ul*no);Jp=New(6ul*no);residual=New(2ul*no);Q=New(nc9);
    R=New(6ul*np);Rtmp=New(6ul*np);gp=New(np3);y=New(2ul*no);g=New(np3);u=New(np3);
    rhs=New(nc9);audit_r=New(nc9);
    CUDA_CHECK(cudaMalloc(&order,4ul*no));CUDA_CHECK(cudaMalloc(&ok,4ul*np));CUDA_CHECK(cudaMalloc(&invalid,4));bytes+=4ul*(no+np+1);
    B0Rows<<<GridSize(no),256>>>(p.cam_idx,p.pt_idx,p.obs2cslot,p.uv,state.R,state.t,state.X,
      INTR_F(p,state),INTR_K1(p,state),INTR_K2(p,state),no,Jc,Jp,residual,order);
    B0Prior<<<GridSize(nc),256>>>(INTR_F(p,state),r2,count,nc,Q);
    MFPointFactorObs<double><<<GridSize(np),256>>>(Jp,p.point_obs_offsets,p.point_obs_list,np,Rtmp);
    MFPointFactorTau<<<GridSize(np),256>>>(Cdiag,Rtmp,lambda,np,R,ok);
    CUDA_CHECK(cudaMemset(invalid,0,4));FrontCheckFactors<<<GridSize(np),256>>>(R,ok,np,invalid);
    int bad=0;CUDA_CHECK(cudaMemcpy(&bad,invalid,4,cudaMemcpyDeviceToHost));
    if(bad)throw std::runtime_error("frontload coherent point factor invalid");
    B0PointRhs<<<(np+7)/8,256>>>(p.point_obs_offsets,p.point_obs_list,Jp,residual,np,gp);
    MFVinvApply<<<GridSize(np),256>>>(R,gp,np,u);
    B0Adjoint<<<nc,256>>>(p.mf_coff,order,p.pt_idx,Jc,Jp,residual,u,E,Q,nullptr,0,nc,rhs);
    ++totals.attempts;totals.allocated_bytes+=bytes;totals.peak_attempt_bytes=std::max(totals.peak_attempt_bytes,bytes);
    totals.construction_seconds+=std::chrono::duration<double>(Clock::now()-start).count();
  }
  ~FrontloadAttempt(){
    auto start=Clock::now();for(auto a:allocations)cudaFree(a);cudaFree(order);cudaFree(ok);cudaFree(invalid);
    totals.destruction_seconds+=std::chrono::duration<double>(Clock::now()-start).count();
  }
  // Includes point damping through R and intrinsic Q, but NOT camera lambda.
  // The unchanged native CG loop adds lambda*x exactly once after KvS.
  void ProductBase(const double* x,double* out){
    B0Forward<<<GridSize(no),256>>>(p.cam_idx,p.obs2cslot,Jc,E,x,no,y);
    B0PointRhs<<<(np+7)/8,256>>>(p.point_obs_offsets,p.point_obs_list,Jp,y,np,g);
    MFVinvApply<<<GridSize(np),256>>>(R,g,np,u);
    B0Adjoint<<<nc,256>>>(p.mf_coff,order,p.pt_idx,Jc,Jp,y,u,E,Q,x,0,nc,out);
    ++products;++totals.products;
  }
  void CompletePhysical(const double* xcu,double* point){
    FrontPhysicalForward<<<GridSize(no),256>>>(p.cam_idx,p.obs2cslot,Jc,xcu,no,y);
    B0PointRhs<<<(np+7)/8,256>>>(p.point_obs_offsets,p.point_obs_list,Jp,y,np,g);
    MFBackSub<<<GridSize(np),256>>>(R,gp,g,np,point);
    ++completions;++totals.completions;
  }
  void RecordFresh(double norm,double nb){fresh_relative=norm/std::max(nb,1e-300);fresh_recorded=true;++totals.fresh_checks;}
  void EnsureFresh(cublasHandle_t blas,const double* x,double nb,long& native_matvecs){
    if(fresh_recorded)return;
    ProductBase(x,audit_r);++native_matvecs;++totals.extra_fresh_products;
    cublasDaxpy(blas,nc9,&lambda,x,1,audit_r,1);const double minus=-1;
    cublasDaxpy(blas,nc9,&minus,rhs,1,audit_r,1);double norm=0;cublasDnrm2(blas,nc9,audit_r,1,&norm);RecordFresh(norm,nb);
  }
};
