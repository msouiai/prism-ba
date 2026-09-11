#pragma once
// Independent point candidates, preserving the champion's original proposal.
__device__ void PrismWorldRay(const double* R,const double* t,const double* x,double* ray){
  // X-C = X + R^T t. No gauge-dependent absolute thresholds.
  double n=0;
  for(int i=0;i<3;++i){ray[i]=x[i]+R[i]*t[0]+R[3+i]*t[1]+R[6+i]*t[2];n+=ray[i]*ray[i];}
  n=sqrt(n);for(int i=0;i<3;++i)ray[i]/=n;
}
__device__ bool PrismLowParallax(const int* offsets,const int* order,const int* ci,
  const double* R,const double* t,const double* X,int point,int lane){
  int first=offsets[point],end=offsets[point+1];if(end-first<2)return false;
  int c0=ci[order[first]];double a[3];PrismWorldRay(R+9*c0,t+3*c0,X+3*point,a);
  double worst=1.;
  for(int j=first+lane;j<end;j+=32){int c=ci[order[j]];double b[3];PrismWorldRay(R+9*c,t+3*c,X+3*point,b);
    double cosine=a[0]*b[0]+a[1]*b[1]+a[2]*b[2];worst=fmin(worst,isfinite(cosine)?cosine:-1.);}
  for(int k=16;k;k>>=1)worst=fmin(worst,__shfl_down_sync(0xffffffff,worst,k));
  return __shfl_sync(0xffffffff,worst,0)>=0.9961946980917455; // cos(5 degrees)
}
#include "follow_refine.cuh"
__device__ bool PrismFollowSolve(double* a,double* dx){
  double L[9]={};bool ok=true;
  for(int i=0;i<3;++i)for(int j=0;j<=i;++j){double v=a[3*i+j];for(int k=0;k<j;++k)v-=L[3*i+k]*L[3*j+k];
    if(i==j){ok=ok&&isfinite(v)&&v>0;L[3*i+j]=sqrt(fmax(v,1e-300));}else L[3*i+j]=v/L[3*j+j];}
  for(int i=0;i<3;++i){double v=-a[9+i];for(int j=0;j<i;++j)v-=L[3*i+j]*dx[j];dx[i]=v/L[3*i+i];}
  for(int i=2;i>=0;--i){double v=dx[i];for(int j=i+1;j<3;++j)v-=L[3*j+i]*dx[j];dx[i]=v/L[3*i+i];}
  for(int i=0;i<3;++i)ok=ok&&isfinite(dx[i]);return ok;
}
__global__ void MFFollowVirtual(const int* offsets,const int* order,const int* ci,
 const double* R,const double* t,const double* X,const double* f,const double* k1,const double* k2,
 const double* Rt,const double* tt,const double* Xt,const double* diag,double tau,int np,int nc,
 double* step,unsigned long long* changed){
  int lane=threadIdx.x%32,p=(blockIdx.x*blockDim.x+threadIdx.x)/32;if(p>=np)return;
  double a[12]={};bool valid=true;
  for(int j=offsets[p]+lane;j<offsets[p+1];j+=32){
    int c=ci[order[j]];const double* r=R+9*c;const double* rt=Rt+9*c;const double* dc=step+9*c;const double* dp=step+9*nc+3*p;
    double rx[3]={},q[3],dq[3],qt[3];
    for(int i=0;i<3;++i)for(int h=0;h<3;++h)rx[i]+=r[3*i+h]*X[3*p+h];
    for(int i=0;i<3;++i){q[i]=rx[i]+t[3*c+i];dq[i]=dc[3+i]+dc[(i+1)%3]*rx[(i+2)%3]-dc[(i+2)%3]*rx[(i+1)%3];
      qt[i]=tt[3*c+i];for(int h=0;h<3;++h){dq[i]+=r[3*i+h]*dp[h];qt[i]+=rt[3*i+h]*Xt[3*p+h];}}
    double u=-q[0]/q[2],v=-q[1]/q[2];
    double uh=u-(dq[0]+u*dq[2])/q[2],vh=v-(dq[1]+v*dq[2])/q[2];
    double rr=u*u+v*v,d=1+k1[c]*rr+k2[c]*rr*rr,h=k1[c]+2*k2[c]*rr;
    double W[4]={f[c]*(d+2*h*u*u)/q[2],f[c]*2*h*u*v/q[2],f[c]*2*h*u*v/q[2],f[c]*(d+2*h*v*v)/q[2]};
    double B[6],A[6],b[2]={qt[0]+uh*qt[2],qt[1]+vh*qt[2]},e[2];
    for(int k=0;k<3;++k){B[k]=rt[k]+uh*rt[6+k];B[3+k]=rt[3+k]+vh*rt[6+k];
      A[k]=W[0]*B[k]+W[1]*B[3+k];A[3+k]=W[2]*B[k]+W[3]*B[3+k];}
    e[0]=W[0]*b[0]+W[1]*b[1];e[1]=W[2]*b[0]+W[3]*b[1];
    valid=valid&&isfinite(e[0])&&isfinite(e[1]);
    for(int i=0;i<3;++i){a[9+i]+=A[i]*e[0]+A[3+i]*e[1];for(int k=0;k<3;++k)a[3*i+k]+=A[i]*A[k]+A[3+i]*A[3+k];}
  }
  for(int k=16;k;k>>=1)for(int h=0;h<12;++h)a[h]+=__shfl_down_sync(0xffffffff,a[h],k);
  bool all=__all_sync(0xffffffff,valid);
  if(lane==0){
    double tr=diag[3*p]+diag[3*p+1]+diag[3*p+2],fl=tau*tr/3.;if(!(fl>0))fl=1e-32;
    for(int i=0;i<3;++i){double z=tau*diag[3*p+i];if(!(z>1e-3*fl))z=1e-3*fl;a[3*i+i]+=z;}
    double dx[3]={};bool ok=PrismFollowSolve(a,dx);
    if(all&&ok){for(int i=0;i<3;++i)step[9*nc+3*p+i]+=dx[i];atomicAdd(changed,1ULL);}
  }
}
struct PrismPointOverlay {
  unsigned long long* changed=nullptr;
  PrismPointOverlay(){CUDA_CHECK(cudaMalloc(&changed,sizeof(*changed)));}
  ~PrismPointOverlay(){cudaFree(changed);}
  unsigned long long Choose(const DeviceProblem& p,const DeviceState& old,const DeviceState& full,
    const double* diag,double tau,double* step,int mode){
    CUDA_CHECK(cudaMemset(changed,0,sizeof(*changed)));
    if(mode==3)MFFollowVirtual<<<(p.npt+7)/8,256>>>(p.point_obs_offsets,p.point_obs_list,p.cam_idx,
      old.R,old.t,old.X,INTR_F(p,old),INTR_K1(p,old),INTR_K2(p,old),full.R,full.t,full.X,diag,tau,p.npt,p.ncam,step,changed);
    else MFFollowPointRefine<<<(p.npt+7)/8,256>>>(p.point_obs_offsets,p.point_obs_list,p.cam_idx,p.uv,
      full.R,full.t,full.X,INTR_F(p,full),INTR_K1(p,full),INTR_K2(p,full),p.npt,p.ncam,step,changed,mode==2);
    unsigned long long n=0;CUDA_CHECK(cudaMemcpy(&n,changed,sizeof(n),cudaMemcpyDeviceToHost));return n;
  }
};
