#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <Eigen/Dense>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using Scalar=double;
#define CK(x) do{cudaError_t e_=(x);if(e_!=cudaSuccess){std::fprintf(stderr,"CUDA %s:%d: %s\n",__FILE__,__LINE__,cudaGetErrorString(e_));throw std::runtime_error("CUDA");}}while(0)
#define BK(x) do{cublasStatus_t e_=(x);if(e_!=CUBLAS_STATUS_SUCCESS){std::fprintf(stderr,"CUBLAS %s:%d: %d\n",__FILE__,__LINE__,(int)e_);throw std::runtime_error("CUBLAS");}}while(0)
#include "reference.cuh"

using Clock=std::chrono::steady_clock;
static double elapsed_ms(Clock::time_point start){return 1e3*std::chrono::duration<double>(Clock::now()-start).count();}

template<class T> static std::vector<T> load_host(const std::string&path,size_t n){
  std::vector<T> v(n);FILE*f=std::fopen(path.c_str(),"rb");
  if(!f||std::fread(v.data(),sizeof(T),n,f)!=n)throw std::runtime_error("read "+path);
  std::fclose(f);return v;
}
template<class T> static T* device_copy(const std::vector<T>&v){T*p=nullptr;CK(cudaMalloc(&p,v.size()*sizeof(T)));CK(cudaMemcpy(p,v.data(),v.size()*sizeof(T),cudaMemcpyHostToDevice));return p;}
template<class T> static T* device_alloc(size_t n){T*p=nullptr;CK(cudaMalloc(&p,n*sizeof(T)));return p;}

__global__ void scale_vec(int n,const double*x,const double*E,double*y){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[i]=x[i]*E[i];}
__global__ void finish_vec(int n,const double*x,const double*E,double sigma,double*y){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[i]=y[i]*E[i]+sigma*x[i];}
__global__ void block_transform(int nc,const double*B,const double*x,double*y,int transpose){
  int c=blockIdx.x*blockDim.x+threadIdx.x;if(c>=nc)return;const double*b=B+81*c;const double*v=x+9*c;double*out=y+9*c;
#pragma unroll
  for(int i=0;i<9;++i){double a=0;
#pragma unroll
    for(int j=0;j<9;++j)a+=(transpose?b[9*j+i]:b[9*i+j])*v[j];out[i]=a;}
}

struct DeviceSystem{
  int nc,np,n,grid;long long no;double sigma;
  float*W=nullptr;double*U=nullptr,*R=nullptr,*E=nullptr,*b=nullptr,*Linv=nullptr;
  int*cams=nullptr,*pts=nullptr,*offs=nullptr;
  double*v=nullptr,*t=nullptr,*point_u=nullptr,*x=nullptr,*r=nullptr,*z=nullptr,*p=nullptr,*ap=nullptr,*q=nullptr,*w=nullptr,*svec=nullptr,*stats=nullptr;
  cublasHandle_t host=nullptr,device=nullptr;
  DeviceSystem(int nc_,int np_,long long no_,double sig,const std::vector<float>&Wh,
      const std::vector<double>&Uh,const std::vector<double>&Rh,const std::vector<double>&Eh,
      const std::vector<double>&bh,const std::vector<double>&Lh,const std::vector<int>&ch,
      const std::vector<int>&ph,const std::vector<int>&oh):nc(nc_),np(np_),n(9*nc_),grid((n+255)/256),no(no_),sigma(sig){
    W=device_copy(Wh);U=device_copy(Uh);R=device_copy(Rh);E=device_copy(Eh);b=device_copy(bh);Linv=device_copy(Lh);
    cams=device_copy(ch);pts=device_copy(ph);offs=device_copy(oh);v=device_alloc<double>(n);t=device_alloc<double>((size_t)3*np);
    point_u=device_alloc<double>((size_t)3*np);x=device_alloc<double>(n);r=device_alloc<double>(n);z=device_alloc<double>(n);
    p=device_alloc<double>(n);ap=device_alloc<double>(n);q=device_alloc<double>(n);w=device_alloc<double>(n);svec=device_alloc<double>(n);
    stats=device_alloc<double>(8);BK(cublasCreate(&host));BK(cublasCreate(&device));BK(cublasSetPointerMode(device,CUBLAS_POINTER_MODE_DEVICE));
  }
  ~DeviceSystem(){if(host)cublasDestroy(host);if(device)cublasDestroy(device);for(void*p:{(void*)W,(void*)U,(void*)R,(void*)E,(void*)b,(void*)Linv,(void*)cams,(void*)pts,(void*)offs,(void*)v,(void*)t,(void*)point_u,(void*)x,(void*)r,(void*)z,(void*)p,(void*)ap,(void*)q,(void*)w,(void*)svec,(void*)stats})cudaFree(p);}
};

static void apply_A(DeviceSystem&s,const double*in,double*out){
  scale_vec<<<s.grid,256>>>(s.n,in,s.E,s.v);CK(cudaMemset(s.t,0,(size_t)3*s.np*sizeof(double)));
  MFPass1<9,float><<<((int)s.no+255)/256,256>>>(s.W,s.cams,s.pts,s.v,(int)s.no,s.t);
  MFVinvApply<<<(s.np+255)/256,256>>>(s.R,s.t,s.np,s.point_u);
  MFPass2<9,float><<<s.nc,256>>>(s.W,s.pts,s.offs,s.point_u,s.U,s.v,(int)s.no,out);
  finish_vec<<<s.grid,256>>>(s.n,in,s.E,s.sigma,out);
}
static void precondition(DeviceSystem&s,const double*in,double*out){
  block_transform<<<(s.nc+63)/64,64>>>(s.nc,s.Linv,in,s.q,0);
  block_transform<<<(s.nc+63)/64,64>>>(s.nc,s.Linv,s.q,out,1);
}

static std::vector<double> batch(DeviceSystem&s,
    std::initializer_list<std::pair<const double*,const double*>> terms,int&phases){
  if(terms.size()>8)throw std::runtime_error("dot batch too large");size_t k=0;
  for(auto term:terms){BK(cublasDdot(s.device,s.n,term.first,1,term.second,1,s.stats+k));++k;}
  std::vector<double> out(k);CK(cudaMemcpy(out.data(),s.stats,k*sizeof(double),cudaMemcpyDeviceToHost));++phases;return out;
}

static std::vector<double> build_Linv(int nc,double sigma,const std::vector<double>&U,const std::vector<double>&E){
  std::vector<double> out((size_t)81*nc);double min_eval=std::numeric_limits<double>::infinity();
  for(int c=0;c<nc;++c){Eigen::Matrix<double,9,9> H;
    for(int i=0;i<9;++i)for(int j=0;j<9;++j)H(i,j)=U[(size_t)81*c+9*i+j]*E[9*c+i]*E[9*c+j]+(i==j?sigma:0);
    H=(H+H.transpose()).eval()*0.5;Eigen::SelfAdjointEigenSolver<Eigen::Matrix<double,9,9>> es(H);
    if(es.info()!=Eigen::Success||es.eigenvalues().minCoeff()<=0)throw std::runtime_error("non-SPD Hcc block");min_eval=std::min(min_eval,es.eigenvalues().minCoeff());
    Eigen::LLT<Eigen::Matrix<double,9,9>> llt(H);if(llt.info()!=Eigen::Success)throw std::runtime_error("Hcc LLT");
    Eigen::Matrix<double,9,9> Li=llt.matrixL().solve(Eigen::Matrix<double,9,9>::Identity());
    for(int i=0;i<9;++i)for(int j=0;j<9;++j)out[(size_t)81*c+9*i+j]=Li(i,j);
  }
  std::printf("HCC_FACTOR min_block_eigenvalue=%.17g\n",min_eval);return out;
}

struct Result{
  int updates=0,products=0,reductions=0;double true_relative=1,total_ms=0,min_den_ratio=std::numeric_limits<double>::infinity();
  bool hit=false,negative=false,audit_failed=false;std::vector<double> solution;
};

static void finish_result(DeviceSystem&s,Result&out,Clock::time_point start){
  CK(cudaDeviceSynchronize());out.total_ms=elapsed_ms(start);out.solution.resize(s.n);
  CK(cudaMemcpy(out.solution.data(),s.x,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToHost));
}

static bool explicit_audit(DeviceSystem&s,Result&out,double nb){
  apply_A(s,s.x,s.ap);++out.products;CK(cudaMemcpy(s.w,s.b,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));
  const double minus=-1;BK(cublasDaxpy(s.host,s.n,&minus,s.ap,1,s.w,1));auto d=batch(s,{{s.w,s.w}},out.reductions);
  out.true_relative=std::sqrt(std::max(0.0,d[0]))/nb;out.hit=out.true_relative<=0.5;out.audit_failed=out.true_relative>0.505;return out.hit;
}

static Result standard(DeviceSystem&s){
  Result out;auto start=Clock::now();CK(cudaMemset(s.x,0,(size_t)s.n*sizeof(double)));CK(cudaMemcpy(s.r,s.b,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));
  auto bn=batch(s,{{s.b,s.b}},out.reductions);double nb=std::sqrt(bn[0]);precondition(s,s.r,s.z);auto init=batch(s,{{s.r,s.z}},out.reductions);
  double gamma=init[0];CK(cudaMemcpy(s.p,s.z,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));
  while(out.updates<128){
    apply_A(s,s.p,s.ap);++out.products;auto cur=batch(s,{{s.p,s.ap},{s.p,s.p}},out.reductions);double denom=cur[0],pp=cur[1];
    out.min_den_ratio=std::min(out.min_den_ratio,denom/std::max(pp,1e-300));if(!(denom>1e-14*pp)){out.negative=true;break;}
    double alpha=gamma/denom,minus=-alpha;BK(cublasDaxpy(s.host,s.n,&alpha,s.p,1,s.x,1));BK(cublasDaxpy(s.host,s.n,&minus,s.ap,1,s.r,1));++out.updates;
    precondition(s,s.r,s.z);auto post=batch(s,{{s.r,s.r},{s.r,s.z}},out.reductions);double rr=post[0],next=post[1];
    if(std::sqrt(std::max(0.0,rr))<=0.5*nb){explicit_audit(s,out,nb);break;}
    double beta=next/gamma;BK(cublasDscal(s.host,s.n,&beta,s.p,1));const double one=1;BK(cublasDaxpy(s.host,s.n,&one,s.z,1,s.p,1));gamma=next;
  }
  if(!out.hit&&!out.negative){apply_A(s,s.x,s.ap);++out.products;CK(cudaMemcpy(s.w,s.b,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));const double minus=-1;BK(cublasDaxpy(s.host,s.n,&minus,s.ap,1,s.w,1));auto d=batch(s,{{s.w,s.w}},out.reductions);out.true_relative=std::sqrt(std::max(0.0,d[0]))/nb;}
  finish_result(s,out,start);return out;
}

static Result cgcg(DeviceSystem&s){
  Result out;auto start=Clock::now();CK(cudaMemset(s.x,0,(size_t)s.n*sizeof(double)));CK(cudaMemcpy(s.r,s.b,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));
  auto bn=batch(s,{{s.b,s.b}},out.reductions);double nb=std::sqrt(bn[0]);precondition(s,s.r,s.z);apply_A(s,s.z,s.w);++out.products;
  auto init=batch(s,{{s.r,s.r},{s.r,s.z},{s.w,s.z},{s.z,s.z}},out.reductions);
  double gamma=init[1],denom=init[2],pp=init[3],alpha=gamma/denom;
  out.min_den_ratio=std::min(out.min_den_ratio,denom/std::max(pp,1e-300));if(!(denom>1e-14*pp)){out.negative=true;finish_result(s,out,start);return out;}
  CK(cudaMemcpy(s.p,s.z,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));CK(cudaMemcpy(s.svec,s.w,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));
  while(out.updates<128){
    double minus=-alpha;BK(cublasDaxpy(s.host,s.n,&alpha,s.p,1,s.x,1));BK(cublasDaxpy(s.host,s.n,&minus,s.svec,1,s.r,1));++out.updates;
    if(out.updates==128)break;
    precondition(s,s.r,s.z);apply_A(s,s.z,s.w);++out.products;
    auto cur=batch(s,{{s.r,s.r},{s.r,s.z},{s.w,s.z},{s.z,s.z},{s.z,s.p}},out.reductions);
    const double rr=cur[0],next=cur[1],delta=cur[2],uu=cur[3],up=cur[4];
    if(std::sqrt(std::max(0.0,rr))<=0.5*nb){explicit_audit(s,out,nb);break;}
    const double beta=next/gamma;const double next_denom=delta-beta*next/alpha;const double next_pp=uu+2*beta*up+beta*beta*pp;
    out.min_den_ratio=std::min(out.min_den_ratio,next_denom/std::max(next_pp,1e-300));
    if(!(next_denom>1e-14*next_pp)||!std::isfinite(next_denom)){out.negative=true;break;}
    BK(cublasDscal(s.host,s.n,&beta,s.p,1));const double one=1;BK(cublasDaxpy(s.host,s.n,&one,s.z,1,s.p,1));
    BK(cublasDscal(s.host,s.n,&beta,s.svec,1));BK(cublasDaxpy(s.host,s.n,&one,s.w,1,s.svec,1));
    alpha=next/next_denom;gamma=next;denom=next_denom;pp=next_pp;
  }
  if(!out.hit){apply_A(s,s.x,s.ap);++out.products;CK(cudaMemcpy(s.w,s.b,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));const double minus=-1;BK(cublasDaxpy(s.host,s.n,&minus,s.ap,1,s.w,1));auto d=batch(s,{{s.w,s.w}},out.reductions);out.true_relative=std::sqrt(std::max(0.0,d[0]))/nb;out.hit=out.true_relative<=0.5;}
  finish_result(s,out,start);return out;
}

static double relative_difference(const std::vector<double>&a,const std::vector<double>&b){
  long double d=0,n=0;for(size_t i=0;i<a.size();++i){long double x=(long double)a[i]-b[i];d+=x*x;n+=(long double)a[i]*a[i];}return std::sqrt((double)(d/std::max(n,(long double)1e-300)));}

static void print_result(const char*arm,int rep,const Result&r){
  std::printf("RESULT arm=%s rep=%d updates=%d products=%d reductions=%d true_relative=%.17g hit=%d negative=%d audit_failed=%d min_den_ratio=%.17g total_ms=%.9g\n",
    arm,rep,r.updates,r.products,r.reductions,r.true_relative,(int)r.hit,(int)r.negative,(int)r.audit_failed,r.min_den_ratio,r.total_ms);
}

int main(int argc,char**argv){try{
  if(argc!=2){std::fprintf(stderr,"usage: %s CAPTURE_DIR\n",argv[0]);return 2;}std::string dir=argv[1];if(dir.back()!='/')dir+='/';
  int cd,nc,np,no;double sigma,radius,eta;FILE*f=std::fopen((dir+"dimensions.txt").c_str(),"r");
  if(!f||std::fscanf(f,"%d %d %d %d %lf %lf %lf",&cd,&nc,&np,&no,&sigma,&radius,&eta)!=7||cd!=9||std::abs(eta-.5)>1e-15)throw std::runtime_error("dimensions/eta");if(f)std::fclose(f);
  auto W=load_host<float>(dir+"W",(size_t)27*no);auto U=load_host<double>(dir+"U",(size_t)81*nc);auto R=load_host<double>(dir+"R",(size_t)6*np);auto E=load_host<double>(dir+"E",(size_t)9*nc);auto b=load_host<double>(dir+"b",(size_t)9*nc);auto cams=load_host<int>(dir+"cams",no);auto pts=load_host<int>(dir+"points",no);auto offs=load_host<int>(dir+"offsets",nc+1);auto Linv=build_Linv(nc,sigma,U,E);
  DeviceSystem s(nc,np,no,sigma,W,U,R,E,b,Linv,cams,pts,offs);std::printf("SYSTEM nc=%d np=%d no=%d sigma=%.17g eta=%.17g\n",nc,np,no,sigma,eta);
  for(int warm=0;warm<3;++warm){if(warm&1){(void)cgcg(s);(void)standard(s);}else{(void)standard(s);(void)cgcg(s);}}
  for(int rep=0;rep<10;++rep){Result a,bres;if(rep&1){bres=cgcg(s);a=standard(s);}else{a=standard(s);bres=cgcg(s);}print_result("standard",rep,a);print_result("cgcg",rep,bres);std::printf("PAIR rep=%d relative_solution_difference=%.17g\n",rep,relative_difference(a.solution,bres.solution));std::fflush(stdout);}
  return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"ERROR %s\n",e.what());return 1;}}
