#pragma once

// B6v4: exact-order fusion of point factor construction and the first
// V_tau^-1 b_p solve.  Device doubles have no extended-register precision, so
// retaining Rp locally removes a global round trip without removing a
// floating-point rounding point.
__global__ void W5PointFactorTauRhs(const Scalar* __restrict__ Cdiag,
    const Scalar* __restrict__ R0f,const Scalar* __restrict__ bp,Scalar tau,
    int npt,Scalar* __restrict__ Rf,int* __restrict__ ok,
    Scalar* __restrict__ uu){
  int p=blockIdx.x*blockDim.x+threadIdx.x; if(p>=npt)return;
  Scalar cd[3]={Cdiag[3*p],Cdiag[3*p+1],Cdiag[3*p+2]};
  Scalar tr=cd[0]+cd[1]+cd[2], fl=tau*tr/3.0; if(!(fl>0.0)) fl=1e-32;
  Scalar Rp[6]; for(int i=0;i<6;++i) Rp[i]=R0f[6*p+i];
  for(int i=0;i<3;++i){
    Scalar q=tau*cd[i]; if(!(q>1e-3*fl)) q=1e-3*fl;
    Scalar v[3]={0,0,0}; v[i]=sqrt(q); MFGivens(Rp,v);
  }
  const bool valid=(Rp[0]>0.0)&&(Rp[3]>0.0)&&(Rp[5]>0.0);
  ok[p]=valid?1:0;
  for(int i=0;i<6;++i) Rf[6*p+i]=Rp[i];
  if(!valid){ uu[3*p]=uu[3*p+1]=uu[3*p+2]=0.0; return; }
  Scalar rhs[3]={bp[3*p],bp[3*p+1],bp[3*p+2]},u[3];
  MFVinv(Rp,rhs,u);
  uu[3*p]=u[0];uu[3*p+1]=u[1];uu[3*p+2]=u[2];
}

template <int CD>
__global__ void W5MakeEquilHcc(const Scalar* __restrict__ Hcc,int ncam,
                               Scalar* __restrict__ E){
  int q=blockIdx.x*blockDim.x+threadIdx.x; if(q>=CD*ncam)return;
  int c=q/CD,i=q-CD*c;
  Scalar d=Hcc[(size_t)CD*CD*c+CD*i+i];
  E[q]=(d>0.0)?1.0/sqrt(d):1.0;
}

__global__ void W5ReducedRhsEquil(const Scalar* __restrict__ bc,
    const Scalar* __restrict__ corr,const Scalar* __restrict__ E,int n,
    Scalar* __restrict__ bprime){
  int i=blockIdx.x*blockDim.x+threadIdx.x; if(i<n)
    bprime[i]=(bc[i]-corr[i])*E[i];
}
