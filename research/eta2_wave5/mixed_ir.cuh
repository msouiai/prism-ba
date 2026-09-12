#pragma once

// Store the same FP32 Jacobian representation as B5, without changing the
// frozen high-precision normal-equation assembly.  This is the approximate
// correction operator only.
template <class HT>
__global__ void W5StoreJacobian9(
    const int* __restrict__ ci,const int* __restrict__ pi,
    const Scalar* __restrict__ uv,const Scalar* __restrict__ R,
    const Scalar* __restrict__ t,const Scalar* __restrict__ X,
    const Scalar* __restrict__ f,const Scalar* __restrict__ k1,
    const Scalar* __restrict__ k2,const int* __restrict__ o2c,int nobs,
    HT* __restrict__ J,Scalar k2mask,int rk,Scalar rk_a2) {
  const int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=nobs)return;
  const int c=ci[o],p=pi[o],slot=o2c[o];const Scalar* Rc=R+9*c;const Scalar* Xp=X+3*p;
  Scalar gx[12],gy[12],rx,ry;
  BalResidualGrad12(Rc[0],Rc[1],Rc[2],Rc[3],Rc[4],Rc[5],Rc[6],Rc[7],Rc[8],
      t[3*c],t[3*c+1],t[3*c+2],Xp[0],Xp[1],Xp[2],f[c],k1[c],k2[c],
      uv[2*o],uv[2*o+1],gx,gy,&rx,&ry);
  gx[8]*=k2mask;gy[8]*=k2mask;
  if(rk){const Scalar sw=sqrt(OcaRobustW(rk,rk_a2,rx*rx+ry*ry));
    for(int q=0;q<12;++q){gx[q]*=sw;gy[q]*=sw;}}
  for(int q=0;q<12;++q){J[(size_t)q*nobs+slot]=(HT)gx[q];J[(size_t)(12+q)*nobs+slot]=(HT)gy[q];}
}

__global__ void W5CastD2F(const Scalar* __restrict__ x,float* __restrict__ y,int n){
  const int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[i]=(float)x[i];
}
__global__ void W5CastF2D(const float* __restrict__ x,Scalar* __restrict__ y,int n){
  const int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[i]=(Scalar)x[i];
}

__global__ void W5BuildPcgF(const Scalar* __restrict__ H,const Scalar* __restrict__ E,
    Scalar shift,int ncam,float* __restrict__ B) {
  const int c=blockIdx.x*blockDim.x+threadIdx.x;if(c>=ncam)return;
  float A[81],L[81];float mx=0;
  for(int i=0;i<9;++i)for(int j=0;j<9;++j){
    float q=(float)(H[81ul*c+9*i+j]*E[9*c+i]*E[9*c+j]+(i==j?shift:0));
    A[9*i+j]=q;L[9*i+j]=0;if(i==j)mx=fmaxf(mx,fabsf(q));
  }
  const float floor=fmaxf(mx*1e-10f,1e-30f);for(int i=0;i<9;++i)if(!(A[9*i+i]>floor))A[9*i+i]=floor;
  bool good=true;
  for(int i=0;i<9&&good;++i)for(int j=0;j<=i;++j){
    float s=.5f*(A[9*i+j]+A[9*j+i]);for(int k=0;k<j;++k)s-=L[9*i+k]*L[9*j+k];
    if(i==j){if(!(s>0)){good=false;break;}L[9*i+j]=sqrtf(s);}else L[9*i+j]=s/L[9*j+j];
  }
  if(!good){for(int q=0;q<81;++q)L[q]=0;for(int i=0;i<9;++i)L[9*i+i]=sqrtf(fmaxf(A[9*i+i],floor));}
  for(int q=0;q<81;++q)B[81ul*c+q]=L[q];
}

__global__ void W5ApplyPcgF(const float* __restrict__ B,const float* __restrict__ r,
    int ncam,float* __restrict__ z) {
  const int c=blockIdx.x*blockDim.x+threadIdx.x;if(c>=ncam)return;
  const float* L=B+81ul*c;float y[9],x[9];
  for(int i=0;i<9;++i){float s=r[9*c+i];for(int k=0;k<i;++k)s-=L[9*i+k]*y[k];y[i]=s/L[9*i+i];}
  for(int i=8;i>=0;--i){float s=y[i];for(int k=i+1;k<9;++k)s-=L[9*k+i]*x[k];x[i]=s/L[9*i+i];}
  for(int i=0;i<9;++i)z[9*c+i]=x[i];
}

__global__ void W5ScaleInputF(const float* __restrict__ x,const Scalar* __restrict__ E,
    int n,float* __restrict__ y){const int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[i]=(float)((Scalar)x[i]*E[i]);}
__global__ void W5ScaleShiftF(float* __restrict__ y,const Scalar* __restrict__ E,
    const float* __restrict__ x,float shift,int n){const int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[i]=(float)((Scalar)y[i]*E[i])+shift*x[i];}

__global__ void W5SqrtPass1F(const float* __restrict__ J,const int* __restrict__ cam,
    const int* __restrict__ pt,const float* __restrict__ v,int nobs,float* __restrict__ tacc){
  const int k=blockIdx.x*blockDim.x+threadIdx.x;if(k>=nobs)return;const int c=cam[k],p=pt[k];
  const float* vc=v+9*c;float y0=0,y1=0;for(int i=0;i<9;++i){y0+=J[(size_t)i*nobs+k]*vc[i];y1+=J[(size_t)(12+i)*nobs+k]*vc[i];}
  for(int q=0;q<3;++q)atomicAdd(&tacc[3*p+q],J[(size_t)(9+q)*nobs+k]*y0+J[(size_t)(21+q)*nobs+k]*y1);
}

__global__ void W5VinvF(const float* __restrict__ R,const float* __restrict__ b,
    int npt,float* __restrict__ u){
  const int p=blockIdx.x*blockDim.x+threadIdx.x;if(p>=npt)return;const float* A=R+6*p;
  if(!(A[0]>0&&A[3]>0&&A[5]>0)){u[3*p]=u[3*p+1]=u[3*p+2]=0;return;}
  const float y0=b[3*p]/A[0],y1=(b[3*p+1]-A[1]*y0)/A[3],
              y2=(b[3*p+2]-A[2]*y0-A[4]*y1)/A[5];
  u[3*p+2]=y2/A[5];u[3*p+1]=(y1-A[4]*u[3*p+2])/A[3];
  u[3*p]=(y0-A[1]*u[3*p+1]-A[2]*u[3*p+2])/A[0];
}

__global__ void W5SqrtPass2F(const float* __restrict__ J,const int* __restrict__ cspt,
    const int* __restrict__ coff,const float* __restrict__ u,const float* __restrict__ v,
    int nobs,const Scalar* __restrict__ f,const Scalar* __restrict__ r2acc,
    const Scalar* __restrict__ obscnt,Scalar intr_w,Scalar k2mask,float* __restrict__ out){
  const int c=blockIdx.x,s=coff[c],e=coff[c+1];const float* vc=v+9*c;float acc[9]={};
  for(int k=s+threadIdx.x;k<e;k+=blockDim.x){const float* up=u+3*cspt[k];float y0=0,y1=0,ju0=0,ju1=0;
    for(int i=0;i<9;++i){y0+=J[(size_t)i*nobs+k]*vc[i];y1+=J[(size_t)(12+i)*nobs+k]*vc[i];}
    for(int q=0;q<3;++q){ju0+=J[(size_t)(9+q)*nobs+k]*up[q];ju1+=J[(size_t)(21+q)*nobs+k]*up[q];}
    const float z0=y0-ju0,z1=y1-ju1;for(int i=0;i<9;++i)acc[i]+=J[(size_t)i*nobs+k]*z0+J[(size_t)(12+i)*nobs+k]*z1;
  }
  __shared__ float sh[9][128];for(int i=0;i<9;++i)sh[i][threadIdx.x]=acc[i];__syncthreads();
  for(int st=64;st>0;st>>=1){if(threadIdx.x<st)for(int i=0;i<9;++i)sh[i][threadIdx.x]+=sh[i][threadIdx.x+st];__syncthreads();}
  if(threadIdx.x==0){float reg[3]={0,0,0};if(r2acc&&obscnt&&obscnt[c]>0){Scalar rb=r2acc[c]/obscnt[c];if(!(rb>1e-12))rb=1e-12;
      const Scalar sf=.5*fabs(f[c])+1e-3;reg[0]=(float)(intr_w/(sf*sf));reg[1]=(float)(intr_w*rb*rb);if(k2mask>0)reg[2]=(float)(intr_w*rb*rb*rb*rb);}
    for(int i=0;i<9;++i)out[9*c+i]=sh[i][0]+(i>=6?reg[i-6]*vc[i]:0);}
}
