#pragma once

// Four point-owned warps per block. Within each point this preserves the
// deterministic q+=32 traversal/tree, then immediately applies the 3x3 factor.
template<int CD,class HT>
__global__ void AuditFusedPass1Vinv(
    const HT* __restrict__ Gp,const int* __restrict__ offsets,
    const int* __restrict__ order,const int* __restrict__ ci,
    const int* __restrict__ original_to_slot,const Scalar* __restrict__ v,
    const Scalar* __restrict__ Rf,int npt,int nobs,Scalar* __restrict__ u){
  constexpr int WARPS=4;
  const int warp=threadIdx.x>>5,lane=threadIdx.x&31;
  const int p=blockIdx.x*WARPS+warp;if(p>=npt)return;Scalar out[3]={};
  for(int q=offsets[p]+lane;q<offsets[p+1];q+=32){
    const int o=order[q],slot=original_to_slot[o],c=ci[o];const Scalar* vc=v+CD*c;
    for(int j=0;j<3;++j){Scalar value=0;
      for(int i=0;i<CD;++i)value+=(Scalar)Gp[(size_t)(3*i+j)*nobs+slot]*vc[i];
      out[j]+=value;}
  }
  for(int off=16;off;off>>=1)for(int j=0;j<3;++j)
    out[j]+=__shfl_down_sync(0xffffffffu,out[j],off);
  if(lane==0){const Scalar* Rp=Rf+6*p;
    if(!(Rp[0]>0.0&&Rp[3]>0.0&&Rp[5]>0.0))u[3*p]=u[3*p+1]=u[3*p+2]=0.0;
    else {Scalar solved[3];MFVinv(Rp,out,solved);u[3*p]=solved[0];u[3*p+1]=solved[1];u[3*p+2]=solved[2];}}
}
