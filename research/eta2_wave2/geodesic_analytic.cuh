#pragma once
__device__ inline void WGeoCross(const double* a,const double* b,double* c){
 c[0]=a[1]*b[2]-a[2]*b[1];c[1]=a[2]*b[0]-a[0]*b[2];c[2]=a[0]*b[1]-a[1]*b[0];
}
__global__ void WaveAnalyticSecond(const int* ci,const int* pi,const double* R,const double* t,
 const double* X,const double* f,const double* k1,const double* d,int nc,int no,double* out){
 int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=no)return;int c=ci[o],j=pi[o];
 const double* r=R+9*c;const double* x=X+3*j;const double* dc=d+9*c;const double* dp=d+9*nc+3*j;
 double rx[3]={},rp[3]={},y[3],v[3],a[3],wx[3],wwx[3],wp[3];
 for(int i=0;i<3;++i)for(int k=0;k<3;++k){rx[i]+=r[3*i+k]*x[k];rp[i]+=r[3*i+k]*dp[k];}
 WGeoCross(dc,rx,wx);WGeoCross(dc,wx,wwx);WGeoCross(dc,rp,wp);
 for(int i=0;i<3;++i){y[i]=rx[i]+t[3*c+i];v[i]=wx[i]+dc[3+i]+rp[i];a[i]=wwx[i]+2*wp[i];}
 double u[2],du[2],ddu[2],q=0,dq=0,ddq=0;
 for(int i=0;i<2;++i){u[i]=-y[i]/y[2];du[i]=-(v[i]+u[i]*v[2])/y[2];
  ddu[i]=-(a[i]+u[i]*a[2]+2*du[i]*v[2])/y[2];q+=u[i]*u[i];dq+=2*u[i]*du[i];ddq+=2*(du[i]*du[i]+u[i]*ddu[i]);}
 double h=1+k1[c]*q,dh=dc[7]*q+k1[c]*dq,ddh=2*dc[7]*dq+k1[c]*ddq;
 for(int i=0;i<2;++i)out[2ul*o+i]=f[c]*(ddu[i]*h+2*du[i]*dh+u[i]*ddh)+2*dc[6]*(du[i]*h+u[i]*dh);
}
