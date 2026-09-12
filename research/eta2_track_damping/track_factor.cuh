// One fixed rule: original factor algebra, tau multiplied by 0.3 for length >= 6.
__global__ void MFPointFactorTauTrack(const Scalar* __restrict__ Cdiag,
    const Scalar* __restrict__ R0f,const int* __restrict__ poff,Scalar tau,int npt,
    Scalar* __restrict__ Rf,int* __restrict__ ok){
  int p=blockIdx.x*blockDim.x+threadIdx.x; if(p>=npt)return;
  if(poff[p+1]-poff[p]>=6)tau*=0.3;
  Scalar cd[3]={Cdiag[3*p],Cdiag[3*p+1],Cdiag[3*p+2]};
  Scalar tr=cd[0]+cd[1]+cd[2], fl=tau*tr/3.0; if(!(fl>0.0)) fl=1e-32;
  Scalar Rp[6]; for(int i=0;i<6;++i) Rp[i]=R0f[6*p+i];
  for(int i=0;i<3;++i){ Scalar q=tau*cd[i]; if(!(q>1e-3*fl)) q=1e-3*fl;
    Scalar v[3]={0,0,0}; v[i]=sqrt(q); MFGivens(Rp,v); }
  ok[p]=((Rp[0]>0.0)&&(Rp[3]>0.0)&&(Rp[5]>0.0))?1:0;
  for(int i=0;i<6;++i) Rf[6*p+i]=Rp[i];
}
