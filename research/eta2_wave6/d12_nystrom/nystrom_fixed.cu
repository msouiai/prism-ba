#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <Eigen/Dense>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

using Scalar=double;
#define CK(x) do{cudaError_t e_=(x);if(e_!=cudaSuccess){std::fprintf(stderr,"CUDA %s:%d: %s\n",__FILE__,__LINE__,cudaGetErrorString(e_));throw std::runtime_error("CUDA");}}while(0)
#define BK(x) do{cublasStatus_t e_=(x);if(e_!=CUBLAS_STATUS_SUCCESS){std::fprintf(stderr,"CUBLAS %s:%d: %d\n",__FILE__,__LINE__,(int)e_);throw std::runtime_error("CUBLAS");}}while(0)
#include "reference.cuh"

using Clock=std::chrono::steady_clock;
static double ms_since(Clock::time_point a){return 1e3*std::chrono::duration<double>(Clock::now()-a).count();}

template<class T> static std::vector<T> load_host(const std::string& path,size_t n){
  std::vector<T> v(n);FILE*f=std::fopen(path.c_str(),"rb");
  if(!f||std::fread(v.data(),sizeof(T),n,f)!=n)throw std::runtime_error("read "+path);
  std::fclose(f);return v;
}
template<class T> static T* device_copy(const std::vector<T>&v){
  T*p=nullptr;CK(cudaMalloc(&p,v.size()*sizeof(T)));CK(cudaMemcpy(p,v.data(),v.size()*sizeof(T),cudaMemcpyHostToDevice));return p;
}
template<class T> static T* device_alloc(size_t n){T*p=nullptr;CK(cudaMalloc(&p,n*sizeof(T)));return p;}

__global__ void scale_vec(int n,const double*x,const double*E,double*y){
  int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[i]=x[i]*E[i];
}
__global__ void finish_vec(int n,const double*x,const double*E,double sigma,double*y){
  int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[i]=y[i]*E[i]+sigma*x[i];
}
__global__ void block_transform(int nc,const double*B,const double*x,double*y,int transpose){
  int c=blockIdx.x*blockDim.x+threadIdx.x;if(c>=nc)return;
  const double*b=B+81*c;const double*v=x+9*c;double*out=y+9*c;
#pragma unroll
  for(int i=0;i<9;++i){double s=0;
#pragma unroll
    for(int j=0;j<9;++j)s+=(transpose?b[9*j+i]:b[9*i+j])*v[j];
    out[i]=s;
  }
}
__global__ void scale_small(int n,const double*c,double*x){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)x[i]*=c[i];}

struct DeviceSystem{
  int nc,np;long long no;int n,grid;double sigma;
  float*W=nullptr;double*U=nullptr,*R=nullptr,*E=nullptr,*b=nullptr,*Linv=nullptr;
  double*v=nullptr,*t=nullptr,*u=nullptr,*x=nullptr,*r=nullptr,*z=nullptr,*p=nullptr,*ap=nullptr,*q=nullptr,*w=nullptr;
  int*cams=nullptr,*pts=nullptr,*offs=nullptr;cublasHandle_t h=nullptr;
  DeviceSystem(int nc_,int np_,long long no_,double sig,const std::vector<float>&Wh,const std::vector<double>&Uh,
      const std::vector<double>&Rh,const std::vector<double>&Eh,const std::vector<double>&bh,
      const std::vector<double>&Lh,const std::vector<int>&ch,const std::vector<int>&ph,const std::vector<int>&oh)
      :nc(nc_),np(np_),no(no_),n(9*nc_),grid((n+255)/256),sigma(sig){
    W=device_copy(Wh);U=device_copy(Uh);R=device_copy(Rh);E=device_copy(Eh);b=device_copy(bh);Linv=device_copy(Lh);
    cams=device_copy(ch);pts=device_copy(ph);offs=device_copy(oh);v=device_alloc<double>(n);t=device_alloc<double>((size_t)3*np);
    u=device_alloc<double>((size_t)3*np);x=device_alloc<double>(n);r=device_alloc<double>(n);z=device_alloc<double>(n);
    p=device_alloc<double>(n);ap=device_alloc<double>(n);q=device_alloc<double>(n);w=device_alloc<double>(n);BK(cublasCreate(&h));
  }
  ~DeviceSystem(){if(h)cublasDestroy(h);cudaFree(W);cudaFree(U);cudaFree(R);cudaFree(E);cudaFree(b);cudaFree(Linv);
    cudaFree(cams);cudaFree(pts);cudaFree(offs);cudaFree(v);cudaFree(t);cudaFree(u);cudaFree(x);cudaFree(r);
    cudaFree(z);cudaFree(p);cudaFree(ap);cudaFree(q);cudaFree(w);}
  double dot(const double*a,const double*bv){double out;BK(cublasDdot(h,n,a,1,bv,1,&out));return out;}
};

static void apply_A(DeviceSystem&s,const double*in,double*out){
  scale_vec<<<s.grid,256>>>(s.n,in,s.E,s.v);CK(cudaMemset(s.t,0,(size_t)3*s.np*sizeof(double)));
  MFPass1<9,float><<<((int)s.no+255)/256,256>>>(s.W,s.cams,s.pts,s.v,(int)s.no,s.t);
  MFVinvApply<<<(s.np+255)/256,256>>>(s.R,s.t,s.np,s.u);
  MFPass2<9,float><<<s.nc,256>>>(s.W,s.pts,s.offs,s.u,s.U,s.v,(int)s.no,out);
  finish_vec<<<s.grid,256>>>(s.n,in,s.E,s.sigma,out);
}
static void lower(DeviceSystem&s,const double*x,double*y){block_transform<<<(s.nc+63)/64,64>>>(s.nc,s.Linv,x,y,0);}
static void upper(DeviceSystem&s,const double*x,double*y){block_transform<<<(s.nc+63)/64,64>>>(s.nc,s.Linv,x,y,1);}

static std::vector<double> build_Linv(int nc,double sigma,const std::vector<double>&U,const std::vector<double>&E){
  std::vector<double> out((size_t)81*nc);double min_eval=std::numeric_limits<double>::infinity();
  for(int c=0;c<nc;++c){Eigen::Matrix<double,9,9> H;
    for(int i=0;i<9;++i)for(int j=0;j<9;++j)H(i,j)=U[(size_t)81*c+9*i+j]*E[9*c+i]*E[9*c+j]+(i==j?sigma:0);
    H=(H+H.transpose()).eval()*0.5;Eigen::SelfAdjointEigenSolver<Eigen::Matrix<double,9,9>> eig(H);
    if(eig.info()!=Eigen::Success||eig.eigenvalues().minCoeff()<=0)throw std::runtime_error("non-SPD H block");
    min_eval=std::min(min_eval,eig.eigenvalues().minCoeff());Eigen::LLT<Eigen::Matrix<double,9,9>> llt(H);
    if(llt.info()!=Eigen::Success)throw std::runtime_error("H block LLT");
    Eigen::Matrix<double,9,9> I=Eigen::Matrix<double,9,9>::Identity();
    Eigen::Matrix<double,9,9> Li=llt.matrixL().solve(I);
    for(int i=0;i<9;++i)for(int j=0;j<9;++j)out[(size_t)81*c+9*i+j]=Li(i,j);
  }
  std::printf("HCC_FACTOR min_block_eigenvalue=%.17g\n",min_eval);return out;
}

struct Nystrom{
  int requested=0,rank=0,products=0;double setup_ms=0,theta_min=0,theta_max=0,factor_residual=0;
  double*Q=nullptr,*coeff=nullptr;
  Nystrom()=default;Nystrom(const Nystrom&)=delete;Nystrom&operator=(const Nystrom&)=delete;
  Nystrom(Nystrom&&o)noexcept{*this=std::move(o);}Nystrom&operator=(Nystrom&&o)noexcept{
    if(this!=&o){cudaFree(Q);cudaFree(coeff);requested=o.requested;rank=o.rank;products=o.products;setup_ms=o.setup_ms;
      theta_min=o.theta_min;theta_max=o.theta_max;factor_residual=o.factor_residual;Q=o.Q;coeff=o.coeff;o.Q=nullptr;o.coeff=nullptr;}
    return *this;
  }
  ~Nystrom(){cudaFree(Q);cudaFree(coeff);}
};

static Nystrom build_nystrom(DeviceSystem&s,int k,uint64_t seed){
  auto start=Clock::now();Nystrom out;out.requested=k;
  std::mt19937_64 rng(seed);std::normal_distribution<double> normal;
  Eigen::MatrixXd O(s.n,k);for(int j=0;j<k;++j)for(int i=0;i<s.n;++i)O(i,j)=normal(rng);
  Eigen::HouseholderQR<Eigen::MatrixXd> qr(O);O=qr.householderQ()*Eigen::MatrixXd::Identity(s.n,k);
  Eigen::MatrixXd Y(s.n,k),At(s.n,k);std::vector<double> host(s.n);
  for(int j=0;j<k;++j){
    CK(cudaMemcpy(s.q,O.col(j).data(),(size_t)s.n*sizeof(double),cudaMemcpyHostToDevice));
    upper(s,s.q,s.p);apply_A(s,s.p,s.ap);++out.products;lower(s,s.ap,s.z);
    CK(cudaMemcpy(host.data(),s.z,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToHost));
    for(int i=0;i<s.n;++i){At(i,j)=host[i];Y(i,j)=O(i,j)-host[i];}
  }
  Eigen::MatrixXd B=O.transpose()*Y;B=(B+B.transpose()).eval()*0.5;
  Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> eb(B);if(eb.info()!=Eigen::Success)throw std::runtime_error("Nystrom core eigen");
  double largest=eb.eigenvalues().maxCoeff();if(!(largest>0))throw std::runtime_error("Nystrom nonpositive core");
  std::vector<int> keep;for(int i=0;i<k;++i)if(eb.eigenvalues()[i]>largest*1e-12)keep.push_back(i);
  if(keep.empty())throw std::runtime_error("Nystrom empty core");
  Eigen::MatrixXd C(s.n,keep.size());
  for(size_t j=0;j<keep.size();++j)C.col(j)=Y*eb.eigenvectors().col(keep[j])/std::sqrt(eb.eigenvalues()[keep[j]]);
  Eigen::JacobiSVD<Eigen::MatrixXd> svd(C,Eigen::ComputeThinU);if(svd.info()!=Eigen::Success)throw std::runtime_error("Nystrom SVD");
  Eigen::VectorXd theta=svd.singularValues().array().square();Eigen::MatrixXd Q=svd.matrixU();
  std::vector<int> valid;for(int i=0;i<theta.size();++i)if(theta[i]>largest*1e-14)valid.push_back(i);
  if(valid.empty())throw std::runtime_error("Nystrom zero approximation");
  Eigen::MatrixXd Qv(s.n,valid.size());Eigen::VectorXd tv(valid.size());
  for(size_t j=0;j<valid.size();++j){Qv.col(j)=Q.col(valid[j]);tv[j]=theta[valid[j]];}
  out.theta_min=tv.minCoeff();out.theta_max=tv.maxCoeff();
  if(out.theta_max>=1.0+1e-10)throw std::runtime_error("Nystrom theta exceeds one: "+std::to_string(out.theta_max));
  for(int i=0;i<tv.size();++i)if(tv[i]>=1.0)tv[i]=std::nextafter(1.0,0.0);
  Eigen::MatrixXd interp=Qv*(tv.asDiagonal()*(Qv.transpose()*O));
  out.factor_residual=(interp-Y).norm()/std::max(Y.norm(),1e-300);out.rank=tv.size();
  std::vector<double> coeff(out.rank);for(int i=0;i<out.rank;++i)coeff[i]=tv[i]/(1-tv[i]);
  CK(cudaMalloc(&out.Q,(size_t)s.n*out.rank*sizeof(double)));CK(cudaMemcpy(out.Q,Qv.data(),(size_t)s.n*out.rank*sizeof(double),cudaMemcpyHostToDevice));
  out.coeff=device_copy(coeff);CK(cudaDeviceSynchronize());out.setup_ms=ms_since(start);return out;
}

struct SolveResult{
  int iterations=0,solve_products=0,sketch_products=0,restarts=0,rank=0;double residual=0,total_ms=0,sketch_ms=0,preconditioner_ms=0;
  double theta_min=0,theta_max=0,factor_residual=0;bool hit=false,negative=false,triggered=false;
};

static void precondition(DeviceSystem&s,const Nystrom*nys,double*r,double*z,double&time_ms){
  auto start=Clock::now();lower(s,r,s.q);
  if(nys&&nys->rank){
    double*small=s.w;double one=1,zero=0;
    BK(cublasDgemv(s.h,CUBLAS_OP_T,s.n,nys->rank,&one,nys->Q,s.n,s.q,1,&zero,small,1));
    scale_small<<<(nys->rank+31)/32,32>>>(nys->rank,nys->coeff,small);
    BK(cublasDgemv(s.h,CUBLAS_OP_N,s.n,nys->rank,&one,nys->Q,s.n,small,1,&one,s.q,1));
  }
  upper(s,s.q,z);CK(cudaDeviceSynchronize());time_ms+=ms_since(start);
}

static SolveResult solve(DeviceSystem&s,int rank,uint64_t seed,bool dispatch){
  SolveResult out;double nb=std::sqrt(s.dot(s.b,s.b));double one=1;
  CK(cudaMemset(s.x,0,(size_t)s.n*sizeof(double)));CK(cudaMemcpy(s.r,s.b,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));
  auto total_start=Clock::now();Nystrom nys;
  if(rank>0&&!dispatch){nys=build_nystrom(s,rank,seed);out.triggered=true;out.sketch_ms=nys.setup_ms;out.sketch_products=nys.products;out.rank=nys.rank;out.theta_min=nys.theta_min;out.theta_max=nys.theta_max;out.factor_residual=nys.factor_residual;}
  const Nystrom*active=out.triggered?&nys:nullptr;double rz=0;
  auto restart=[&](){precondition(s,active,s.r,s.z,out.preconditioner_ms);CK(cudaMemcpy(s.p,s.z,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));rz=s.dot(s.r,s.z);++out.restarts;};
  restart();out.residual=1;
  while(out.iterations<128){
    apply_A(s,s.p,s.ap);++out.solve_products;double pap=s.dot(s.p,s.ap);if(!(pap>0)){out.negative=true;break;}
    double alpha=rz/pap,minus=-alpha;BK(cublasDaxpy(s.h,s.n,&alpha,s.p,1,s.x,1));BK(cublasDaxpy(s.h,s.n,&minus,s.ap,1,s.r,1));++out.iterations;
    out.residual=std::sqrt(s.dot(s.r,s.r))/nb;
    if(out.residual<=0.5){
      apply_A(s,s.x,s.ap);++out.solve_products;double m=-1;BK(cublasDscal(s.h,s.n,&m,s.ap,1));BK(cublasDaxpy(s.h,s.n,&one,s.b,1,s.ap,1));
      out.residual=std::sqrt(s.dot(s.ap,s.ap))/nb;if(out.residual<=0.5){out.hit=true;break;}
      CK(cudaMemcpy(s.r,s.ap,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));restart();continue;
    }
    if(dispatch&&!out.triggered&&out.iterations==8){
      // A changed recurrence begins from the explicit residual.  Besides
      // making the restart mathematically self-contained, this charges the
      // same residual-replacement product required by a native integration.
      apply_A(s,s.x,s.ap);++out.solve_products;CK(cudaMemcpy(s.r,s.b,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));
      double minus_one=-1;BK(cublasDaxpy(s.h,s.n,&minus_one,s.ap,1,s.r,1));
      out.residual=std::sqrt(s.dot(s.r,s.r))/nb;
      if(out.residual<=0.5){out.hit=true;break;}
      if(rank>0){nys=build_nystrom(s,rank,seed);out.sketch_ms=nys.setup_ms;out.sketch_products=nys.products;out.rank=nys.rank;
        out.theta_min=nys.theta_min;out.theta_max=nys.theta_max;out.factor_residual=nys.factor_residual;active=&nys;}
      out.triggered=true;restart();continue;
    }
    precondition(s,active,s.r,s.z,out.preconditioner_ms);double next=s.dot(s.r,s.z),beta=next/rz;
    BK(cublasDscal(s.h,s.n,&beta,s.p,1));BK(cublasDaxpy(s.h,s.n,&one,s.z,1,s.p,1));rz=next;
  }
  CK(cudaDeviceSynchronize());out.total_ms=ms_since(total_start);return out;
}

int main(int argc,char**argv){try{
  if(argc!=2){std::fprintf(stderr,"usage: %s CAPTURE_DIR\n",argv[0]);return 2;}std::string dir=argv[1];if(dir.back()!='/')dir+='/';
  int cd,nc,np,no;double sigma,radius,eta;FILE*f=std::fopen((dir+"dimensions.txt").c_str(),"r");
  if(!f||std::fscanf(f,"%d %d %d %d %lf %lf %lf",&cd,&nc,&np,&no,&sigma,&radius,&eta)!=7||cd!=9||std::abs(eta-.5)>1e-15)throw std::runtime_error("dimensions/eta");if(f)std::fclose(f);
  auto W=load_host<float>(dir+"W",(size_t)27*no);auto U=load_host<double>(dir+"U",(size_t)81*nc);auto R=load_host<double>(dir+"R",(size_t)6*np);
  auto E=load_host<double>(dir+"E",(size_t)9*nc);auto b=load_host<double>(dir+"b",(size_t)9*nc);auto cams=load_host<int>(dir+"cams",no);
  auto pts=load_host<int>(dir+"points",no);auto offs=load_host<int>(dir+"offsets",nc+1);auto Linv=build_Linv(nc,sigma,U,E);
  DeviceSystem s(nc,np,no,sigma,W,U,R,E,b,Linv,cams,pts,offs);std::printf("SYSTEM nc=%d np=%d no=%d sigma=%.17g eta=%.17g\n",nc,np,no,sigma,eta);
  std::vector<int> ranks={0,4,8,16};if(const char*e=std::getenv("D12_ONLY_RANK"))ranks={std::atoi(e)};
  bool dispatch_only=std::getenv("D12_DISPATCH_ONLY")!=nullptr;
  for(int rank:ranks)for(int mode=0;mode<2;++mode){bool dispatch=mode==1;if(dispatch_only&&!dispatch&&rank>0)continue;
    int reps=rank?3:3;for(int rep=0;rep<reps;++rep){uint64_t seed=2026091300ULL+rep;SolveResult r=solve(s,rank,seed,dispatch);
      std::printf("NYSTROM mode=%s requested_rank=%d rep=%d seed=%llu triggered=%d effective_rank=%d iterations=%d solve_products=%d sketch_products=%d total_products=%d restarts=%d true_relative=%.17g hit=%d negative=%d total_ms=%.9g sketch_ms=%.9g preconditioner_ms=%.9g theta_min=%.17g theta_max=%.17g factor_residual=%.17g\n",
        dispatch?"dispatch8":"oracle",rank,rep,(unsigned long long)seed,(int)r.triggered,r.rank,r.iterations,r.solve_products,r.sketch_products,r.solve_products+r.sketch_products,r.restarts,r.residual,(int)r.hit,(int)r.negative,r.total_ms,r.sketch_ms,r.preconditioner_ms,r.theta_min,r.theta_max,r.factor_residual);std::fflush(stdout);
    }
  }
  return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"ERROR %s\n",e.what());return 1;}}
