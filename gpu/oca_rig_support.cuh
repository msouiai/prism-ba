// oca_rig_support.cuh -- helpers the rig / fisheye / pinhole path
// (oca_rigfisheye.cuh) needs and which mfree_release's oca_cuda.cu defines in
// its shared section. Kept in a separate header on the prism-ba tree so the
// port of the MFREE rig path leaves prism's BAL/dof9 kernels untouched.
// Verbatim copies of mfree_release/solver/oca_cuda.cu @ 0a6cb5a.
#pragma once
#include <functional>
#include <unordered_map>

__global__ void KernelCostFinal(const Scalar* __restrict__ part, int nb, Scalar* __restrict__ out) {
  __shared__ Scalar sh[256]; Scalar a = 0.0;
  for (int i = threadIdx.x; i < nb; i += 256) a += part[i];
  sh[threadIdx.x] = a; __syncthreads();
  for (int st = 128; st > 0; st >>= 1) { if (threadIdx.x < st) sh[threadIdx.x] += sh[threadIdx.x + st]; __syncthreads(); }
  if (threadIdx.x == 0) *out = sh[0];
}

// from the cached R0 and pay O(1) per point instead of O(obs_p). The split is
// bit-identical by construction: the same Givens sequence in the same order,
// with the intermediate R0 spilled to memory (fp64, as in the register form).
template <class HT>
__global__ void MFPointFactorR0(const HT* __restrict__ Bo,
    const int* __restrict__ poff,const int* __restrict__ plist,int npt,
    Scalar* __restrict__ Rf0){
  int p=blockIdx.x*blockDim.x+threadIdx.x; if(p>=npt)return;
  Scalar Rp[6]={0,0,0,0,0,0};
  int s=poff[p],e=poff[p+1];
  for(int k=s;k<e;++k){ int o=plist[k];
    Scalar v0[3]={(Scalar)Bo[6*o],(Scalar)Bo[6*o+1],(Scalar)Bo[6*o+2]};   MFGivens(Rp,v0);
    Scalar v1[3]={(Scalar)Bo[6*o+3],(Scalar)Bo[6*o+4],(Scalar)Bo[6*o+5]}; MFGivens(Rp,v1); }
  for(int i=0;i<6;++i) Rf0[6*p+i]=Rp[i];
}
__global__ void MFPointFactorDamp(const Scalar* __restrict__ Rf0,const Scalar* __restrict__ Cdiag,
    Scalar tau,int npt,Scalar* __restrict__ Rf,int* __restrict__ ok,
    const Scalar* __restrict__ tau_arr=nullptr,Scalar tau_cap_dev=0.0){
  int p=blockIdx.x*blockDim.x+threadIdx.x; if(p>=npt)return;
  if(tau_arr) tau*=tau_arr[p];
  if(tau_cap_dev>0.0 && tau>tau_cap_dev) tau=tau_cap_dev;
  Scalar cd[3]={Cdiag[3*p],Cdiag[3*p+1],Cdiag[3*p+2]};
  Scalar tr=cd[0]+cd[1]+cd[2], fl=tau*tr/3.0; if(!(fl>0.0)) fl=1e-32;
  Scalar Rp[6]; for(int i=0;i<6;++i) Rp[i]=Rf0[6*p+i];
  for(int i=0;i<3;++i){ Scalar q=tau*cd[i]; if(!(q>1e-3*fl)) q=1e-3*fl;
    Scalar v[3]={0,0,0}; v[i]=sqrt(q); MFGivens(Rp,v); }
  ok[p]=((Rp[0]>0.0)&&(Rp[3]>0.0)&&(Rp[5]>0.0))?1:0;
  for(int i=0;i<6;++i) Rf[6*p+i]=Rp[i];
}

// V^-1 once per (observation, camera dof): CD=9 triangular solve pairs, i.e.
// ~54 fp64 divisions per observation, only ever to form the scalar g^T V^-1 g.
// V^-1 depends on the POINT alone, so hoist it -- one symmetric 3x3 inverse
// per point (npt << nobs, built from the same triangular solves, so no extra
// conditioning risk beyond the quadratic form's own rounding) -- and leave the
// per-observation kernel a quadratic form with no divisions at all.
__global__ void MFPointVinv(const Scalar* __restrict__ Rf,int npt,Scalar* __restrict__ S){
  int p=blockIdx.x*blockDim.x+threadIdx.x; if(p>=npt)return;
  const Scalar* Rp=Rf+6*p; Scalar* Sp=S+6*p;
  if(!(Rp[0]>0.0&&Rp[3]>0.0&&Rp[5]>0.0)){ for(int i=0;i<6;++i) Sp[i]=0.0; return; }
  Scalar col[3][3];
  for(int i=0;i<3;++i){ Scalar e[3]={0,0,0}; e[i]=1.0; Scalar u[3]; MFVinv(Rp,e,u);
    col[i][0]=u[0]; col[i][1]=u[1]; col[i][2]=u[2]; }
  // symmetrize: V^-1 is symmetric, the two triangular solves are not bitwise so
  Sp[0]=col[0][0];                 Sp[1]=0.5*(col[1][0]+col[0][1]);
  Sp[2]=0.5*(col[2][0]+col[0][2]); Sp[3]=col[1][1];
  Sp[4]=0.5*(col[2][1]+col[1][2]); Sp[5]=col[2][2];
}
template <int CD, class HT>
__global__ void MFDiagKS(const HT* __restrict__ Gp,const int* __restrict__ spt,
    const int* __restrict__ scam,const Scalar* __restrict__ S,int nobs,Scalar* __restrict__ dk){
  int k=blockIdx.x*blockDim.x+threadIdx.x; if(k>=nobs)return;
  int p=spt[k],c=scam[k];
  Scalar s0=S[6*p],s1=S[6*p+1],s2=S[6*p+2],s3=S[6*p+3],s4=S[6*p+4],s5=S[6*p+5];
  if(s0==0.0&&s3==0.0&&s5==0.0) return;      // matches MFDiagK's !ok early-out
  for(int i=0;i<CD;++i){
    Scalar g0=Gp[(size_t)(3*i+0)*nobs+k],g1=Gp[(size_t)(3*i+1)*nobs+k],g2=Gp[(size_t)(3*i+2)*nobs+k];
    Scalar q=g0*(s0*g0+s1*g1+s2*g2)+g1*(s1*g0+s3*g1+s4*g2)+g2*(s2*g0+s4*g1+s5*g2);
    atomicAdd(&dk[CD*c+i], -q); }
}

// AUDIT 2026-09-14 (C2): the block-reduced cost path caches its partial-sum
// buffer in a function-local static with a high-water cap. That was a REGRESSION
// against the legacy path, which allocated per call and therefore always landed
// on the CURRENT device: the library entry points call cudaSetDevice(gpu_index),
// so a process that solved on GPU 0 and then on GPU 1 reused the GPU-0 pointer
// whenever nb <= cap -> illegal access. Keying the cache on the device fixes it.
//
// Why a device-keyed static rather than a member of DeviceProblem (which has the
// right lifetime): ComputeCost takes a *const* DeviceProblem& and is called from
// ~20 solvers in this file, and the rig path has its own problem struct, so the
// member route needs mutable state plus a const_cast on two structs for exactly
// the same effect. One keyed cache keeps a single implementation honest.
// The realloc is also ordered null-first-then-allocate so a throwing cudaMalloc
// leaves {nullptr, 0} rather than a freed pointer with a stale non-zero cap.
struct MFCostScratch {
  Scalar* part = nullptr;
  int cap = 0;
  Scalar* out = nullptr;
  // Grow `part` to hold nb partials on the CURRENT device.
  void ensure(int nb) {
    if (nb <= cap) return;
    Scalar* old = part;
    part = nullptr; cap = 0;            // never leave a dangling pointer behind
    if (old) cudaFree(old);
    CUDA_CHECK(cudaMalloc(&part, (size_t)nb * sizeof(Scalar)));
    cap = nb;
  }
  void ensure_out() { if (!out) CUDA_CHECK(cudaMalloc(&out, sizeof(Scalar))); }
};
static MFCostScratch& MFCostScratchForCurrentDevice() {
  static std::unordered_map<int, MFCostScratch> per_device;
  int dev = 0; CUDA_CHECK(cudaGetDevice(&dev));
  return per_device[dev];
}

// AUDIT 2026-09-14 (C7): SolveMFreeShiftedCG / SolveRigFisheye raw-allocate ~20
// device buffers and free them only at the tail. CUDA_CHECK THROWS and nothing
// catches inside, so a mid-solve OOM inside COLMAP's repeated-BA loop leaked the
// fragment arrays (6.3 GB fp32 at 29M obs) for the process lifetime and made
// every later BA fail too. This registry is the scope guard: M() records every
// allocation, the destructor releases them on BOTH the normal and the throwing
// path. Order of release is irrelevant (no aliasing), and cudaFree(nullptr) is a
// no-op, so conditional buffers need no special case.
// IMPORTANT: declare the guard BEFORE the scratch state struct and the cuBLAS
// handle it releases, so those outlive the destructor that reads them.
struct MFDeviceScratch {
  std::vector<void*> ptrs;
  std::vector<std::function<void()>> deferred;   // state structs, handles, ...
  void track(void* q) { if (q) ptrs.push_back(q); }
  void alloc(void** q, size_t bytes) { CUDA_CHECK(cudaMalloc(q, bytes)); ptrs.push_back(*q); }
  void defer(std::function<void()> f) { deferred.push_back(std::move(f)); }
  ~MFDeviceScratch() {
    for (auto it = deferred.rbegin(); it != deferred.rend(); ++it) (*it)();
    for (void* q : ptrs) cudaFree(q);
  }
  MFDeviceScratch() = default;
  MFDeviceScratch(const MFDeviceScratch&) = delete;
  MFDeviceScratch& operator=(const MFDeviceScratch&) = delete;
};
// ROUND 10: CD templates the camera-block dimension. CD=6 reproduces round 9
