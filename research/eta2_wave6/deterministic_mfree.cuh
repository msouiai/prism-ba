#pragma once

__global__ void W6InvertPermutation(const int* __restrict__ original_to_slot,
                                    int count,int* __restrict__ slot_to_original){
  const int o=blockIdx.x*blockDim.x+threadIdx.x;
  if(o<count)slot_to_original[original_to_slot[o]]=o;
}

__device__ __forceinline__ void W6ResidualGrad9(
    int o,int c,int p,const Scalar* uv,const Scalar* R,const Scalar* t,
    const Scalar* X,const Scalar* f,const Scalar* k1,const Scalar* k2,
    Scalar k2mask,int rk,Scalar rk_a2,Scalar* gx,Scalar* gy,
    Scalar& rx,Scalar& ry,Scalar& radius2){
  const Scalar* Rc=R+9*c;const Scalar* Xp=X+3*p;
  Scalar r0x,r0y;
  BalResidualGrad12(Rc[0],Rc[1],Rc[2],Rc[3],Rc[4],Rc[5],Rc[6],Rc[7],Rc[8],
      t[3*c],t[3*c+1],t[3*c+2],Xp[0],Xp[1],Xp[2],f[c],k1[c],k2[c],
      uv[2*o],uv[2*o+1],gx,gy,&r0x,&r0y);
  gx[8]*=k2mask;gy[8]*=k2mask;
  rx=r0x;ry=r0y;
  const Scalar px=Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2]+t[3*c];
  const Scalar py=Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2]+t[3*c+1];
  const Scalar pz=Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2]+t[3*c+2];
  const Scalar qx=-px/pz,qy=-py/pz;radius2=qx*qx+qy*qy;
  if(rk){const Scalar sw=sqrt(OcaRobustW(rk,rk_a2,rx*rx+ry*ry));
    rx*=sw;ry*=sw;for(int i=0;i<12;++i){gx[i]*=sw;gy[i]*=sw;}}
}

// One fixed warp owns a camera.  Each lane accumulates a stable strided list,
// then the warp tree fixes the inter-lane order.
__global__ void W6DeterministicCameraAssembly9(
    const int* __restrict__ coff,const int* __restrict__ slot_to_obs,
    const int* __restrict__ ci,const int* __restrict__ pi,
    const Scalar* __restrict__ uv,const Scalar* __restrict__ R,
    const Scalar* __restrict__ t,const Scalar* __restrict__ X,
    const Scalar* __restrict__ f,const Scalar* __restrict__ k1,
    const Scalar* __restrict__ k2,int ncam,Scalar k2mask,int rk,Scalar rk_a2,
    Scalar* __restrict__ Hcc,Scalar* __restrict__ bc,
    Scalar* __restrict__ r2acc,Scalar* __restrict__ obscnt){
  const int c=blockIdx.x,lane=threadIdx.x;if(c>=ncam)return;
  Scalar g[9]={};Scalar h[45]={};Scalar rs=0,cnt=0;
  for(int slot=coff[c]+lane;slot<coff[c+1];slot+=32){
    const int o=slot_to_obs[slot],p=pi[o];Scalar gx[12],gy[12],rx,ry,r2;
    W6ResidualGrad9(o,c,p,uv,R,t,X,f,k1,k2,k2mask,rk,rk_a2,gx,gy,rx,ry,r2);
    for(int i=0;i<9;++i)g[i]+=rx*gx[i]+ry*gy[i];
    int q=0;for(int i=0;i<9;++i)for(int j=0;j<=i;++j,++q)
      h[q]+=gx[i]*gx[j]+gy[i]*gy[j];
    rs+=r2;cnt+=1.0;
  }
  for(int off=16;off;off>>=1){
    for(int i=0;i<9;++i)g[i]+=__shfl_down_sync(0xffffffffu,g[i],off);
    for(int i=0;i<45;++i)h[i]+=__shfl_down_sync(0xffffffffu,h[i],off);
    rs+=__shfl_down_sync(0xffffffffu,rs,off);
    cnt+=__shfl_down_sync(0xffffffffu,cnt,off);
  }
  if(lane==0){
    for(int i=0;i<9;++i)bc[9*c+i]=g[i];
    int q=0;for(int i=0;i<9;++i)for(int j=0;j<=i;++j,++q){
      Hcc[81*c+9*i+j]=h[q];Hcc[81*c+9*j+i]=h[q];}
    if(r2acc)r2acc[c]=rs;if(obscnt)obscnt[c]=cnt;
  }
}

__global__ void W6DeterministicPointAssembly9(
    const int* __restrict__ offsets,const int* __restrict__ order,
    const int* __restrict__ ci,const int* __restrict__ pi,
    const Scalar* __restrict__ uv,const Scalar* __restrict__ R,
    const Scalar* __restrict__ t,const Scalar* __restrict__ X,
    const Scalar* __restrict__ f,const Scalar* __restrict__ k1,
    const Scalar* __restrict__ k2,int npt,Scalar k2mask,int rk,Scalar rk_a2,
    Scalar* __restrict__ Cdiag,Scalar* __restrict__ bp){
  const int p=blockIdx.x,lane=threadIdx.x;if(p>=npt)return;
  Scalar g[3]={},d[3]={};
  for(int slot=offsets[p]+lane;slot<offsets[p+1];slot+=32){
    const int o=order[slot],c=ci[o];Scalar gx[12],gy[12],rx,ry,r2;
    W6ResidualGrad9(o,c,p,uv,R,t,X,f,k1,k2,k2mask,rk,rk_a2,gx,gy,rx,ry,r2);
    for(int j=0;j<3;++j){g[j]+=rx*gx[9+j]+ry*gy[9+j];d[j]+=gx[9+j]*gx[9+j]+gy[9+j]*gy[9+j];}
  }
  for(int off=16;off;off>>=1)for(int j=0;j<3;++j){
    g[j]+=__shfl_down_sync(0xffffffffu,g[j],off);
    d[j]+=__shfl_down_sync(0xffffffffu,d[j],off);
  }
  if(lane==0)for(int j=0;j<3;++j){bp[3*p+j]=g[j];Cdiag[3*p+j]=d[j];}
}

template<int CD,class HT>
__global__ void W6DeterministicPass1(
    const HT* __restrict__ Gp,const int* __restrict__ offsets,
    const int* __restrict__ order,const int* __restrict__ ci,
    const int* __restrict__ original_to_slot,const Scalar* __restrict__ v,
    int npt,int nobs,Scalar* __restrict__ tacc){
  const int p=blockIdx.x,lane=threadIdx.x;if(p>=npt)return;Scalar out[3]={};
  for(int q=offsets[p]+lane;q<offsets[p+1];q+=32){
    const int o=order[q],slot=original_to_slot[o],c=ci[o];const Scalar* vc=v+CD*c;
    for(int j=0;j<3;++j){Scalar value=0;
      for(int i=0;i<CD;++i)value+=(Scalar)Gp[(size_t)(3*i+j)*nobs+slot]*vc[i];
      out[j]+=value;}
  }
  for(int off=16;off;off>>=1)for(int j=0;j<3;++j)
    out[j]+=__shfl_down_sync(0xffffffffu,out[j],off);
  if(lane==0)for(int j=0;j<3;++j)tacc[3*p+j]=out[j];
}

template<int CD,class HT>
__global__ void W6DeterministicPass1Multi(
    const HT* __restrict__ Gp,const int* __restrict__ offsets,
    const int* __restrict__ order,const int* __restrict__ ci,
    const int* __restrict__ original_to_slot,const Scalar* __restrict__ XCU,
    int n_cf,int nl,int npt,int nobs,Scalar* __restrict__ TACC,int n_p){
  const int p=blockIdx.x,lane=threadIdx.x;if(p>=npt)return;Scalar out[15]={};
  for(int q=offsets[p]+lane;q<offsets[p+1];q+=32){
    const int o=order[q],slot=original_to_slot[o],c=ci[o];
    for(int l=0;l<nl;++l){const Scalar* vc=XCU+(size_t)l*n_cf+CD*c;
      for(int j=0;j<3;++j){Scalar value=0;
        for(int i=0;i<CD;++i)value+=(Scalar)Gp[(size_t)(3*i+j)*nobs+slot]*vc[i];
        out[3*l+j]+=value;}}
  }
  for(int off=16;off;off>>=1)for(int q=0;q<3*nl;++q)
    out[q]+=__shfl_down_sync(0xffffffffu,out[q],off);
  if(lane==0)for(int l=0;l<nl;++l)for(int j=0;j<3;++j)
    TACC[(size_t)l*n_p+3*p+j]=out[3*l+j];
}
