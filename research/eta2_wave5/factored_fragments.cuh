#pragma once

// Wave-5 B1: compact factorization of the 2x9 camera / 2x3 point Jacobian.
// The frozen SIMPLE_RADIAL path fixes k2, so one observation is represented by
//
//   P = dr/dY                         6 floats
//   q = R X (rotation lever arm)      3 floats
//   dr/d(f,k1)                        4 floats
//
// instead of the 9x3 cross block W = Jc^T Jp (27 floats).  R is read from
// camera state and normally reused from cache because the champion stores the
// factors in camera-major order.  All contractions are evaluated without
// materialising W.

constexpr int W5_FACTORED_VALUES = 13;

struct W5FactoredObs {
  float px, py, pz;      // first residual row of dr/dY
  float yx, yy, yz;      // second residual row of dr/dY
  float qx, qy, qz;      // R X, excluding translation
  float fx, kx;          // first residual derivatives wrt f, k1
  float fy, ky;          // second residual derivatives wrt f, k1
};

template <class HT>
__device__ __forceinline__ W5FactoredObs W5LoadFactored(
    const HT* __restrict__ F, int nobs, int k) {
  W5FactoredObs a;
  a.px=(float)F[(size_t)0*nobs+k];  a.py=(float)F[(size_t)1*nobs+k];
  a.pz=(float)F[(size_t)2*nobs+k];  a.yx=(float)F[(size_t)3*nobs+k];
  a.yy=(float)F[(size_t)4*nobs+k];  a.yz=(float)F[(size_t)5*nobs+k];
  a.qx=(float)F[(size_t)6*nobs+k];  a.qy=(float)F[(size_t)7*nobs+k];
  a.qz=(float)F[(size_t)8*nobs+k];  a.fx=(float)F[(size_t)9*nobs+k];
  a.kx=(float)F[(size_t)10*nobs+k]; a.fy=(float)F[(size_t)11*nobs+k];
  a.ky=(float)F[(size_t)12*nobs+k];
  return a;
}

__device__ __forceinline__ void W5PointRows(
    const W5FactoredObs& a, const Scalar* __restrict__ R,
    Scalar* __restrict__ bx, Scalar* __restrict__ by) {
  bx[0]=R[0]*(Scalar)a.px+R[3]*(Scalar)a.py+R[6]*(Scalar)a.pz;
  bx[1]=R[1]*(Scalar)a.px+R[4]*(Scalar)a.py+R[7]*(Scalar)a.pz;
  bx[2]=R[2]*(Scalar)a.px+R[5]*(Scalar)a.py+R[8]*(Scalar)a.pz;
  by[0]=R[0]*(Scalar)a.yx+R[3]*(Scalar)a.yy+R[6]*(Scalar)a.yz;
  by[1]=R[1]*(Scalar)a.yx+R[4]*(Scalar)a.yy+R[7]*(Scalar)a.yz;
  by[2]=R[2]*(Scalar)a.yx+R[5]*(Scalar)a.yy+R[8]*(Scalar)a.yz;
}

// Jp u = P (R u).  This associativity avoids constructing the six entries of
// Jp when only its action is needed.
__device__ __forceinline__ void W5PointApply(
    const W5FactoredObs& a,const Scalar* __restrict__ R,
    const Scalar* __restrict__ u,Scalar& x,Scalar& y) {
  const Scalar q0=R[0]*u[0]+R[1]*u[1]+R[2]*u[2];
  const Scalar q1=R[3]*u[0]+R[4]*u[1]+R[5]*u[2];
  const Scalar q2=R[6]*u[0]+R[7]*u[1]+R[8]*u[2];
  x=(Scalar)a.px*q0+(Scalar)a.py*q1+(Scalar)a.pz*q2;
  y=(Scalar)a.yx*q0+(Scalar)a.yy*q1+(Scalar)a.yz*q2;
}

// Jp^T [x,y] = R^T P^T [x,y].
__device__ __forceinline__ void W5PointTransposeApply(
    const W5FactoredObs& a,const Scalar* __restrict__ R,
    Scalar x,Scalar y,Scalar* __restrict__ out) {
  const Scalar p0=(Scalar)a.px*x+(Scalar)a.yx*y;
  const Scalar p1=(Scalar)a.py*x+(Scalar)a.yy*y;
  const Scalar p2=(Scalar)a.pz*x+(Scalar)a.yz*y;
  out[0]=R[0]*p0+R[3]*p1+R[6]*p2;
  out[1]=R[1]*p0+R[4]*p1+R[7]*p2;
  out[2]=R[2]*p0+R[5]*p1+R[8]*p2;
}

__device__ __forceinline__ void W5CameraRow(
    const W5FactoredObs& a, int i, Scalar& ax, Scalar& ay) {
  switch(i) {
    case 0:
      ax=(Scalar)a.qy*a.pz-(Scalar)a.qz*a.py;
      ay=(Scalar)a.qy*a.yz-(Scalar)a.qz*a.yy; break;
    case 1:
      ax=(Scalar)a.qz*a.px-(Scalar)a.qx*a.pz;
      ay=(Scalar)a.qz*a.yx-(Scalar)a.qx*a.yz; break;
    case 2:
      ax=(Scalar)a.qx*a.py-(Scalar)a.qy*a.px;
      ay=(Scalar)a.qx*a.yy-(Scalar)a.qy*a.yx; break;
    case 3: ax=(Scalar)a.px; ay=(Scalar)a.yx; break;
    case 4: ax=(Scalar)a.py; ay=(Scalar)a.yy; break;
    case 5: ax=(Scalar)a.pz; ay=(Scalar)a.yz; break;
    case 6: ax=(Scalar)a.fx; ay=(Scalar)a.fy; break;
    case 7: ax=(Scalar)a.kx; ay=(Scalar)a.ky; break;
    default: ax=0.0; ay=0.0; break; // fixed k2 coordinate
  }
}

template <class HT>
__global__ void MFAssembleFactored9(
    const int* __restrict__ ci,const int* __restrict__ pi,const Scalar* __restrict__ uv,
    const Scalar* __restrict__ R,const Scalar* __restrict__ t,const Scalar* __restrict__ X,
    const Scalar* __restrict__ f,const Scalar* __restrict__ k1,const Scalar* __restrict__ k2,
    const int* __restrict__ o2slot,int nobs,Scalar* __restrict__ Hcc,
    Scalar* __restrict__ Cdiag,HT* __restrict__ F,HT* __restrict__ Bo,
    Scalar* __restrict__ bc,Scalar* __restrict__ bp,Scalar k2mask=0.0,
    Scalar* __restrict__ r2acc=nullptr,Scalar* __restrict__ obscnt=nullptr,
    int rk=0,Scalar rk_a2=0.0) {
  int o=blockIdx.x*blockDim.x+threadIdx.x; if(o>=nobs)return;
  int c=ci[o],p=pi[o];
  const Scalar* Rc=R+9*c; const Scalar* Xp=X+3*p;
  Scalar qx=Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2];
  Scalar qy=Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2];
  Scalar qz=Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2];
  Scalar Px=qx+t[3*c],Py=qy+t[3*c+1],Pz=qz+t[3*c+2];
  Scalar xq=-Px/Pz,yq=-Py/Pz,r2=xq*xq+yq*yq;
  Scalar dist=1.0+k1[c]*r2+k2[c]*r2*r2;
  Scalar rx=f[c]*dist*xq-uv[2*o],ry=f[c]*dist*yq-uv[2*o+1];
  Scalar gx[12],gy[12],r0x,r0y;
  BalResidualGrad12(Rc[0],Rc[1],Rc[2],Rc[3],Rc[4],Rc[5],Rc[6],Rc[7],Rc[8],
      t[3*c],t[3*c+1],t[3*c+2],Xp[0],Xp[1],Xp[2],f[c],k1[c],k2[c],
      uv[2*o],uv[2*o+1],gx,gy,&r0x,&r0y);
  gx[8]*=k2mask; gy[8]*=k2mask;
  if(r2acc){ atomicAdd(&r2acc[c],r2); atomicAdd(&obscnt[c],(Scalar)1.0); }
  if(rk) {
    const Scalar sw=sqrt(OcaRobustW(rk,rk_a2,rx*rx+ry*ry));
    rx*=sw; ry*=sw;
    for(int i=0;i<12;++i){gx[i]*=sw;gy[i]*=sw;}
  }
  for(int i=0;i<9;++i) atomicAdd(&bc[9*c+i],rx*gx[i]+ry*gy[i]);
  for(int i=0;i<3;++i) atomicAdd(&bp[3*p+i],rx*gx[9+i]+ry*gy[9+i]);
  for(int i=0;i<9;++i) for(int j=0;j<9;++j)
    atomicAdd(&Hcc[81*c+9*i+j],gx[i]*gx[j]+gy[i]*gy[j]);
  for(int i=0;i<3;++i)
    atomicAdd(&Cdiag[3*p+i],gx[9+i]*gx[9+i]+gy[9+i]*gy[9+i]);
  const int k=o2slot[o];
  F[(size_t)0*nobs+k]=(HT)gx[3]; F[(size_t)1*nobs+k]=(HT)gx[4];
  F[(size_t)2*nobs+k]=(HT)gx[5]; F[(size_t)3*nobs+k]=(HT)gy[3];
  F[(size_t)4*nobs+k]=(HT)gy[4]; F[(size_t)5*nobs+k]=(HT)gy[5];
  F[(size_t)6*nobs+k]=(HT)qx;    F[(size_t)7*nobs+k]=(HT)qy;
  F[(size_t)8*nobs+k]=(HT)qz;    F[(size_t)9*nobs+k]=(HT)gx[6];
  F[(size_t)10*nobs+k]=(HT)gx[7];F[(size_t)11*nobs+k]=(HT)gy[6];
  F[(size_t)12*nobs+k]=(HT)gy[7];
  for(int j=0;j<3;++j){Bo[6*o+j]=(HT)gx[9+j];Bo[6*o+3+j]=(HT)gy[9+j];}
}

template <class HT>
__global__ void MFPass1Factored9(
    const HT* __restrict__ F,const int* __restrict__ scam,
    const int* __restrict__ spt,const Scalar* __restrict__ R,
    const Scalar* __restrict__ v,int nobs,Scalar* __restrict__ tacc) {
  int k=blockIdx.x*blockDim.x+threadIdx.x;if(k>=nobs)return;
  const int c=scam[k],p=spt[k];const Scalar* Rc=R+9*c;
  const W5FactoredObs a=W5LoadFactored(F,nobs,k);
  const Scalar* vc=v+9*c;Scalar avx=0.0,avy=0.0;
#pragma unroll
  for(int i=0;i<9;++i){Scalar ax,ay;W5CameraRow(a,i,ax,ay);avx+=ax*vc[i];avy+=ay*vc[i];}
  Scalar out[3];W5PointTransposeApply(a,Rc,avx,avy,out);
#pragma unroll
  for(int j=0;j<3;++j)atomicAdd(&tacc[3*p+j],out[j]);
}

template <class HT>
__global__ void MFPass1MultiFactored9(
    const HT* __restrict__ F,const int* __restrict__ scam,
    const int* __restrict__ spt,const Scalar* __restrict__ R,
    const Scalar* __restrict__ XCU,int n_cf,int nl,int nobs,
    Scalar* __restrict__ TACC,int n_p) {
  int k=blockIdx.x*blockDim.x+threadIdx.x;if(k>=nobs)return;
  const int c=scam[k],p=spt[k];const Scalar* Rc=R+9*c;
  const W5FactoredObs a=W5LoadFactored(F,nobs,k);
  for(int l=0;l<nl;++l){const Scalar* vc=XCU+(size_t)l*n_cf+9*c;Scalar avx=0.0,avy=0.0;
#pragma unroll
    for(int i=0;i<9;++i){Scalar ax,ay;W5CameraRow(a,i,ax,ay);avx+=ax*vc[i];avy+=ay*vc[i];}
    Scalar out[3];W5PointTransposeApply(a,Rc,avx,avy,out);
#pragma unroll
    for(int j=0;j<3;++j)atomicAdd(&TACC[(size_t)l*n_p+3*p+j],out[j]);
  }
}

template <class HT>
__global__ void MFPass2Factored9(
    const HT* __restrict__ F,const int* __restrict__ cspt,
    const int* __restrict__ coff,const Scalar* __restrict__ R,
    const Scalar* __restrict__ u,const Scalar* __restrict__ Hcc,
    const Scalar* __restrict__ v,int nobs,Scalar* __restrict__ w) {
  int c=blockIdx.x,s=coff[c],e=coff[c+1];const Scalar* Rc=R+9*c;
  Scalar acc[9]={};
  for(int k=s+threadIdx.x;k<e;k+=blockDim.x){
    const int p=cspt[k];const W5FactoredObs a=W5LoadFactored(F,nobs,k);
    const Scalar* up=u+3*p;
    Scalar bux,buy;W5PointApply(a,Rc,up,bux,buy);
#pragma unroll
    for(int i=0;i<9;++i){Scalar ax,ay;W5CameraRow(a,i,ax,ay);acc[i]+=ax*bux+ay*buy;}
  }
  __shared__ Scalar sh[9][128];
#pragma unroll
  for(int i=0;i<9;++i)sh[i][threadIdx.x]=acc[i];
  __syncthreads();
  for(int st=64;st>0;st>>=1){if(threadIdx.x<st)
#pragma unroll
    for(int i=0;i<9;++i)sh[i][threadIdx.x]+=sh[i][threadIdx.x+st];__syncthreads();}
  if(threadIdx.x==0)
#pragma unroll
    for(int i=0;i<9;++i){Scalar q=0.0;
#pragma unroll
      for(int j=0;j<9;++j)q+=Hcc[81*c+9*i+j]*v[9*c+j];w[9*c+i]=q-sh[i][0];}
}

template <class HT>
__global__ void MFRhsDiagFusedFactored9(
    const HT* __restrict__ F,const int* __restrict__ cam,
    const int* __restrict__ pt,const Scalar* __restrict__ Rcam,
    const Scalar* __restrict__ Rf,const Scalar* __restrict__ ub,int nobs,
    Scalar* __restrict__ corr,Scalar* __restrict__ dk) {
  int k=blockIdx.x*blockDim.x+threadIdx.x;if(k>=nobs)return;
  const int p=pt[k],c=cam[k];const Scalar* Rc=Rcam+9*c;
  const Scalar* rp=Rf+6*p;const Scalar* up=ub+3*p;
  const bool valid=rp[0]>0.0&&rp[3]>0.0&&rp[5]>0.0;
  const W5FactoredObs a=W5LoadFactored(F,nobs,k);
  Scalar bux,buy;W5PointApply(a,Rc,up,bux,buy);
  Scalar cxx=0.0,cxy=0.0,cyy=0.0;
  if(valid){
    Scalar bx[3],by[3],ux[3],uy[3];W5PointRows(a,Rc,bx,by);
    MFVinv(rp,bx,ux);MFVinv(rp,by,uy);
    cxx=bx[0]*ux[0]+bx[1]*ux[1]+bx[2]*ux[2];
    cxy=bx[0]*uy[0]+bx[1]*uy[1]+bx[2]*uy[2];
    cyy=by[0]*uy[0]+by[1]*uy[1]+by[2]*uy[2];
  }
#pragma unroll
  for(int i=0;i<9;++i){
    Scalar ax,ay;W5CameraRow(a,i,ax,ay);
    atomicAdd(&corr[9*c+i],ax*bux+ay*buy);
    if(valid&&dk)atomicAdd(&dk[9*c+i],-(ax*ax*cxx+2.0*ax*ay*cxy+ay*ay*cyy));
  }
}

__device__ __forceinline__ void W5AtomicMaxPositive(Scalar* address,Scalar value) {
  atomicMax(reinterpret_cast<unsigned long long*>(address),__double_as_longlong(value));
}

template <class HT>
__global__ void W5FactoredAudit9(
    const int* __restrict__ ci,const int* __restrict__ pi,const Scalar* __restrict__ uv,
    const Scalar* __restrict__ R,const Scalar* __restrict__ t,const Scalar* __restrict__ X,
    const Scalar* __restrict__ f,const Scalar* __restrict__ k1,const Scalar* __restrict__ k2,
    const int* __restrict__ o2slot,const HT* __restrict__ F,int nobs,
    Scalar* __restrict__ out) {
  int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=nobs)return;
  const int c=ci[o],p=pi[o],k=o2slot[o];const Scalar* Rc=R+9*c;const Scalar* Xp=X+3*p;
  Scalar gx[12],gy[12],rx,ry;
  BalResidualGrad12(Rc[0],Rc[1],Rc[2],Rc[3],Rc[4],Rc[5],Rc[6],Rc[7],Rc[8],
      t[3*c],t[3*c+1],t[3*c+2],Xp[0],Xp[1],Xp[2],f[c],k1[c],k2[c],
      uv[2*o],uv[2*o+1],gx,gy,&rx,&ry);
  gx[8]=0.0;gy[8]=0.0;
  const W5FactoredObs a=W5LoadFactored(F,nobs,k);Scalar bx[3],by[3];W5PointRows(a,Rc,bx,by);
  Scalar d2=0.0,r2=0.0,mad=0.0,mar=0.0;
#pragma unroll
  for(int i=0;i<9;++i){Scalar ax,ay;W5CameraRow(a,i,ax,ay);
#pragma unroll
    for(int j=0;j<3;++j){
      const Scalar got=ax*bx[j]+ay*by[j];
      const Scalar ref=(Scalar)(float)(gx[i]*gx[9+j]+gy[i]*gy[9+j]);
      const Scalar d=got-ref;d2+=d*d;r2+=ref*ref;mad=fmax(mad,fabs(d));mar=fmax(mar,fabs(ref));
    }
  }
  atomicAdd(out,d2);atomicAdd(out+1,r2);W5AtomicMaxPositive(out+2,mad);W5AtomicMaxPositive(out+3,mar);
}
