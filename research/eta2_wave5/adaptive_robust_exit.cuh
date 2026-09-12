#pragma once

// Count observations whose Cauchy weight is below 0.5.  For
// w(s)=1/(1+s/a2), this is exactly s>a2.  One block atomic keeps this
// diagnostic/exit rule cheap even when the initial stage downweights many
// observations.
__global__ void W5CountDownweighted(const int* ci,const int* pi,const double* uv,
    const double* R,const double* t,const double* X,const double* f,
    const double* k1,const double* k2,int no,double a2,
    unsigned long long* total){
  int o=blockIdx.x*blockDim.x+threadIdx.x;unsigned int hit=0;
  if(o<no){
    int c=ci[o],p=pi[o];const double* r=R+9*c;const double* x=X+3*p;
    double qx=r[0]*x[0]+r[1]*x[1]+r[2]*x[2]+t[3*c];
    double qy=r[3]*x[0]+r[4]*x[1]+r[5]*x[2]+t[3*c+1];
    double qz=r[6]*x[0]+r[7]*x[1]+r[8]*x[2]+t[3*c+2];
    double u=-qx/qz,v=-qy/qz,s=u*u+v*v;
    double factor=f[c]*(1+k1[c]*s+k2[c]*s*s);
    double a=factor*u-uv[2*o],b=factor*v-uv[2*o+1];
    double sq=a*a+b*b;hit=(unsigned int)(isfinite(sq)&&sq>a2);
  }
  __shared__ unsigned int count[256];count[threadIdx.x]=hit;__syncthreads();
  for(int d=128;d;d>>=1){if(threadIdx.x<d)count[threadIdx.x]+=count[threadIdx.x+d];__syncthreads();}
  if(threadIdx.x==0&&count[0])atomicAdd(total,(unsigned long long)count[0]);
}

struct W5AdaptiveExit {
  unsigned long long* count=nullptr;
  W5AdaptiveExit(){CUDA_CHECK(cudaMalloc(&count,sizeof(*count)));}
  ~W5AdaptiveExit(){cudaFree(count);}
  W5AdaptiveExit(const W5AdaptiveExit&)=delete;
  double Fraction(const DeviceProblem& p,const DeviceState& s,double a2,
                  unsigned long long& number){
    CUDA_CHECK(cudaMemset(count,0,sizeof(*count)));
    W5CountDownweighted<<<GridSize(p.nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,
      s.R,s.t,s.X,INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),p.nobs,a2,count);
    CUDA_CHECK(cudaMemcpy(&number,count,sizeof(number),cudaMemcpyDeviceToHost));
    return (double)number/std::max(1,p.nobs);
  }
};
