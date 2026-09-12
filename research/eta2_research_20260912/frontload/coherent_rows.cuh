#pragma once
// Brief 0: diagnostic-only FP64 Jacobian operator. No production path changes.
__global__ void B0Rows(const int* ci,const int* pi,const int* slot,const double* uv,
    const double* R,const double* t,const double* X,const double* f,const double* k1,
    const double* k2,int no,double* Jc,double* Jp,double* residual,int* order){
  int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=no)return;
  int c=ci[o],j=pi[o],a=slot[o];const double* r=R+9*c;const double* x=X+3*j;
  double gx[12],gy[12],rx,ry;
  BalResidualGrad12(r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7],r[8],
    t[3*c],t[3*c+1],t[3*c+2],x[0],x[1],x[2],f[c],k1[c],k2[c],uv[2*o],uv[2*o+1],gx,gy,&rx,&ry);
  gx[8]=gy[8]=0;
  for(int k=0;k<9;++k){Jc[18ul*a+k]=gx[k];Jc[18ul*a+9+k]=gy[k];}
  for(int k=0;k<3;++k){Jp[6ul*o+k]=gx[k+9];Jp[6ul*o+3+k]=gy[k+9];}
  residual[2ul*o]=rx;residual[2ul*o+1]=ry;order[a]=o;
}
__global__ void B0Forward(const int* ci,const int* slot,const double* Jc,
    const double* E,const double* x,int no,double* y){
  int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=no)return;int c=ci[o],a=slot[o];
  double u=0,v=0;for(int k=0;k<9;++k){double t=E[9*c+k]*x[9*c+k];u+=Jc[18ul*a+k]*t;v+=Jc[18ul*a+9+k]*t;}
  y[2ul*o]=u;y[2ul*o+1]=v;
}
__global__ void B0PointRhs(const int* offsets,const int* order,const double* Jp,
    const double* y,int np,double* g){
  int lane=threadIdx.x%32,j=(blockIdx.x*blockDim.x+threadIdx.x)/32;if(j>=np)return;
  double v[3]={};for(int a=offsets[j]+lane;a<offsets[j+1];a+=32){int o=order[a];
    for(int k=0;k<3;++k)v[k]+=Jp[6ul*o+k]*y[2ul*o]+Jp[6ul*o+3+k]*y[2ul*o+1];}
  for(int s=16;s;s/=2)for(int k=0;k<3;++k)v[k]+=__shfl_down_sync(0xffffffff,v[k],s);
  if(lane==0)for(int k=0;k<3;++k)g[3*j+k]=v[k];
}
__global__ void B0Prior(const double* f,const double* r2,const double* count,int nc,double* Q){
  int c=blockIdx.x*blockDim.x+threadIdx.x;if(c>=nc)return;
  for(int k=0;k<9;++k)Q[9*c+k]=0;
  if(count[c]>0){double m=fmax(r2[c]/count[c],1e-12),sf=.5*fabs(f[c])+1e-3;
    Q[9*c+6]=1/(sf*sf);Q[9*c+7]=m*m;}
}
__global__ void B0Adjoint(const int* offsets,const int* order,const int* pi,
    const double* Jc,const double* Jp,const double* y,const double* u,
    const double* E,const double* Q,const double* x,double lambda,int nc,double* out){
  int c=blockIdx.x;if(c>=nc)return;double v[9]={};
  for(int a=offsets[c]+threadIdx.x;a<offsets[c+1];a+=blockDim.x){int o=order[a],j=pi[o];
    double rx=y[2ul*o],ry=y[2ul*o+1];for(int k=0;k<3;++k){rx-=Jp[6ul*o+k]*u[3*j+k];ry-=Jp[6ul*o+3+k]*u[3*j+k];}
    for(int k=0;k<9;++k)v[k]+=Jc[18ul*a+k]*rx+Jc[18ul*a+9+k]*ry;
  }
  __shared__ double sum[9][256];for(int k=0;k<9;++k)sum[k][threadIdx.x]=v[k];__syncthreads();
  for(int s=128;s;s/=2){if(threadIdx.x<s)for(int k=0;k<9;++k)sum[k][threadIdx.x]+=sum[k][threadIdx.x+s];__syncthreads();}
  if(threadIdx.x<9){int k=threadIdx.x,a=9*c+k;out[a]=E[a]*sum[k][0]+(x?(lambda+E[a]*E[a]*Q[a])*x[a]:0);}
}
__global__ void B0Compose(const double* x,const double* E,const double* xp,int nc,int np,double* d){
  int a=blockIdx.x*blockDim.x+threadIdx.x;
  if(a<9*nc)d[a]=-E[a]*x[a];if(a<3*np)d[9ul*nc+a]=-xp[a];
}
