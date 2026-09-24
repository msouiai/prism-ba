#pragma once
// Bounded conventional nonlinear point-only refinement at fixed cameras.
// One analytic Gauss-Newton step per track; fixed diagonal regularization and
// three backtracking trials. No candidate is allowed to worsen its whole track.
__device__ double PrismRefinePixel(int o,const int* ci,const double* uv,
    const double* R,const double* t,const double* f,const double* k1,
    const double* k2,const double* x,double* jac=nullptr,double* residual=nullptr){
  int c=ci[o];const double* r=R+9*c;
  double q[3];for(int a=0;a<3;++a)q[a]=r[3*a]*x[0]+r[3*a+1]*x[1]+r[3*a+2]*x[2]+t[3*c+a];
  double u=-q[0]/q[2],v=-q[1]/q[2],s=u*u+v*v;
  double d=1+k1[c]*s+k2[c]*s*s,h=k1[c]+2*k2[c]*s;
  double e[2]={f[c]*d*u-uv[2*o],f[c]*d*v-uv[2*o+1]};
  if(residual){residual[0]=e[0];residual[1]=e[1];}
  if(jac)for(int a=0;a<3;++a){
    double du=-(r[a]+u*r[6+a])/q[2],dv=-(r[3+a]+v*r[6+a])/q[2];
    double ds=2*(u*du+v*dv);
    jac[a]=f[c]*(d*du+u*h*ds);jac[3+a]=f[c]*(d*dv+v*h*ds);
  }
  double z=.5*(e[0]*e[0]+e[1]*e[1]);return isfinite(z)?z:CUDART_INF;
}
__global__ void MFPointRefine(const int* offsets,const int* order,const int* ci,
    const double* uv,const double* R,const double* t,const double* X,
    const double* f,const double* k1,const double* k2,int np,int nc,
    double* step,unsigned long long* changed){
  int lane=threadIdx.x%32,point=(blockIdx.x*blockDim.x+threadIdx.x)/32;
  if(point>=np)return;
  double x[3]={X[3*point],X[3*point+1],X[3*point+2]},a[13]={};
  for(int j=offsets[point]+lane;j<offsets[point+1];j+=32){
    double J[6],e[2];a[12]+=PrismRefinePixel(order[j],ci,uv,R,t,f,k1,k2,x,J,e);
    for(int h=0;h<3;++h){a[9+h]+=J[h]*e[0]+J[3+h]*e[1];
      for(int k=0;k<3;++k)a[3*h+k]+=J[h]*J[k]+J[3+h]*J[3+k];}
  }
  for(int k=16;k;k>>=1)for(int h=0;h<13;++h)a[h]+=__shfl_down_sync(0xffffffff,a[h],k);
  double dx[3]={};
  if(lane==0){
    double scale=fmax((a[0]+a[4]+a[8])/3,1e-30),L[9]={};bool ok=isfinite(a[12]);
    for(int h=0;h<3;++h)a[3*h+h]+=1e-6*fmax(a[3*h+h],1e-3*scale);
    for(int i=0;i<3;++i)for(int j=0;j<=i;++j){
      double v=a[3*i+j];for(int k=0;k<j;++k)v-=L[3*i+k]*L[3*j+k];
      if(i==j){ok=ok&&isfinite(v)&&v>0;L[3*i+j]=sqrt(fmax(v,1e-300));}
      else L[3*i+j]=v/L[3*j+j];
    }
    for(int i=0;i<3;++i){double v=-a[9+i];for(int j=0;j<i;++j)v-=L[3*i+j]*dx[j];dx[i]=v/L[3*i+i];}
    for(int i=2;i>=0;--i){double v=dx[i];for(int j=i+1;j<3;++j)v-=L[3*j+i]*dx[j];dx[i]=v/L[3*i+i];}
    for(int i=0;i<3;++i)ok=ok&&isfinite(dx[i]);if(!ok)for(int i=0;i<3;++i)dx[i]=0;
  }
  for(int i=0;i<3;++i)dx[i]=__shfl_sync(0xffffffff,dx[i],0);
  double best=__shfl_sync(0xffffffff,a[12],0),selected=0;
  for(int trial=0;trial<3;++trial){double alpha=ldexp(1.,-trial),y[3],cost=0;
    for(int i=0;i<3;++i)y[i]=x[i]+alpha*dx[i];
    for(int j=offsets[point]+lane;j<offsets[point+1];j+=32)cost+=PrismRefinePixel(order[j],ci,uv,R,t,f,k1,k2,y);
    for(int k=16;k;k>>=1)cost+=__shfl_down_sync(0xffffffff,cost,k);
    if(lane==0&&cost<best){best=cost;selected=alpha;}
  }
  if(lane==0&&selected){for(int i=0;i<3;++i)step[9*nc+3*point+i]+=selected*dx[i];atomicAdd(changed,1ULL);}
}
struct PrismPointRefinement {
  unsigned long long* changed=nullptr;
  PrismPointRefinement(){CUDA_CHECK(cudaMalloc(&changed,sizeof(*changed)));}
  ~PrismPointRefinement(){cudaFree(changed);}
  unsigned long long Choose(const DeviceProblem& p,const DeviceState& full,double* step){
    CUDA_CHECK(cudaMemset(changed,0,sizeof(*changed)));
    MFPointRefine<<<(p.npt+7)/8,256>>>(p.point_obs_offsets,p.point_obs_list,p.cam_idx,p.uv,
      full.R,full.t,full.X,INTR_F(p,full),INTR_K1(p,full),INTR_K2(p,full),p.npt,p.ncam,step,changed);
    unsigned long long n=0;CUDA_CHECK(cudaMemcpy(&n,changed,sizeof(n),cudaMemcpyDeviceToHost));return n;
  }
};
