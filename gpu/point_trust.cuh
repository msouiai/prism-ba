#pragma once
// Conditional point trust region: camera step / forcing and linearization
// are held fixed. D = max(diag(V), 1e-3 mean(diag(V))) elementwise.
template<bool Solve>
__global__ void MFPointTrustSums(const double* R0,const double* cd,const double* step,
    int np,double old_tau,double new_tau,double* sums){
  const int p=blockIdx.x*blockDim.x+threadIdx.x;
  double n=0,q=0,after=0;
  if(p<np){
    const double* r=R0+6*p;const double* x=step+3*p;
    double mean=(cd[3*p]+cd[3*p+1]+cd[3*p+2])/3;
    double d[3];for(int i=0;i<3;++i)d[i]=fmax(cd[3*p+i],1e-3*mean);
    double z[3]={r[0]*x[0]+r[1]*x[1]+r[2]*x[2],r[3]*x[1]+r[4]*x[2],r[5]*x[2]};
    for(int i=0;i<3;++i){n+=d[i]*x[i]*x[i];q+=z[i]*z[i];}
    if constexpr(Solve){
      if(n>0){
        double h[3]={r[0]*z[0]+old_tau*d[0]*x[0],
          r[1]*z[0]+r[3]*z[1]+old_tau*d[1]*x[1],
          r[2]*z[0]+r[4]*z[1]+r[5]*z[2]+old_tau*d[2]*x[2]};
        double rt[6];for(int i=0;i<6;++i)rt[i]=r[i];
        for(int i=0;i<3;++i){double row[3]={0,0,0};row[i]=sqrt(new_tau*d[i]);MFGivens(rt,row);}
        double y[3];MFVinv(rt,h,y);
        for(int i=0;i<3;++i)after+=d[i]*y[i]*y[i];
      }
    }
  }
  __shared__ double buf[3][256];buf[0][threadIdx.x]=n;buf[1][threadIdx.x]=q;buf[2][threadIdx.x]=after;
  __syncthreads();
  for(int k=128;k>0;k>>=1){if(threadIdx.x<k)for(int j=0;j<3;++j)buf[j][threadIdx.x]+=buf[j][threadIdx.x+k];__syncthreads();}
  if(threadIdx.x<3)atomicAdd(sums+threadIdx.x,buf[threadIdx.x][0]);
}
struct PrismPointTrust {
  struct Result {double tau=0,ratio=1,rayleigh_tau=0,norm2=0,curvature=0;int calls=0;bool valid=false;};
  double* device=nullptr;
  PrismPointTrust(){CUDA_CHECK(cudaMalloc(&device,3*sizeof(double)));}
  ~PrismPointTrust(){cudaFree(device);}
  PrismPointTrust(const PrismPointTrust&)=delete;
  PrismPointTrust& operator=(const PrismPointTrust&)=delete;
  void Sums(const double* r,const double* d,const double* x,int n,double old_tau,
      double trial,double* host,bool solve){
    CUDA_CHECK(cudaMemset(device,0,3*sizeof(double)));
    if(solve)MFPointTrustSums<true><<<GridSize(n),256>>>(r,d,x,n,old_tau,trial,device);
    else MFPointTrustSums<false><<<GridSize(n),256>>>(r,d,x,n,old_tau,trial,device);
    CUDA_CHECK(cudaMemcpy(host,device,3*sizeof(double),cudaMemcpyDeviceToHost));
  }
  Result Choose(const double* r,const double* d,const double* x,int n,
      double old_tau,double alpha,int mode){
    Result out;out.tau=old_tau;
    if(!(old_tau>0&&std::isfinite(old_tau)&&alpha>0&&alpha<1))return out;
    double v[3];Sums(r,d,x,n,old_tau,old_tau,v,false);++out.calls;
    out.norm2=v[0];out.curvature=v[1];
    if(!(std::isfinite(v[0])&&v[0]>0&&std::isfinite(v[1])&&v[1]>=0))return out;
    const double mu=v[1]/v[0];
    if(mu>3*(1+1e-8))return out; // D/QR mismatch or unusable numerics
    constexpr double cap=1e8;
    out.rayleigh_tau=std::min(cap,(old_tau+mu)/alpha-mu);
    auto ratio2=[&](double tau){Sums(r,d,x,n,old_tau,tau,v,true);++out.calls;return v[2]/out.norm2;};
    if(mode==1){out.tau=out.rayleigh_tau;out.ratio=std::sqrt(ratio2(out.tau));
      out.valid=std::isfinite(out.ratio)&&out.tau>=old_tau;return out;}
    // Eigenvalues of D^-1/2 V D^-1/2 lie in [0,3], since its trace <=3.
    double lo=std::min(cap,old_tau/alpha),hi=std::min(cap,(old_tau+3)/alpha-3);
    const double target=alpha*alpha;
    double hi_ratio=ratio2(hi);
    if(!(std::isfinite(hi_ratio)&&hi_ratio<=target*(1+1e-10)))return out;
    for(int k=0;k<12 && hi>lo*(1+1e-3);++k){
      const double mid=std::sqrt(lo*hi),value=ratio2(mid);
      if(!std::isfinite(value))return out;
      if(value>target)lo=mid;else{hi=mid;hi_ratio=value;}
    }
    out.tau=hi;out.ratio=std::sqrt(hi_ratio);out.valid=true;return out;
  }
};
