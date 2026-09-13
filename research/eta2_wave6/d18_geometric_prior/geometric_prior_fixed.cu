#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <Eigen/Dense>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <numeric>
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
template<class T> static void save_host(const std::string&path,const std::vector<T>&v){FILE*f=std::fopen(path.c_str(),"wb");if(!f||std::fwrite(v.data(),sizeof(T),v.size(),f)!=v.size())throw std::runtime_error("write "+path);std::fclose(f);}

__global__ void scale_vec(int n,const double*x,const double*E,double*y){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[i]=x[i]*E[i];}
__global__ void finish_vec(int n,const double*x,const double*E,double sigma,double*y){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[i]=y[i]*E[i]+sigma*x[i];}
__global__ void block_transform(int nc,const double*B,const double*x,double*y,int transpose){
  int c=blockIdx.x*blockDim.x+threadIdx.x;if(c>=nc)return;const double*b=B+81*c;const double*v=x+9*c;double*out=y+9*c;
#pragma unroll
  for(int i=0;i<9;++i){double a=0;
#pragma unroll
    for(int j=0;j<9;++j)a+=(transpose?b[9*j+i]:b[9*i+j])*v[j];out[i]=a;}
}
__global__ void block_add(int nc,const double*B,const double*x,double*y){
  int c=blockIdx.x*blockDim.x+threadIdx.x;if(c>=nc)return;const double*b=B+81*c;const double*v=x+9*c;double*out=y+9*c;
#pragma unroll
  for(int i=0;i<9;++i){double a=0;
#pragma unroll
    for(int j=0;j<9;++j)a+=b[9*i+j]*v[j];out[i]+=a;}
}
__global__ void project_mask(int nc,const int*mask,double*x){int c=blockIdx.x*blockDim.x+threadIdx.x;if(c<nc&&mask[c])for(int j=0;j<8;++j)x[9*c+j]=0;}

struct DeviceSystem{
  int nc,np,n,grid;long long no;double sigma;
  float*W=nullptr;double*U=nullptr,*R=nullptr,*E=nullptr,*b=nullptr,*Linv=nullptr,*Delta=nullptr;
  int*cams=nullptr,*pts=nullptr,*offs=nullptr,*mask=nullptr;
  double*v=nullptr,*t=nullptr,*point_u=nullptr,*x=nullptr,*r=nullptr,*z=nullptr,*p=nullptr,*ap=nullptr,*q=nullptr,*w=nullptr;
  cublasHandle_t blas=nullptr;bool constrained=false;
  DeviceSystem(int nc_,int np_,long long no_,double sig,const std::vector<float>&Wh,
      const std::vector<double>&Uh,const std::vector<double>&Rh,const std::vector<double>&Eh,
      const std::vector<double>&bh,const std::vector<int>&ch,const std::vector<int>&ph,const std::vector<int>&oh)
      :nc(nc_),np(np_),n(9*nc_),grid((n+255)/256),no(no_),sigma(sig){
    W=device_copy(Wh);U=device_copy(Uh);R=device_copy(Rh);E=device_copy(Eh);b=device_copy(bh);
    cams=device_copy(ch);pts=device_copy(ph);offs=device_copy(oh);Linv=device_alloc<double>((size_t)81*nc);
    Delta=device_alloc<double>((size_t)81*nc);mask=device_alloc<int>(nc);v=device_alloc<double>(n);t=device_alloc<double>((size_t)3*np);
    point_u=device_alloc<double>((size_t)3*np);x=device_alloc<double>(n);r=device_alloc<double>(n);z=device_alloc<double>(n);
    p=device_alloc<double>(n);ap=device_alloc<double>(n);q=device_alloc<double>(n);w=device_alloc<double>(n);BK(cublasCreate(&blas));
  }
  ~DeviceSystem(){if(blas)cublasDestroy(blas);for(void*p0:{(void*)W,(void*)U,(void*)R,(void*)E,(void*)b,(void*)Linv,(void*)Delta,(void*)cams,(void*)pts,(void*)offs,(void*)mask,(void*)v,(void*)t,(void*)point_u,(void*)x,(void*)r,(void*)z,(void*)p,(void*)ap,(void*)q,(void*)w})cudaFree(p0);}
  void set_arm(const std::vector<double>&delta,const std::vector<double>&linv,const std::vector<int>&masked,bool constraint){
    CK(cudaMemcpy(Delta,delta.data(),delta.size()*8,cudaMemcpyHostToDevice));CK(cudaMemcpy(Linv,linv.data(),linv.size()*8,cudaMemcpyHostToDevice));
    CK(cudaMemcpy(mask,masked.data(),masked.size()*4,cudaMemcpyHostToDevice));constrained=constraint;
  }
  void project(double*x0){if(constrained)project_mask<<<(nc+255)/256,256>>>(nc,mask,x0);}
  double dot(const double*a,const double*c){double out;BK(cublasDdot(blas,n,a,1,c,1,&out));return out;}
};

static void apply_A(DeviceSystem&s,const double*in,double*out){
  scale_vec<<<s.grid,256>>>(s.n,in,s.E,s.v);CK(cudaMemset(s.t,0,(size_t)3*s.np*sizeof(double)));
  MFPass1<9,float><<<((int)s.no+255)/256,256>>>(s.W,s.cams,s.pts,s.v,(int)s.no,s.t);
  MFVinvApply<<<(s.np+255)/256,256>>>(s.R,s.t,s.np,s.point_u);
  MFPass2<9,float><<<s.nc,256>>>(s.W,s.pts,s.offs,s.point_u,s.U,s.v,(int)s.no,out);
  finish_vec<<<s.grid,256>>>(s.n,in,s.E,s.sigma,out);block_add<<<(s.nc+63)/64,64>>>(s.nc,s.Delta,in,out);s.project(out);
}
static void precondition(DeviceSystem&s,const double*in,double*out){
  block_transform<<<(s.nc+63)/64,64>>>(s.nc,s.Linv,in,s.q,0);block_transform<<<(s.nc+63)/64,64>>>(s.nc,s.Linv,s.q,out,1);s.project(out);
}

struct PriorGeometry{std::vector<Eigen::Matrix<double,8,8>> blocks;std::vector<double> minima;std::vector<int> gate;double mu_ref=0;int top_camera=-1,weakest_camera=-1;double raw_ratio=0,top_energy_fraction=0;};
static PriorGeometry prior_geometry(int nc,long long no,const std::vector<double>&E,const std::vector<double>&raw,double radius,DeviceSystem&s){
  double*dB=device_alloc<double>((size_t)81*nc);CK(cudaMemset(dB,0,(size_t)81*nc*8));
  MFBlockSchurCM<9,float><<<nc,32>>>(s.W,s.pts,s.offs,s.R,(int)no,dB);MFBlockAddHcc<9><<<(nc+255)/256,256>>>(s.U,nc,dB);
  std::vector<double>B((size_t)81*nc);CK(cudaMemcpy(B.data(),dB,B.size()*8,cudaMemcpyDeviceToHost));cudaFree(dB);
  PriorGeometry out;out.gate.assign(nc,0);out.blocks.resize(nc);out.minima.resize(nc);std::vector<double> maxima;maxima.reserve(nc);
  for(int c=0;c<nc;++c){Eigen::Matrix<double,8,8>A;for(int i=0;i<8;++i)for(int j=0;j<8;++j)A(i,j)=.5*(B[(size_t)81*c+9*i+j]+B[(size_t)81*c+9*j+i])*E[9*c+i]*E[9*c+j];out.blocks[c]=A;
    Eigen::SelfAdjointEigenSolver<Eigen::Matrix<double,8,8>> es(A);if(es.info()!=Eigen::Success)throw std::runtime_error("block eigensolve");out.minima[c]=es.eigenvalues()[0];maxima.push_back(es.eigenvalues()[7]);}
  std::sort(maxima.begin(),maxima.end());out.mu_ref=maxima[maxima.size()/2];if(maxima.size()%2==0)out.mu_ref=.5*(out.mu_ref+maxima[maxima.size()/2-1]);
  long double all=0,top=-1;for(int c=0;c<nc;++c){long double q=0;for(int j=0;j<8;++j){long double x=raw[9*c+j];q+=x*x;}all+=q;if(q>top){top=q;out.top_camera=c;}}
  out.weakest_camera=std::min_element(out.minima.begin(),out.minima.end())-out.minima.begin();out.raw_ratio=std::sqrt((double)all)/radius;out.top_energy_fraction=(double)(top/std::max(all,(long double)1e-300));
  if(out.raw_ratio>100&&out.top_energy_fraction>.99&&out.top_camera==out.weakest_camera)out.gate[out.top_camera]=1;return out;
}

static std::vector<double> build_delta(const PriorGeometry&g,double dose,bool constraint){
  int nc=g.gate.size();std::vector<double>out((size_t)81*nc,0.0);if(constraint||dose==0)return out;
  for(int c=0;c<nc;++c)if(g.gate[c]){Eigen::SelfAdjointEigenSolver<Eigen::Matrix<double,8,8>> es(g.blocks[c]);if(es.info()!=Eigen::Success)throw std::runtime_error("prior eigensolve");
    Eigen::Array<double,8,1> d=(dose*g.mu_ref-es.eigenvalues().array()).max(0.0);Eigen::Matrix<double,8,8>D=es.eigenvectors()*d.matrix().asDiagonal()*es.eigenvectors().transpose();
    for(int i=0;i<8;++i)for(int j=0;j<8;++j)out[(size_t)81*c+9*i+j]=D(i,j);}
  return out;
}

static std::vector<double> build_linv(int nc,double sigma,const std::vector<double>&U,const std::vector<double>&E,const std::vector<double>&Delta,const std::vector<int>&gate,bool constraint){
  std::vector<double>out((size_t)81*nc,0.0);
  for(int c=0;c<nc;++c){Eigen::Matrix<double,9,9>H=Eigen::Matrix<double,9,9>::Zero();if(constraint&&gate[c])H.setIdentity();else for(int i=0;i<9;++i)for(int j=0;j<9;++j)H(i,j)=U[(size_t)81*c+9*i+j]*E[9*c+i]*E[9*c+j]+Delta[(size_t)81*c+9*i+j]+(i==j?sigma:0);
    H=(H+H.transpose()).eval()*.5;Eigen::LLT<Eigen::Matrix<double,9,9>>llt(H);if(llt.info()!=Eigen::Success)throw std::runtime_error("prior Hcc LLT");Eigen::Matrix<double,9,9>Li=llt.matrixL().solve(Eigen::Matrix<double,9,9>::Identity());
    for(int i=0;i<9;++i)for(int j=0;j<9;++j)out[(size_t)81*c+9*i+j]=Li(i,j);}
  return out;
}

struct Result{int updates=0,products=0;double recursive_relative=1,true_relative=1,total_ms=0,min_curvature=std::numeric_limits<double>::infinity();bool hit=false,negative=false;std::vector<double>solution;};
static Result solve(DeviceSystem&s,double eta){
  Result out;auto start=Clock::now();CK(cudaMemset(s.x,0,(size_t)s.n*8));CK(cudaMemcpy(s.r,s.b,(size_t)s.n*8,cudaMemcpyDeviceToDevice));s.project(s.r);
  double nb=std::sqrt(s.dot(s.r,s.r));precondition(s,s.r,s.z);double rz=s.dot(s.r,s.z);CK(cudaMemcpy(s.p,s.z,(size_t)s.n*8,cudaMemcpyDeviceToDevice));
  while(out.updates<128){apply_A(s,s.p,s.ap);++out.products;double pap=s.dot(s.p,s.ap),pp=s.dot(s.p,s.p);out.min_curvature=std::min(out.min_curvature,pap/std::max(pp,1e-300));if(!(pap>1e-14*pp)){out.negative=true;break;}
    double alpha=rz/pap,minus=-alpha;BK(cublasDaxpy(s.blas,s.n,&alpha,s.p,1,s.x,1));BK(cublasDaxpy(s.blas,s.n,&minus,s.ap,1,s.r,1));++out.updates;out.recursive_relative=std::sqrt(s.dot(s.r,s.r))/nb;if(out.recursive_relative<=eta)break;
    precondition(s,s.r,s.z);double next=s.dot(s.r,s.z),beta=next/rz;BK(cublasDscal(s.blas,s.n,&beta,s.p,1));double one=1;BK(cublasDaxpy(s.blas,s.n,&one,s.z,1,s.p,1));rz=next;
  }
  apply_A(s,s.x,s.ap);++out.products;CK(cudaMemcpy(s.w,s.b,(size_t)s.n*8,cudaMemcpyDeviceToDevice));s.project(s.w);double minus=-1;BK(cublasDaxpy(s.blas,s.n,&minus,s.ap,1,s.w,1));out.true_relative=std::sqrt(s.dot(s.w,s.w))/nb;out.hit=out.true_relative<=eta;CK(cudaDeviceSynchronize());out.total_ms=elapsed_ms(start);out.solution.resize(s.n);CK(cudaMemcpy(out.solution.data(),s.x,(size_t)s.n*8,cudaMemcpyDeviceToHost));return out;
}

int main(int argc,char**argv){try{
  if(argc!=3){std::fprintf(stderr,"usage: %s CAPTURE_DIR OUTPUT_DIR\n",argv[0]);return 2;}std::string dir=argv[1],outdir=argv[2];if(dir.back()!='/')dir+='/';if(outdir.back()!='/')outdir+='/';
  int cd,nc,np,no;double sigma,radius,eta;FILE*f=std::fopen((dir+"dimensions.txt").c_str(),"r");if(!f||std::fscanf(f,"%d %d %d %d %lf %lf %lf",&cd,&nc,&np,&no,&sigma,&radius,&eta)!=7||cd!=9)throw std::runtime_error("dimensions");if(f)std::fclose(f);
  if(!(radius>0)){f=std::fopen((dir+"registered_radius.txt").c_str(),"r");if(!f||std::fscanf(f,"%lf",&radius)!=1||!(radius>0)||!std::isfinite(radius))throw std::runtime_error("registered radius");if(f)std::fclose(f);}
  auto W=load_host<float>(dir+"W",(size_t)27*no);auto U=load_host<double>(dir+"U",(size_t)81*nc);auto R=load_host<double>(dir+"R",(size_t)6*np);auto E=load_host<double>(dir+"E",(size_t)9*nc);auto b=load_host<double>(dir+"b",(size_t)9*nc);auto cams=load_host<int>(dir+"cams",no);auto pts=load_host<int>(dir+"points",no);auto offs=load_host<int>(dir+"offsets",nc+1);auto raw=load_host<double>(dir+"eta2_raw_scaled.f64",(size_t)9*nc);
  DeviceSystem s(nc,np,no,sigma,W,U,R,E,b,cams,pts,offs);auto g=prior_geometry(nc,no,E,raw,radius,s);int ng=std::accumulate(g.gate.begin(),g.gate.end(),0);
  std::printf("SYSTEM nc=%d np=%d no=%d sigma=%.17g eta=%.17g gated=%d mu_ref=%.17g top_camera=%d weakest_camera=%d raw_ratio=%.17g top_energy_fraction=%.17g ids=",nc,np,no,sigma,eta,ng,g.mu_ref,g.top_camera,g.weakest_camera,g.raw_ratio,g.top_energy_fraction);for(int c=0;c<nc;++c)if(g.gate[c])std::printf("%d,",c);std::printf("\n");
  struct Arm{const char*name;double dose;bool constraint;};std::vector<Arm>arms={{"0",0,false},{"01",.1,false},{"1",1,false},{"10",10,false},{"100",100,false},{"inf",0,true}};
  for(const auto&arm:arms){auto delta=build_delta(g,arm.dose,arm.constraint);auto linv=build_linv(nc,sigma,U,E,delta,g.gate,arm.constraint);s.set_arm(delta,linv,g.gate,arm.constraint);
    for(int warm=0;warm<2;++warm)(void)solve(s,eta);
    for(int rep=0;rep<3;++rep){auto r=solve(s,eta);save_host(outdir+"solution-a"+arm.name+"-r"+std::to_string(rep)+".f64",r.solution);double gated2=0,free2=0;for(int c=0;c<nc;++c)for(int j=0;j<8;++j)(g.gate[c]?gated2:free2)+=r.solution[9*c+j]*r.solution[9*c+j];
      std::printf("D18 arm=%s rep=%d updates=%d products=%d recursive_relative=%.17g true_relative=%.17g hit=%d negative=%d min_curvature=%.17g total_ms=%.9g raw_norm=%.17g gated_energy_fraction=%.17g\n",arm.name,rep,r.updates,r.products,r.recursive_relative,r.true_relative,(int)r.hit,(int)r.negative,r.min_curvature,r.total_ms,std::sqrt(gated2+free2),gated2/std::max(gated2+free2,1e-300));std::fflush(stdout);}
  }
  return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"ERROR %s\n",e.what());return 1;}}
