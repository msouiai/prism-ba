#define OCA_CORE_LIBRARY 1
#define PRISM_OWNED_WORKSPACE_TESTING 1
#include "build/owned-workspace.cu"

#include <array>
#include <bit>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <thread>

namespace {
struct Fixture {
  std::vector<int> ci,pi;
  std::vector<double> uv,R,t,X,f,k1,k2;
  oca::Problem problem;
  oca::State state;
  Fixture(int nc,int np) {
    R.resize(9*nc);t.assign(3*nc,0.0);f.assign(nc,800.0);k1.assign(nc,0.0);k2.assign(nc,0.0);
    for(int c=0;c<nc;++c){R[9*c]=R[9*c+4]=R[9*c+8]=1.0;t[3*c]=0.08*c;}
    X.resize(3*np);
    for(int p=0;p<np;++p){X[3*p]=0.02*(p%5)-0.04;X[3*p+1]=0.015*(p%7)-0.045;X[3*p+2]=-4.0-0.03*p;}
    for(int p=0;p<np;++p)for(int c=0;c<nc;++c){
      ci.push_back(c);pi.push_back(p);const double px=X[3*p]+t[3*c],py=X[3*p+1],pz=X[3*p+2];
      uv.push_back(-f[c]*px/pz+1e-3*((p+c)%3-1));uv.push_back(-f[c]*py/pz-1e-3*((2*p+c)%3-1));
    }
    problem.num_cameras=nc;problem.num_points=np;problem.num_observations=(int)ci.size();
    problem.camera_index=ci.data();problem.point_index=pi.data();problem.observations=uv.data();Bind();
  }
  Fixture(const Fixture& q):ci(q.ci),pi(q.pi),uv(q.uv),R(q.R),t(q.t),X(q.X),f(q.f),k1(q.k1),k2(q.k2),problem(q.problem){Bind();}
  void Bind(){problem.camera_index=ci.data();problem.point_index=pi.data();problem.observations=uv.data();state={R.data(),t.data(),X.data(),f.data(),k1.data(),k2.data()};}
};
std::mutex observations_mutex;
std::vector<std::pair<std::thread::id,PrismOwnedWorkspaceSnapshot>> observations;
void Observe(const PrismOwnedWorkspaceSnapshot& s){std::lock_guard<std::mutex> lock(observations_mutex);observations.push_back({std::this_thread::get_id(),s});}
void RequireAt(bool ok,int line){if(!ok){std::fprintf(stderr,"workspace test failed at line %d\n",line);std::abort();}}
#define Require(x) RequireAt((x),__LINE__)
template<class T> bool BitsEqual(const T&a,const T&b){return std::memcmp(&a,&b,sizeof(T))==0;}
template<class T> bool VectorBitsEqual(const std::vector<T>&a,const std::vector<T>&b){return a.size()==b.size()&&(a.empty()||std::memcmp(a.data(),b.data(),a.size()*sizeof(T))==0);}
bool Equal(const Fixture&a,const Fixture&b){return VectorBitsEqual(a.R,b.R)&&VectorBitsEqual(a.t,b.t)&&VectorBitsEqual(a.X,b.X)&&VectorBitsEqual(a.f,b.f)&&VectorBitsEqual(a.k1,b.k1)&&VectorBitsEqual(a.k2,b.k2);}
bool Equal(const oca::Result&a,const oca::Result&b){
  return a.success==b.success&&a.iterations==b.iterations&&BitsEqual(a.initial_cost,b.initial_cost)&&BitsEqual(a.final_cost,b.final_cost)&&VectorBitsEqual(a.cost_per_iteration,b.cost_per_iteration)&&BitsEqual(a.final_lambda,b.final_lambda)&&BitsEqual(a.initial_median_error_px,b.initial_median_error_px)&&BitsEqual(a.final_median_error_px,b.final_median_error_px)&&a.message==b.message;
}
}

int main(){
  setenv("OCA_W6_DETERMINISTIC","1",1);setenv("OCA_CLASSICAL_LM","1",1);setenv("OCA_COMPACT_FRAGMENTS","2",1);setenv("OCA_FORCE_UNSHARED","1",1);setenv("OCA_PCG","1",1);int devices=0;if(cudaGetDeviceCount(&devices)!=cudaSuccess||devices<1)return 77;
  const int caller_target=devices>1?1:0;CUDA_CHECK(cudaSetDevice(caller_target));int caller=-1;CUDA_CHECK(cudaGetDevice(&caller));
  oca::Options opt;opt.gpu_index=0;opt.refine_intrinsics=true;opt.initial_lambda=.1;opt.max_iterations=1;opt.cg_checkpoints={1};opt.num_shifts=1;opt.max_consecutive_failures=0;opt.func_tolerance=0;
  Fixture a0(2,9),b0(3,17),a_ref(a0),b_ref(b0),a_run(a0),b_run(b0);
  auto ar=oca::Solve(a_ref.problem,opt,&a_ref.state);auto br=oca::Solve(b_ref.problem,opt,&b_ref.state);
  if(!ar.success||!br.success)std::fprintf(stderr,"serial a=%d %s b=%d %s\n",ar.success,ar.message.c_str(),br.success,br.message.c_str());Require(ar.success&&br.success);
  prism_owned_workspace_observer=&Observe;observations.clear();oca::Result ac,bc;int after_a=-1,after_b=-1;
  std::thread ta([&]{CUDA_CHECK(cudaSetDevice(caller_target));ac=oca::Solve(a_run.problem,opt,&a_run.state);CUDA_CHECK(cudaGetDevice(&after_a));});
  std::thread tb([&]{CUDA_CHECK(cudaSetDevice(caller_target));bc=oca::Solve(b_run.problem,opt,&b_run.state);CUDA_CHECK(cudaGetDevice(&after_b));});ta.join();tb.join();
  Require(Equal(ar,ac)&&Equal(br,bc)&&Equal(a_ref,a_run)&&Equal(b_ref,b_run));Require(observations.size()==2);
  const auto &x=observations[0].second,&y=observations[1].second;
  const std::array<const void*,7> xp={x.blas_partials,x.blas_output,x.cost_partials,x.cost_output,x.bounded_result,x.count_output,x.block_diag_output};
  const std::array<const void*,7> yp={y.blas_partials,y.blas_output,y.cost_partials,y.cost_output,y.bounded_result,y.count_output,y.block_diag_output};
  for(size_t i=0;i<xp.size();++i)Require(xp[i]&&yp[i]&&xp[i]!=yp[i]);
  Require(after_a==caller_target&&after_b==caller_target);int after=-1;CUDA_CHECK(cudaGetDevice(&after));Require(after==caller);
  prism_owned_workspace_observer=nullptr;prism_owned_workspace_fail_after=3;Fixture fail(a0);auto fr=oca::Solve(fail.problem,opt,&fail.state);Require(!fr.success);CUDA_CHECK(cudaGetDevice(&after));Require(after==caller);
  return 0;
}
