#pragma once

// Identical fixed-order cost reduction kernels to deterministic_cost.cuh.
// Only scratch ownership changes: every launch uses the bound solve workspace.
__global__ void W6CostPartials(
    const int* __restrict__ cam_idx, const int* __restrict__ pt_idx,
    const Scalar* __restrict__ uv, const Scalar* __restrict__ R,
    const Scalar* __restrict__ t, const Scalar* __restrict__ X,
    const Scalar* __restrict__ f, const Scalar* __restrict__ k1,
    const Scalar* __restrict__ k2, int nobs, Scalar* __restrict__ partials,
    int rk, Scalar rk_a2) {
  const int o=blockIdx.x*blockDim.x+threadIdx.x; Scalar value=0.0;
  if(o<nobs){
    const int c=cam_idx[o],p=pt_idx[o]; const Scalar* Rc=R+9*c; const Scalar* Xp=X+3*p;
    const Scalar Px=Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2]+t[3*c];
    const Scalar Py=Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2]+t[3*c+1];
    const Scalar Pz=Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2]+t[3*c+2];
    const Scalar xp=-Px/Pz,yp=-Py/Pz,r2=xp*xp+yp*yp;
    const Scalar distortion=1.0+k1[c]*r2+k2[c]*r2*r2;
    const Scalar rx=f[c]*distortion*xp-uv[2*o],ry=f[c]*distortion*yp-uv[2*o+1];
    const Scalar ss=rx*rx+ry*ry; value=0.5*(rk?OcaRho(rk,rk_a2,ss):ss);
  }
  __shared__ Scalar sums[256]; sums[threadIdx.x]=value; __syncthreads();
  for(int stride=128;stride;stride>>=1){if(threadIdx.x<stride)sums[threadIdx.x]+=sums[threadIdx.x+stride];__syncthreads();}
  if(threadIdx.x==0)partials[blockIdx.x]=sums[0];
}
__global__ void W6ReduceScalarFixed(const Scalar* __restrict__ partials,int count,Scalar* __restrict__ output){
  Scalar value=0.0;for(int i=threadIdx.x;i<count;i+=blockDim.x)value+=partials[i];
  __shared__ Scalar sums[256];sums[threadIdx.x]=value;__syncthreads();
  for(int stride=128;stride;stride>>=1){if(threadIdx.x<stride)sums[threadIdx.x]+=sums[threadIdx.x+stride];__syncthreads();}
  if(threadIdx.x==0)output[0]=sums[0];
}
inline Scalar PrismW6DeterministicCost(const DeviceProblem& p,const DeviceState& s,int rk,Scalar rk_a2){
  auto& owned=OwnedWorkspaceCurrent();const int blocks=GridSize(p.nobs);
  if(blocks>owned.cost_capacity)throw std::runtime_error("BAL workspace cost capacity exceeded");
  W6CostPartials<<<blocks,256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),p.nobs,owned.cost_partials,rk,rk_a2);
  W6ReduceScalarFixed<<<1,256>>>(owned.cost_partials,blocks,owned.cost_output);
  Scalar cost=0.0;CUDA_CHECK(cudaMemcpy(&cost,owned.cost_output,sizeof(Scalar),cudaMemcpyDeviceToHost));return cost;
}
