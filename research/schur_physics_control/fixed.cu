#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <cstdio>
#include <string>
#include <vector>
#include <cmath>
#include <algorithm>
#include <stdexcept>
using Scalar=double;
#define CK(x) do{if((x)!=cudaSuccess)throw std::runtime_error("CUDA failure");}while(0)
#include "reference.cuh"
#include "coarse.cuh"
template<class T>T* alloc(size_t n){T*p;CK(cudaMalloc(&p,n*sizeof(T)));return p;}
template<class T>T* load(std::string s,size_t n){std::vector<T>v(n);FILE*f=fopen(s.c_str(),"rb");if(!f||fread(v.data(),sizeof(T),n,f)!=n)throw std::runtime_error("capture read "+s);fclose(f);T*p=alloc<T>(n);CK(cudaMemcpy(p,v.data(),n*sizeof(T),cudaMemcpyHostToDevice));return p;}
__global__ void scaled(int n,const double*x,const double*E,double*y){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[i]=x[i]*E[i];}
__global__ void finish(int n,const double*x,const double*E,double sigma,double*y){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[i]=y[i]*E[i]+sigma*x[i];}
__global__ void normalize(int nc,const double*U,const double*E,double sig,double*B){int c=blockIdx.x*blockDim.x+threadIdx.x;if(c<nc)for(int i=0;i<9;++i)for(int j=0;j<9;++j)B[81ul*c+9*i+j]=U[81ul*c+9*i+j]*E[9*c+i]*E[9*c+j]+(i==j?sig:0);}
struct System {
  int nc,np,no,n; double sig,eta;
  float* W;double *U,*R,*E,*b,*v,*t,*u,*B,*tmp;int *cam,*pt,*off;
  System(std::string dir){
    dir+="/";int cd;double radius;FILE*f=fopen((dir+"dimensions.txt").c_str(),"r");
    if(!f||fscanf(f,"%d %d %d %d %lf %lf %lf",&cd,&nc,&np,&no,&sig,&radius,&eta)!=7||cd!=9)throw std::runtime_error("dimensions");fclose(f);n=9*nc;
    W=load<float>(dir+"W",27ul*no);U=load<double>(dir+"U",81ul*nc);R=load<double>(dir+"R",6ul*np);E=load<double>(dir+"E",n);b=load<double>(dir+"b",n);
    cam=load<int>(dir+"cams",no);pt=load<int>(dir+"points",no);off=load<int>(dir+"offsets",nc+1);
    v=alloc<double>(n);t=alloc<double>(3ul*np);u=alloc<double>(3ul*np);B=alloc<double>(81ul*nc);tmp=alloc<double>(n);
  }
  ~System(){cudaFree(W);for(auto p:{U,R,E,b,v,t,u,B,tmp})cudaFree(p);for(auto p:{cam,pt,off})cudaFree(p);}
  void Prepare(){normalize<<<(nc+255)/256,256>>>(nc,U,E,sig,B);MFBlockChol<9><<<(nc+255)/256,256>>>(B,nc,1e-10,nullptr);}
  void Apply(const double*in,double*out){
    scaled<<<(n+255)/256,256>>>(n,in,E,v);CK(cudaMemset(t,0,3ul*np*8));
    MFPass1<9,float><<<(no+255)/256,256>>>(W,cam,pt,v,no,t);
    MFVinvApply<<<(np+255)/256,256>>>(R,t,np,u);
    MFPass2<9,float><<<nc,256>>>(W,pt,off,u,U,v,no,out);
    finish<<<(n+255)/256,256>>>(n,in,E,sig,out);
  }
  void Base(const double*r,double*z){MFBlockSolve<9><<<(nc+255)/256,256>>>(B,r,nc,0,tmp);MFBlockSolve<9><<<(nc+255)/256,256>>>(B,tmp,nc,1,z);}
};
struct Timer{cudaEvent_t a,b;Timer(){CK(cudaEventCreate(&a));CK(cudaEventCreate(&b));}~Timer(){cudaEventDestroy(a);cudaEventDestroy(b);}void Start(){CK(cudaEventRecord(a));}double End(){CK(cudaEventRecord(b));CK(cudaEventSynchronize(b));float x;CK(cudaEventElapsedTime(&x,a,b));return x;}};
struct Result{int iterations=0,products=0;double relative=1,ms=0;bool hit=false,negative=false;};
Result Solve(System&s,cublasHandle_t h,PrismCoarse* coarse,bool collect,double*save_x=nullptr){
  const int n=s.n;auto x=alloc<double>(n),r=alloc<double>(n),z=alloc<double>(n),p=alloc<double>(n),ap=alloc<double>(n);
  auto dot=[&](const double*a,const double*b){double v;PrismCoarse::blas(cublasDdot(h,n,a,1,b,1,&v));return v;};
  Result out;Timer time;time.Start();
  auto pre=[&](){if(coarse)coarse->Apply(r,z,[&](const double*a,double*b){s.Base(a,b);});else s.Base(r,z);};
  if(collect&&coarse)coarse->StartCollection();
  CK(cudaMemset(x,0,n*8ul));CK(cudaMemcpy(r,s.b,n*8ul,cudaMemcpyDeviceToDevice));
  double nb=std::sqrt(dot(r,r));pre();CK(cudaMemcpy(p,z,n*8ul,cudaMemcpyDeviceToDevice));double rz=dot(r,z);
  for(int it=0;it<128;++it){
    s.Apply(p,ap);++out.products;double pap=dot(p,ap),pp=dot(p,p);
    if(!(pap>1e-14*pp)||!std::isfinite(pap)){out.negative=true;break;}
    if(collect&&coarse)coarse->Observe(h,p,ap,pp);
    double alpha=rz/pap,minus=-alpha,one=1;
    PrismCoarse::blas(cublasDaxpy(h,n,&alpha,p,1,x,1));PrismCoarse::blas(cublasDaxpy(h,n,&minus,ap,1,r,1));++out.iterations;
    out.relative=std::sqrt(dot(r,r))/nb;
    if(out.relative<=s.eta||it==127){
      s.Apply(x,ap);++out.products;double m=-1;PrismCoarse::blas(cublasDscal(h,n,&m,ap,1));PrismCoarse::blas(cublasDaxpy(h,n,&one,s.b,1,ap,1));
      out.relative=std::sqrt(dot(ap,ap))/nb;
      if(out.relative<=s.eta||it==127){out.hit=out.relative<=s.eta;break;}
      CK(cudaMemcpy(r,ap,n*8ul,cudaMemcpyDeviceToDevice));pre();CK(cudaMemcpy(p,z,n*8ul,cudaMemcpyDeviceToDevice));rz=dot(r,z);continue;
    }
    pre();double next=dot(r,z),beta=next/rz;PrismCoarse::blas(cublasDscal(h,n,&beta,p,1));PrismCoarse::blas(cublasDaxpy(h,n,&one,z,1,p,1));rz=next;
  }
  if(save_x)CK(cudaMemcpy(save_x,x,n*8ul,cudaMemcpyDeviceToDevice));
  out.ms=time.End();if(collect&&coarse)coarse->FinishCollection(out.iterations);
  for(auto v:{x,r,z,p,ap})cudaFree(v);return out;
}
#ifndef PRISM_FIXED_LIBRARY
int main(int argc,char**argv){
  if(argc<2||argc>3)return 2;
  System current(argv[1]);System*previous=argc==3?new System(argv[2]):nullptr;
  if(previous&&previous->n!=current.n)throw std::runtime_error("camera dimensions changed");
  cublasHandle_t h;PrismCoarse::blas(cublasCreate(&h));
  int repetitions=getenv("PRISM_FIXED_REPS")?atoi(getenv("PRISM_FIXED_REPS")):3;
  for(int rep=-1;rep<repetitions;++rep)for(int arm=0;arm<3;++arm){
    int ranks[3]={0,8,16},rank=ranks[(arm+std::max(0,rep))%3];
    PrismCoarse*coarse=rank?new PrismCoarse(current.n,rank):nullptr;
    Result prev;double prev_setup=0,setup=0;Timer timer;
    if(previous){timer.Start();previous->Prepare();prev_setup=timer.End();prev=Solve(*previous,h,coarse,true);}
    timer.Start();current.Prepare();
    if(coarse)coarse->Prepare(h,[&](const double*a,double*b){current.Apply(a,b);});
    setup=timer.End();
    auto result=Solve(current,h,coarse,true);
    if(rep>=0)printf("COARSE_FIXED rep=%d rank=%d used=%d active=%d coarse_rejects=%d prior_iterations=%d prior_hit=%d prior_ms=%.9g setup_ms=%.9g solve_ms=%.9g current_ms=%.9g pair_ms=%.9g iterations=%d products=%d true_relative=%.17g hit=%d negative=%d\n",
      rep,rank,coarse?coarse->used:0,coarse?coarse->active:0,coarse?coarse->rejects:0,
      prev.iterations,previous?prev.hit:1,prev.ms+prev_setup,setup,result.ms,setup+result.ms,prev_setup+prev.ms+setup+result.ms,result.iterations,result.products+(coarse?coarse->used:0),result.relative,result.hit,result.negative);
    fflush(stdout);delete coarse;
  }
  delete previous;cublasDestroy(h);
}
#endif
