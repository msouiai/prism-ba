#pragma once

// Wave-5 B5: a Schur operator derived from one rounded Jacobian.
//
// The frozen Eta2 path stores W = Jc^T Jp in FP32 while accumulating Hcc,
// Cdiag, bc and bp from the original FP64 rows.  The independently rounded
// ingredients need not be the Gram blocks of any one Jacobian.  Here every
// observation stores the two 12-entry Jacobian rows in FP32 and all normal
// equation ingredients are accumulated from those stored values.
//
// The matrix-free product is evaluated in projected-residual form
//
//   y = Jc v,  u = (Jp^T Jp + Qp)^-1 Jp^T y,
//   Sv = Jc^T (y - Jp u) + Qin v,
//
// avoiding the global Hcc*v - W*u subtraction.  With exact point solves its
// curvature is the explicitly nonnegative sum
//
//   ||y-Jp*u||^2 + u^T Qp u + v^T Qin v.

constexpr int W5_SQRT_VALUES = 24;  // two rows x (9 camera + 3 point)

template <class HT>
__device__ __forceinline__ Scalar W5SqrtJ(
    const HT* __restrict__ J, int nobs, int k, int row, int col) {
  return (Scalar)J[(size_t)(12*row+col)*nobs+k];
}

__device__ __forceinline__ void W5SqrtGivens(Scalar* Rp, Scalar* v) {
  const int ix[3][3]={{0,1,2},{-1,3,4},{-1,-1,5}};
  for(int j=0;j<3;++j){
    const Scalar vj=v[j]; if(vj==0.0) continue;
    const Scalar rjj=Rp[ix[j][j]], rr=hypot(rjj,vj); if(rr==0.0) continue;
    const Scalar cs=rjj/rr, sn=vj/rr; Rp[ix[j][j]]=rr;
    for(int q=j+1;q<3;++q){const Scalar a=Rp[ix[j][q]],b=v[q];
      Rp[ix[j][q]]=cs*a+sn*b;v[q]=-sn*a+cs*b;}
    v[j]=0.0;
  }
}

template <class HT>
__global__ void MFAssembleSqrt9(
    const int* __restrict__ ci,const int* __restrict__ pi,
    const Scalar* __restrict__ uv,const Scalar* __restrict__ R,
    const Scalar* __restrict__ t,const Scalar* __restrict__ X,
    const Scalar* __restrict__ f,const Scalar* __restrict__ k1,
    const Scalar* __restrict__ k2,const int* __restrict__ o2c,int nobs,
    Scalar* __restrict__ Hcc,Scalar* __restrict__ Cdiag,
    HT* __restrict__ J,Scalar* __restrict__ bc,Scalar* __restrict__ bp,
    Scalar k2mask=0.0,Scalar* __restrict__ r2acc=nullptr,
    Scalar* __restrict__ obscnt=nullptr,int rk=0,Scalar rk_a2=0.0) {
  const int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=nobs)return;
  const int c=ci[o],p=pi[o],slot=o2c[o];
  const Scalar* Rc=R+9*c;const Scalar* Xp=X+3*p;
  const Scalar Px=Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2]+t[3*c];
  const Scalar Py=Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2]+t[3*c+1];
  const Scalar Pz=Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2]+t[3*c+2];
  const Scalar xq=-Px/Pz,yq=-Py/Pz,r2=xq*xq+yq*yq;
  const Scalar dist=1.0+k1[c]*r2+k2[c]*r2*r2;
  Scalar rx=f[c]*dist*xq-uv[2*o],ry=f[c]*dist*yq-uv[2*o+1];
  Scalar gx[12],gy[12],r0x,r0y;
  BalResidualGrad12(Rc[0],Rc[1],Rc[2],Rc[3],Rc[4],Rc[5],Rc[6],Rc[7],Rc[8],
      t[3*c],t[3*c+1],t[3*c+2],Xp[0],Xp[1],Xp[2],f[c],k1[c],k2[c],
      uv[2*o],uv[2*o+1],gx,gy,&r0x,&r0y);
  gx[8]*=k2mask;gy[8]*=k2mask;
  if(r2acc){atomicAdd(&r2acc[c],r2);atomicAdd(&obscnt[c],(Scalar)1.0);}
  if(rk){const Scalar sw=sqrt(OcaRobustW(rk,rk_a2,rx*rx+ry*ry));
    rx*=sw;ry*=sw;for(int q=0;q<12;++q){gx[q]*=sw;gy[q]*=sw;}}

  // Round once, store once, and derive every block from these same values.
  Scalar jx[12],jy[12];
  for(int q=0;q<12;++q){
    const HT ax=(HT)gx[q],ay=(HT)gy[q];
    J[(size_t)q*nobs+slot]=ax;J[(size_t)(12+q)*nobs+slot]=ay;
    jx[q]=(Scalar)ax;jy[q]=(Scalar)ay;
  }
  for(int i=0;i<9;++i){
    atomicAdd(&bc[9*c+i],rx*jx[i]+ry*jy[i]);
    for(int q=0;q<9;++q)
      atomicAdd(&Hcc[81*c+9*i+q],jx[i]*jx[q]+jy[i]*jy[q]);
  }
  for(int i=0;i<3;++i){
    atomicAdd(&bp[3*p+i],rx*jx[9+i]+ry*jy[9+i]);
    atomicAdd(&Cdiag[3*p+i],jx[9+i]*jx[9+i]+jy[9+i]*jy[9+i]);
  }
}

template <class HT>
__global__ void MFPointFactorObsSqrt9(
    const HT* __restrict__ J,const int* __restrict__ o2c,
    const int* __restrict__ poff,const int* __restrict__ plist,
    int npt,int nobs,Scalar* __restrict__ out,int* __restrict__ fallback) {
  const int p=blockIdx.x*blockDim.x+threadIdx.x;if(p>=npt)return;
  Scalar a[6]={};const int begin=poff[p],end=poff[p+1];
  for(int q=begin;q<end;++q){const int k=o2c[plist[q]];
    for(int row=0;row<2;++row){
      const Scalar x=W5SqrtJ(J,nobs,k,row,9),
                   y=W5SqrtJ(J,nobs,k,row,10),
                   z=W5SqrtJ(J,nobs,k,row,11);
      a[0]+=x*x;a[1]+=x*y;a[2]+=x*z;a[3]+=y*y;a[4]+=y*z;a[5]+=z*z;
    }
  }
  Scalar r[6];
  r[0]=sqrt(a[0]);r[1]=a[1]/r[0];r[2]=a[2]/r[0];
  r[3]=sqrt(a[3]-r[1]*r[1]);r[4]=(a[4]-r[1]*r[2])/r[3];
  r[5]=sqrt(a[5]-r[2]*r[2]-r[4]*r[4]);
  Scalar inv[6];inv[0]=1/r[0];inv[3]=1/r[3];inv[5]=1/r[5];
  inv[1]=-r[1]*inv[0]*inv[3];inv[4]=-r[4]*inv[3]*inv[5];
  inv[2]=-(r[1]*inv[4]+r[2]*inv[5])*inv[0];
  Scalar nr=0,ni=0;for(int q=0;q<6;++q){nr+=r[q]*r[q];ni+=inv[q]*inv[q];}
  const Scalar rec[6]={r[0]*r[0],r[0]*r[1],r[0]*r[2],
    r[1]*r[1]+r[3]*r[3],r[1]*r[2]+r[3]*r[4],
    r[2]*r[2]+r[4]*r[4]+r[5]*r[5]};
  Scalar err=0,scale=0;for(int q=0;q<6;++q){err=fmax(err,fabs(rec[q]-a[q]));scale=fmax(scale,fabs(a[q]));}
  const Scalar budget=64*2.2204460492503131e-16*fmax((Scalar)1.0,(Scalar)(2*(end-begin)));
  const bool good=isfinite(nr*ni)&&r[0]>0&&r[3]>0&&r[5]>0&&
                  budget*nr*ni<1e-8&&err<=budget*scale;
  if(!good){
    for(int q=0;q<6;++q)r[q]=0;
    for(int q=begin;q<end;++q){const int k=o2c[plist[q]];
      Scalar x[3]={W5SqrtJ(J,nobs,k,0,9),W5SqrtJ(J,nobs,k,0,10),W5SqrtJ(J,nobs,k,0,11)};
      Scalar y[3]={W5SqrtJ(J,nobs,k,1,9),W5SqrtJ(J,nobs,k,1,10),W5SqrtJ(J,nobs,k,1,11)};
      W5SqrtGivens(r,x);W5SqrtGivens(r,y);
    }
  }
  for(int q=0;q<6;++q)out[6ul*p+q]=r[q];if(fallback)fallback[p]=!good;
}

template <class HT>
__global__ void MFSqrtPass1(
    const HT* __restrict__ J,const int* __restrict__ cam,
    const int* __restrict__ pt,const Scalar* __restrict__ v,
    int nobs,Scalar* __restrict__ tacc) {
  const int k=blockIdx.x*blockDim.x+threadIdx.x;if(k>=nobs)return;
  const int c=cam[k],p=pt[k];const Scalar* vc=v+9*c;
  Scalar y[2]={0,0};
  for(int i=0;i<9;++i){y[0]+=W5SqrtJ(J,nobs,k,0,i)*vc[i];y[1]+=W5SqrtJ(J,nobs,k,1,i)*vc[i];}
  for(int q=0;q<3;++q)
    atomicAdd(&tacc[3*p+q],W5SqrtJ(J,nobs,k,0,9+q)*y[0]+W5SqrtJ(J,nobs,k,1,9+q)*y[1]);
}

template <class HT>
__global__ void MFSqrtPass1Multi(
    const HT* __restrict__ J,const int* __restrict__ cam,
    const int* __restrict__ pt,const Scalar* __restrict__ X,
    int nc,int nl,int nobs,Scalar* __restrict__ T,int np) {
  const int k=blockIdx.x*blockDim.x+threadIdx.x;if(k>=nobs)return;
  const int c=cam[k],p=pt[k];
  for(int l=0;l<nl;++l){const Scalar* vc=X+(size_t)l*nc+9*c;Scalar y[2]={0,0};
    for(int i=0;i<9;++i){y[0]+=W5SqrtJ(J,nobs,k,0,i)*vc[i];y[1]+=W5SqrtJ(J,nobs,k,1,i)*vc[i];}
    for(int q=0;q<3;++q)atomicAdd(&T[(size_t)l*np+3*p+q],
      W5SqrtJ(J,nobs,k,0,9+q)*y[0]+W5SqrtJ(J,nobs,k,1,9+q)*y[1]);
  }
}

template <class HT>
__global__ void MFSqrtRhsDiag9(
    const HT* __restrict__ J,const int* __restrict__ cam,
    const int* __restrict__ pt,const Scalar* __restrict__ Rf,
    const Scalar* __restrict__ ub,int nobs,Scalar* __restrict__ corr,
    Scalar* __restrict__ dk) {
  const int k=blockIdx.x*blockDim.x+threadIdx.x;if(k>=nobs)return;
  const int c=cam[k],p=pt[k];const Scalar* u=ub+3*p;const Scalar* R=Rf+6*p;
  Scalar ju[2]={0,0};
  for(int q=0;q<3;++q){ju[0]+=W5SqrtJ(J,nobs,k,0,9+q)*u[q];ju[1]+=W5SqrtJ(J,nobs,k,1,9+q)*u[q];}
  const bool valid=R[0]>0&&R[3]>0&&R[5]>0;
  for(int i=0;i<9;++i){
    const Scalar ax=W5SqrtJ(J,nobs,k,0,i),ay=W5SqrtJ(J,nobs,k,1,i);
    atomicAdd(&corr[9*c+i],ax*ju[0]+ay*ju[1]);
    if(valid&&dk){
      Scalar g[3];for(int q=0;q<3;++q)g[q]=W5SqrtJ(J,nobs,k,0,9+q)*ax+W5SqrtJ(J,nobs,k,1,9+q)*ay;
      const Scalar y0=g[0]/R[0],y1=(g[1]-R[1]*y0)/R[3],
                   y2=(g[2]-R[2]*y0-R[4]*y1)/R[5];
      atomicAdd(&dk[9*c+i],-(y0*y0+y1*y1+y2*y2));
    }
  }
}

template <class HT>
__global__ void MFSqrtPass2(
    const HT* __restrict__ J,const int* __restrict__ cspt,
    const int* __restrict__ coff,const Scalar* __restrict__ u,
    const Scalar* __restrict__ v,int nobs,const Scalar* __restrict__ f,
    const Scalar* __restrict__ r2acc,const Scalar* __restrict__ obscnt,
    Scalar intr_w,Scalar k2mask,Scalar* __restrict__ out) {
  const int c=blockIdx.x,s=coff[c],e=coff[c+1];const Scalar* vc=v+9*c;
  Scalar acc[9]={};
  for(int k=s+threadIdx.x;k<e;k+=blockDim.x){
    const int p=cspt[k];const Scalar* up=u+3*p;Scalar y[2]={0,0},ju[2]={0,0};
    for(int i=0;i<9;++i){y[0]+=W5SqrtJ(J,nobs,k,0,i)*vc[i];y[1]+=W5SqrtJ(J,nobs,k,1,i)*vc[i];}
    for(int q=0;q<3;++q){ju[0]+=W5SqrtJ(J,nobs,k,0,9+q)*up[q];ju[1]+=W5SqrtJ(J,nobs,k,1,9+q)*up[q];}
    const Scalar z0=y[0]-ju[0],z1=y[1]-ju[1];
    for(int i=0;i<9;++i)acc[i]+=W5SqrtJ(J,nobs,k,0,i)*z0+W5SqrtJ(J,nobs,k,1,i)*z1;
  }
  __shared__ Scalar sh[9][128];for(int i=0;i<9;++i)sh[i][threadIdx.x]=acc[i];__syncthreads();
  for(int st=64;st>0;st>>=1){if(threadIdx.x<st)for(int i=0;i<9;++i)sh[i][threadIdx.x]+=sh[i][threadIdx.x+st];__syncthreads();}
  if(threadIdx.x==0){
    Scalar reg[3]={0,0,0};
    if(r2acc&&obscnt&&obscnt[c]>0){
      Scalar rb=r2acc[c]/obscnt[c];if(!(rb>1e-12))rb=1e-12;
      const Scalar sf=0.5*fabs(f[c])+1e-3;
      reg[0]=intr_w/(sf*sf);reg[1]=intr_w*rb*rb;
      if(k2mask>0)reg[2]=intr_w*rb*rb*rb*rb;
    }
    for(int i=0;i<9;++i)out[9*c+i]=sh[i][0]+(i>=6?reg[i-6]*vc[i]:0.0);
  }
}

// Literal normal-equation action from the same stored J.  Audit only: it
// deliberately performs Hcc*v - Jc^T Jp*u so the projected form can be
// checked against the conventional Schur algebra.
template <class HT>
__global__ void MFSqrtReferencePass2(
    const HT* __restrict__ J,const int* __restrict__ cspt,
    const int* __restrict__ coff,const Scalar* __restrict__ u,
    const Scalar* __restrict__ Hcc,const Scalar* __restrict__ v,
    int nobs,Scalar* __restrict__ out) {
  const int c=blockIdx.x,s=coff[c],e=coff[c+1];Scalar cross[9]={};
  for(int k=s+threadIdx.x;k<e;k+=blockDim.x){const Scalar* up=u+3*cspt[k];Scalar ju[2]={0,0};
    for(int q=0;q<3;++q){ju[0]+=W5SqrtJ(J,nobs,k,0,9+q)*up[q];ju[1]+=W5SqrtJ(J,nobs,k,1,9+q)*up[q];}
    for(int i=0;i<9;++i)cross[i]+=W5SqrtJ(J,nobs,k,0,i)*ju[0]+W5SqrtJ(J,nobs,k,1,i)*ju[1];
  }
  __shared__ Scalar sh[9][128];for(int i=0;i<9;++i)sh[i][threadIdx.x]=cross[i];__syncthreads();
  for(int st=64;st>0;st>>=1){if(threadIdx.x<st)for(int i=0;i<9;++i)sh[i][threadIdx.x]+=sh[i][threadIdx.x+st];__syncthreads();}
  if(threadIdx.x==0)for(int i=0;i<9;++i){Scalar q=0;for(int j=0;j<9;++j)q+=Hcc[81*c+9*i+j]*v[9*c+j];out[9*c+i]=q-sh[i][0];}
}

template <class HT>
__global__ void MFSqrtSosObs(const HT* __restrict__ J,const int* __restrict__ cam,
    const int* __restrict__ pt,const Scalar* __restrict__ v,
    const Scalar* __restrict__ u,int nobs,Scalar* __restrict__ sums) {
  const int k=blockIdx.x*blockDim.x+threadIdx.x;if(k>=nobs)return;
  const Scalar* vc=v+9*cam[k];const Scalar* up=u+3*pt[k];Scalar y[2]={0,0},ju[2]={0,0};
  for(int i=0;i<9;++i){y[0]+=W5SqrtJ(J,nobs,k,0,i)*vc[i];y[1]+=W5SqrtJ(J,nobs,k,1,i)*vc[i];}
  for(int q=0;q<3;++q){ju[0]+=W5SqrtJ(J,nobs,k,0,9+q)*up[q];ju[1]+=W5SqrtJ(J,nobs,k,1,9+q)*up[q];}
  const Scalar z0=y[0]-ju[0],z1=y[1]-ju[1];atomicAdd(&sums[0],z0*z0+z1*z1);
}

__global__ void MFSqrtSosPoint(const Scalar* __restrict__ Cdiag,
    const Scalar* __restrict__ u,Scalar tau,int npt,Scalar* __restrict__ sums) {
  const int p=blockIdx.x*blockDim.x+threadIdx.x;if(p>=npt)return;
  const Scalar tr=Cdiag[3*p]+Cdiag[3*p+1]+Cdiag[3*p+2];
  Scalar fl=tau*tr/3.0;if(!(fl>0))fl=1e-32;Scalar q=0;
  for(int i=0;i<3;++i){Scalar d=tau*Cdiag[3*p+i];if(!(d>1e-3*fl))d=1e-3*fl;q+=d*u[3*p+i]*u[3*p+i];}
  atomicAdd(&sums[1],q);
}

__global__ void MFSqrtSosIntr(const Scalar* __restrict__ v,
    const Scalar* __restrict__ f,const Scalar* __restrict__ r2acc,
    const Scalar* __restrict__ obscnt,int ncam,Scalar intr_w,
    Scalar k2mask,Scalar* __restrict__ sums) {
  const int c=blockIdx.x*blockDim.x+threadIdx.x;if(c>=ncam||!r2acc||!obscnt||!(obscnt[c]>0))return;
  Scalar rb=r2acc[c]/obscnt[c];if(!(rb>1e-12))rb=1e-12;const Scalar sf=.5*fabs(f[c])+1e-3;
  Scalar q=intr_w/(sf*sf)*v[9*c+6]*v[9*c+6]+intr_w*rb*rb*v[9*c+7]*v[9*c+7];
  if(k2mask>0)q+=intr_w*rb*rb*rb*rb*v[9*c+8]*v[9*c+8];atomicAdd(&sums[2],q);
}

__global__ void W5SqrtDifference(const Scalar* __restrict__ a,
    const Scalar* __restrict__ b,Scalar* __restrict__ d,int n) {
  const int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)d[i]=a[i]-b[i];
}
