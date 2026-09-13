#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <cusolverSp.h>
#include <cusolverSp_LOWLEVEL_PREVIEW.h>
#include <cusparse.h>
#include <suitesparse/cholmod.h>
#ifdef D11_HAVE_CUDSS
#include <cudss.h>
#endif
#include <Eigen/Sparse>
#include <Eigen/SparseCholesky>
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <numeric>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using Scalar=double;
#define CK(x) do{cudaError_t e_=(x);if(e_!=cudaSuccess){std::fprintf(stderr,"CUDA %s:%d: %s\n",__FILE__,__LINE__,cudaGetErrorString(e_));throw std::runtime_error("CUDA");}}while(0)
#define CSK(x) do{cusolverStatus_t e_=(x);if(e_!=CUSOLVER_STATUS_SUCCESS){std::fprintf(stderr,"CUSOLVER %s:%d: %d\n",__FILE__,__LINE__,(int)e_);throw std::runtime_error("CUSOLVER");}}while(0)
#define CPK(x) do{cusparseStatus_t e_=(x);if(e_!=CUSPARSE_STATUS_SUCCESS){std::fprintf(stderr,"CUSPARSE %s:%d: %d\n",__FILE__,__LINE__,(int)e_);throw std::runtime_error("CUSPARSE");}}while(0)
#ifdef D11_HAVE_CUDSS
#define DSK(x) do{cudssStatus_t e_=(x);if(e_!=CUDSS_STATUS_SUCCESS){std::fprintf(stderr,"CUDSS %s:%d: %d\n",__FILE__,__LINE__,(int)e_);throw std::runtime_error("CUDSS");}}while(0)
#endif
#include "reference.cuh"

using Clock=std::chrono::steady_clock;
static double seconds(Clock::time_point a){return std::chrono::duration<double>(Clock::now()-a).count();}

template<class T> static std::vector<T> load_host(const std::string& path,size_t n){
  std::vector<T> v(n);FILE*f=std::fopen(path.c_str(),"rb");
  if(!f||std::fread(v.data(),sizeof(T),n,f)!=n)throw std::runtime_error("read "+path);
  std::fclose(f);return v;
}
template<class T> static T* device_copy(const std::vector<T>& v){
  T*p=nullptr;CK(cudaMalloc(&p,v.size()*sizeof(T)));CK(cudaMemcpy(p,v.data(),v.size()*sizeof(T),cudaMemcpyHostToDevice));return p;
}
template<class T> static T* device_alloc(size_t n){T*p=nullptr;CK(cudaMalloc(&p,n*sizeof(T)));return p;}

struct DSU{
  std::vector<int> p,r;
  explicit DSU(int n):p(n),r(n,0){std::iota(p.begin(),p.end(),0);}
  int find(int x){while(x!=p[x]){p[x]=p[p[x]];x=p[x];}return x;}
  bool join(int a,int b){a=find(a);b=find(b);if(a==b)return false;if(r[a]<r[b])std::swap(a,b);p[b]=a;if(r[a]==r[b])++r[a];return true;}
};
struct Edge{int a,b,w;};

struct Topology{
  int nc=0,np=0,no=0;
  std::vector<int> poff,porder;
  std::vector<double> tree_dist;
  std::vector<int> selected2,selected3;
  long long graph_pairs=0;
  int graph_edges=0;
  double graph_seconds=0,tree_seconds=0,selection_seconds=0;
};
static size_t selected_pair_count(int q,int np,const std::vector<int>&selected,const std::vector<int>&cams){
  std::unordered_map<uint64_t,char> seen;seen.reserve((size_t)np*std::max(1,q*(q-1)/2));
  for(int p=0;p<np;++p)for(int a=0;a<q;++a){int oa=selected[(size_t)p*q+a];if(oa<0)continue;for(int b=a+1;b<q;++b){int ob=selected[(size_t)p*q+b];if(ob<0)continue;int ca=cams[oa],cb=cams[ob],lo=std::min(ca,cb),hi=std::max(ca,cb);seen[((uint64_t)(uint32_t)lo<<32)|(uint32_t)hi]=1;}}
  return seen.size();
}

static Topology build_topology(int nc,int np,int no,const std::vector<int>& cams,const std::vector<int>& pts){
  Topology t;t.nc=nc;t.np=np;t.no=no;t.poff.assign(np+1,0);
  for(int p:pts){if(p<0||p>=np)throw std::runtime_error("point id");++t.poff[p+1];}
  std::partial_sum(t.poff.begin(),t.poff.end(),t.poff.begin());
  t.porder.resize(no);std::vector<int> cur=t.poff;
  for(int k=0;k<no;++k)t.porder[cur[pts[k]]++]=k;

  auto begin=Clock::now();
  std::vector<int> weights((size_t)nc*nc,0);
  std::vector<int> unique;
  for(int p=0;p<np;++p){
    unique.clear();unique.reserve(t.poff[p+1]-t.poff[p]);
    for(int h=t.poff[p];h<t.poff[p+1];++h)unique.push_back(cams[t.porder[h]]);
    std::sort(unique.begin(),unique.end());unique.erase(std::unique(unique.begin(),unique.end()),unique.end());
    t.graph_pairs+=(long long)unique.size()*(unique.size()-1)/2;
    for(size_t a=0;a<unique.size();++a)for(size_t b=a+1;b<unique.size();++b){
      ++weights[(size_t)unique[a]*nc+unique[b]];++weights[(size_t)unique[b]*nc+unique[a]];
    }
  }
  std::vector<Edge> edges;
  for(int a=0;a<nc;++a)for(int b=a+1;b<nc;++b){int w=weights[(size_t)a*nc+b];if(w)edges.push_back({a,b,w});}
  t.graph_edges=(int)edges.size();t.graph_seconds=seconds(begin);

  begin=Clock::now();
  std::sort(edges.begin(),edges.end(),[](const Edge&x,const Edge&y){
    if(x.w!=y.w)return x.w>y.w;if(x.a!=y.a)return x.a<y.a;return x.b<y.b;
  });
  DSU dsu(nc);std::vector<std::vector<std::pair<int,double>>> tree(nc);int kept=0;
  for(const auto&e:edges)if(dsu.join(e.a,e.b)){
    double len=1.0/e.w;tree[e.a].push_back({e.b,len});tree[e.b].push_back({e.a,len});if(++kept==nc-1)break;
  }
  if(kept!=nc-1)throw std::runtime_error("camera graph disconnected");
  t.tree_dist.assign((size_t)nc*nc,0);
  for(int root=0;root<nc;++root){
    std::vector<int> parent(nc,-2),stack(1,root);parent[root]=-1;
    while(!stack.empty()){
      int u=stack.back();stack.pop_back();
      for(auto [v,len]:tree[u])if(parent[v]==-2){parent[v]=u;t.tree_dist[(size_t)root*nc+v]=t.tree_dist[(size_t)root*nc+u]+len;stack.push_back(v);}
    }
  }
  t.tree_seconds=seconds(begin);

  begin=Clock::now();t.selected2.assign((size_t)np*2,-1);t.selected3.assign((size_t)np*3,-1);
  struct Choice{double score;int cam,obs;};std::vector<Choice> choices;
  for(int p=0;p<np;++p){
    choices.clear();
    for(int h=t.poff[p];h<t.poff[p+1];++h){
      int obs=t.porder[h],c=cams[obs];bool duplicate=false;
      for(const auto&q:choices)if(q.cam==c){duplicate=true;break;}
      if(duplicate)continue;
      double sum=0;int count=0;
      for(int z=t.poff[p];z<t.poff[p+1];++z){int c2=cams[t.porder[z]];if(c2!=c){sum+=t.tree_dist[(size_t)c*nc+c2];++count;}}
      choices.push_back({count?sum/count:0.0,c,obs});
    }
    std::sort(choices.begin(),choices.end(),[](const Choice&a,const Choice&b){
      if(a.score!=b.score)return a.score<b.score;if(a.cam!=b.cam)return a.cam<b.cam;return a.obs<b.obs;
    });
    for(int k=0;k<std::min<int>(2,choices.size());++k)t.selected2[(size_t)p*2+k]=choices[k].obs;
    for(int k=0;k<std::min<int>(3,choices.size());++k)t.selected3[(size_t)p*3+k]=choices[k].obs;
  }
  t.selection_seconds=seconds(begin);return t;
}

using Block=std::array<double,81>;
struct MatrixBuild{
  Eigen::SparseMatrix<double> M;
  double seconds=0;
  long long selected_factors=0,offdiag_blocks=0;
};

static void transformed_rows(const std::vector<float>&W,long long no,const std::vector<double>&R,int p,int obs,double*Y){
  const double*r=&R[(size_t)6*p];
  for(int i=0;i<9;++i){
    double w0=W[(size_t)(3*i)*no+obs],w1=W[(size_t)(3*i+1)*no+obs],w2=W[(size_t)(3*i+2)*no+obs];
    double y0=w0/r[0];double y1=(w1-r[1]*y0)/r[3];double y2=(w2-r[2]*y0-r[4]*y1)/r[5];
    Y[3*i]=y0;Y[3*i+1]=y1;Y[3*i+2]=y2;
  }
}

static MatrixBuild make_preconditioner(int q,int nc,int np,long long no,double sigma,
    const std::vector<float>&W,const std::vector<double>&U,const std::vector<double>&R,
    const std::vector<double>&E,const std::vector<int>&cams,const std::vector<int>&pts,
    const std::vector<int>&selected){
  auto begin=Clock::now();std::vector<Block> diag(nc);for(auto&b:diag)b.fill(0);
  for(int c=0;c<nc;++c)for(int i=0;i<81;++i)diag[c][i]=U[(size_t)81*c+i];
  std::unordered_map<uint64_t,Block> off;off.reserve(std::min<long long>((long long)np*std::max(1,q*(q-1)/2),(long long)nc*(nc-1)/2));
  long long factors=0;
  for(int p=0;p<np;++p){
    int obs[3]={-1,-1,-1},m=0;double Y[3][27];
    for(int a=0;a<q;++a){int k=selected[(size_t)p*q+a];if(k>=0){obs[m]=k;transformed_rows(W,no,R,p,k,Y[m]);++m;++factors;}}
    for(int a=0;a<m;++a){int ca=cams[obs[a]];Block&d=diag[ca];
      for(int i=0;i<9;++i)for(int j=0;j<9;++j){double s=0;for(int k=0;k<3;++k)s+=Y[a][3*i+k]*Y[a][3*j+k];d[9*i+j]-=s;}
      for(int b=a+1;b<m;++b){int cb=cams[obs[b]],lo=std::min(ca,cb),hi=std::max(ca,cb);uint64_t key=(uint64_t)(uint32_t)lo<<32|(uint32_t)hi;
        auto[it,inserted]=off.try_emplace(key);if(inserted)it->second.fill(0);Block&z=it->second;
        const double*YL=ca<cb?Y[a]:Y[b];const double*YH=ca<cb?Y[b]:Y[a];
        for(int i=0;i<9;++i)for(int j=0;j<9;++j){double s=0;for(int k=0;k<3;++k)s+=YL[3*i+k]*YH[3*j+k];z[9*i+j]-=s;}
      }
    }
  }
  std::vector<Eigen::Triplet<double>> trip;
  trip.reserve((size_t)81*(nc+2*off.size()));
  for(int c=0;c<nc;++c)for(int i=0;i<9;++i)for(int j=0;j<9;++j){double v=diag[c][9*i+j]*E[9*c+i]*E[9*c+j]+(i==j?sigma:0);if(v!=0)trip.emplace_back(9*c+i,9*c+j,v);}
  for(const auto&kv:off){int lo=(int)(kv.first>>32),hi=(int)(uint32_t)kv.first;const Block&z=kv.second;
    for(int i=0;i<9;++i)for(int j=0;j<9;++j){double v=z[9*i+j]*E[9*lo+i]*E[9*hi+j];if(v!=0){trip.emplace_back(9*lo+i,9*hi+j,v);trip.emplace_back(9*hi+j,9*lo+i,v);}}
  }
  MatrixBuild out;out.M.resize(9*nc,9*nc);out.M.setFromTriplets(trip.begin(),trip.end());out.M.makeCompressed();
  out.seconds=seconds(begin);out.selected_factors=factors;out.offdiag_blocks=off.size();return out;
}

struct DeviceSystem{
  int nc,np;long long no;int n,grid;double sigma;
  float*W;double*U,*R,*E,*b,*v,*t,*u,*x,*r,*z,*p,*ap;int*cams,*pts,*offs;cublasHandle_t h;
  DeviceSystem(int nc_,int np_,long long no_,double sig,const std::vector<float>&Wh,const std::vector<double>&Uh,
      const std::vector<double>&Rh,const std::vector<double>&Eh,const std::vector<double>&bh,
      const std::vector<int>&ch,const std::vector<int>&ph,const std::vector<int>&oh):nc(nc_),np(np_),no(no_),n(9*nc_),grid((n+255)/256),sigma(sig){
    W=device_copy(Wh);U=device_copy(Uh);R=device_copy(Rh);E=device_copy(Eh);b=device_copy(bh);cams=device_copy(ch);pts=device_copy(ph);offs=device_copy(oh);
    v=device_alloc<double>(n);t=device_alloc<double>((size_t)3*np);u=device_alloc<double>((size_t)3*np);x=device_alloc<double>(n);r=device_alloc<double>(n);z=device_alloc<double>(n);p=device_alloc<double>(n);ap=device_alloc<double>(n);cublasCreate(&h);
  }
  ~DeviceSystem(){cublasDestroy(h);cudaFree(W);cudaFree(U);cudaFree(R);cudaFree(E);cudaFree(b);cudaFree(cams);cudaFree(pts);cudaFree(offs);cudaFree(v);cudaFree(t);cudaFree(u);cudaFree(x);cudaFree(r);cudaFree(z);cudaFree(p);cudaFree(ap);}
  double dot(double*a,double*bv){double z0;if(cublasDdot(h,n,a,1,bv,1,&z0)!=CUBLAS_STATUS_SUCCESS)throw std::runtime_error("dot");return z0;}
};
__global__ void scale_vec(int n,const double*x,const double*E,double*y){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[i]=x[i]*E[i];}
__global__ void finish_vec(int n,const double*x,const double*E,double sigma,double*y){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[i]=y[i]*E[i]+sigma*x[i];}
static void apply(DeviceSystem&s,double*in,double*out){
  scale_vec<<<s.grid,256>>>(s.n,in,s.E,s.v);CK(cudaMemset(s.t,0,(size_t)3*s.np*sizeof(double)));
  MFPass1<9,float><<<((int)s.no+255)/256,256>>>(s.W,s.cams,s.pts,s.v,(int)s.no,s.t);
  MFVinvApply<<<(s.np+255)/256,256>>>(s.R,s.t,s.np,s.u);
  MFPass2<9,float><<<s.nc,256>>>(s.W,s.pts,s.offs,s.u,s.U,s.v,(int)s.no,out);
  finish_vec<<<s.grid,256>>>(s.n,in,s.E,s.sigma,out);
}

struct SolveResult{int iterations=0,products=0;double residual=0,wall_ms=0,preconditioner_ms=0;bool hit=false,neg=false;};
using Solver=Eigen::SimplicialLDLT<Eigen::SparseMatrix<double>,Eigen::Lower,Eigen::AMDOrdering<int>>;
static SolveResult pcg(DeviceSystem&s,Solver&solver,double tol){
  SolveResult out;std::vector<double> hr(s.n),hz(s.n);double nb=std::sqrt(s.dot(s.b,s.b));
  auto pre=[&](){auto a=Clock::now();CK(cudaMemcpy(hr.data(),s.r,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToHost));Eigen::Map<Eigen::VectorXd> rv(hr.data(),s.n);Eigen::Map<Eigen::VectorXd> zv(hz.data(),s.n);zv=solver.solve(rv);if(solver.info()!=Eigen::Success)throw std::runtime_error("solve");CK(cudaMemcpy(s.z,hz.data(),(size_t)s.n*sizeof(double),cudaMemcpyHostToDevice));out.preconditioner_ms+=1e3*seconds(a);};
  CK(cudaMemset(s.x,0,(size_t)s.n*sizeof(double)));CK(cudaMemcpy(s.r,s.b,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));
  auto start=Clock::now();pre();CK(cudaMemcpy(s.p,s.z,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));double rz=s.dot(s.r,s.z);out.residual=1;
  for(;out.iterations<128;){
    apply(s,s.p,s.ap);++out.products;double pap=s.dot(s.p,s.ap);if(!(pap>0)){out.neg=true;break;}
    double alpha=rz/pap,minus=-alpha,one=1;cublasDaxpy(s.h,s.n,&alpha,s.p,1,s.x,1);cublasDaxpy(s.h,s.n,&minus,s.ap,1,s.r,1);++out.iterations;
    out.residual=std::sqrt(s.dot(s.r,s.r))/nb;
    if(out.residual<=tol||out.iterations==128){
      apply(s,s.x,s.ap);++out.products;double m=-1;cublasDscal(s.h,s.n,&m,s.ap,1);cublasDaxpy(s.h,s.n,&one,s.b,1,s.ap,1);out.residual=std::sqrt(s.dot(s.ap,s.ap))/nb;
      if(out.residual<=tol||out.iterations==128)break;
      CK(cudaMemcpy(s.r,s.ap,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));pre();CK(cudaMemcpy(s.p,s.z,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));rz=s.dot(s.r,s.z);continue;
    }
    pre();double next=s.dot(s.r,s.z),beta=next/rz;cublasDscal(s.h,s.n,&beta,s.p,1);cublasDaxpy(s.h,s.n,&one,s.z,1,s.p,1);rz=next;
  }
  CK(cudaDeviceSynchronize());out.wall_ms=1e3*seconds(start);out.hit=out.residual<=tol;return out;
}

struct GpuChol{
  int n=0,nnz=0;int*row=nullptr,*col=nullptr;double*val=nullptr;void*workspace=nullptr;
  int*perm=nullptr;double*rhs_perm=nullptr,*x_perm=nullptr;bool has_perm=false;
  cusolverSpHandle_t handle=nullptr;cusparseMatDescr_t descr=nullptr;csrcholInfo_t info=nullptr;
  double transfer_ms=0,symbolic_ms=0,factor_ms=0;size_t internal_bytes=0,workspace_bytes=0;
  explicit GpuChol(const Eigen::SparseMatrix<double>&M,const std::vector<int>&permutation={}){
    n=M.rows();Eigen::SparseMatrix<double,Eigen::RowMajor> lower=M.triangularView<Eigen::Lower>();lower.makeCompressed();nnz=lower.nonZeros();
    auto a=Clock::now();CK(cudaMalloc(&row,(size_t)(n+1)*sizeof(int)));CK(cudaMalloc(&col,(size_t)nnz*sizeof(int)));CK(cudaMalloc(&val,(size_t)nnz*sizeof(double)));
    CK(cudaMemcpy(row,lower.outerIndexPtr(),(size_t)(n+1)*sizeof(int),cudaMemcpyHostToDevice));CK(cudaMemcpy(col,lower.innerIndexPtr(),(size_t)nnz*sizeof(int),cudaMemcpyHostToDevice));CK(cudaMemcpy(val,lower.valuePtr(),(size_t)nnz*sizeof(double),cudaMemcpyHostToDevice));transfer_ms=1e3*seconds(a);
    if(!permutation.empty()){if((int)permutation.size()!=n)throw std::runtime_error("permutation size");has_perm=true;perm=device_copy(permutation);rhs_perm=device_alloc<double>(n);x_perm=device_alloc<double>(n);}
    CSK(cusolverSpCreate(&handle));CPK(cusparseCreateMatDescr(&descr));CPK(cusparseSetMatType(descr,CUSPARSE_MATRIX_TYPE_GENERAL));CPK(cusparseSetMatIndexBase(descr,CUSPARSE_INDEX_BASE_ZERO));CPK(cusparseSetMatFillMode(descr,CUSPARSE_FILL_MODE_LOWER));CPK(cusparseSetMatDiagType(descr,CUSPARSE_DIAG_TYPE_NON_UNIT));CSK(cusolverSpCreateCsrcholInfo(&info));
    a=Clock::now();CSK(cusolverSpXcsrcholAnalysis(handle,n,nnz,descr,row,col,info));CK(cudaDeviceSynchronize());symbolic_ms=1e3*seconds(a);
    CSK(cusolverSpDcsrcholBufferInfo(handle,n,nnz,descr,val,row,col,info,&internal_bytes,&workspace_bytes));CK(cudaMalloc(&workspace,workspace_bytes));
    std::vector<double> times;
    for(int rep=0;rep<3;++rep){a=Clock::now();CSK(cusolverSpDcsrcholFactor(handle,n,nnz,descr,val,row,col,info,workspace));CK(cudaDeviceSynchronize());times.push_back(1e3*seconds(a));int singular=-1;CSK(cusolverSpDcsrcholZeroPivot(handle,info,1e-14,&singular));if(singular>=0)throw std::runtime_error("GPU Cholesky zero pivot "+std::to_string(singular));}
    std::sort(times.begin(),times.end());factor_ms=times[1];
  }
  ~GpuChol(){if(info)cusolverSpDestroyCsrcholInfo(info);if(descr)cusparseDestroyMatDescr(descr);if(handle)cusolverSpDestroy(handle);cudaFree(row);cudaFree(col);cudaFree(val);cudaFree(workspace);cudaFree(perm);cudaFree(rhs_perm);cudaFree(x_perm);}
  void solve(const double*b,double*x);
};
__global__ void permutation_in(int n,const int*p,const double*x,double*y){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[i]=x[p[i]];}
__global__ void permutation_out(int n,const int*p,const double*x,double*y){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[p[i]]=x[i];}
void GpuChol::solve(const double*b,double*x){
  if(!has_perm){CSK(cusolverSpDcsrcholSolve(handle,n,b,x,info,workspace));return;}
  permutation_in<<<(n+255)/256,256>>>(n,perm,b,rhs_perm);CSK(cusolverSpDcsrcholSolve(handle,n,rhs_perm,x_perm,info,workspace));permutation_out<<<(n+255)/256,256>>>(n,perm,x_perm,x);
}

static SolveResult pcg_gpu(DeviceSystem&s,GpuChol&solver,double tol){
  SolveResult out;double nb=std::sqrt(s.dot(s.b,s.b));
  auto pre=[&](){auto a=Clock::now();solver.solve(s.r,s.z);CK(cudaDeviceSynchronize());out.preconditioner_ms+=1e3*seconds(a);};
  CK(cudaMemset(s.x,0,(size_t)s.n*sizeof(double)));CK(cudaMemcpy(s.r,s.b,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));
  auto start=Clock::now();pre();CK(cudaMemcpy(s.p,s.z,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));double rz=s.dot(s.r,s.z);out.residual=1;
  for(;out.iterations<128;){
    apply(s,s.p,s.ap);++out.products;double pap=s.dot(s.p,s.ap);if(!(pap>0)){out.neg=true;break;}
    double alpha=rz/pap,minus=-alpha,one=1;cublasDaxpy(s.h,s.n,&alpha,s.p,1,s.x,1);cublasDaxpy(s.h,s.n,&minus,s.ap,1,s.r,1);++out.iterations;out.residual=std::sqrt(s.dot(s.r,s.r))/nb;
    if(out.residual<=tol||out.iterations==128){
      apply(s,s.x,s.ap);++out.products;double m=-1;cublasDscal(s.h,s.n,&m,s.ap,1);cublasDaxpy(s.h,s.n,&one,s.b,1,s.ap,1);out.residual=std::sqrt(s.dot(s.ap,s.ap))/nb;
      if(out.residual<=tol||out.iterations==128)break;
      CK(cudaMemcpy(s.r,s.ap,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));pre();CK(cudaMemcpy(s.p,s.z,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));rz=s.dot(s.r,s.z);continue;
    }
    pre();double next=s.dot(s.r,s.z),beta=next/rz;cublasDscal(s.h,s.n,&beta,s.p,1);cublasDaxpy(s.h,s.n,&one,s.z,1,s.p,1);rz=next;
  }
  CK(cudaDeviceSynchronize());out.wall_ms=1e3*seconds(start);out.hit=out.residual<=tol;return out;
}

struct CholmodSolver{
  int n=0;cholmod_common common{};cholmod_sparse*A=nullptr;cholmod_factor*L=nullptr;
  cholmod_dense*B=nullptr,*X=nullptr,*Y=nullptr,*workE=nullptr;
  double symbolic_ms=0,factor_ms=0;size_t factor_nnz=0;
  explicit CholmodSolver(const Eigen::SparseMatrix<double>&M){
    n=M.rows();cholmod_start(&common);common.nmethods=1;common.method[0].ordering=CHOLMOD_AMD;common.postorder=1;
    Eigen::SparseMatrix<double> lower=M.triangularView<Eigen::Lower>();lower.makeCompressed();
    A=cholmod_allocate_sparse(n,n,lower.nonZeros(),1,1,-1,CHOLMOD_REAL,&common);if(!A)throw std::runtime_error("cholmod alloc");
    int*ap=(int*)A->p,*ai=(int*)A->i;double*ax=(double*)A->x;
    for(int k=0;k<=n;++k)ap[k]=lower.outerIndexPtr()[k];
    for(int k=0;k<lower.nonZeros();++k){ai[k]=lower.innerIndexPtr()[k];ax[k]=lower.valuePtr()[k];}
    auto start=Clock::now();L=cholmod_analyze(A,&common);symbolic_ms=1e3*seconds(start);if(!L)throw std::runtime_error("cholmod analyze");
    std::vector<double> times;
    for(int rep=0;rep<3;++rep){start=Clock::now();int ok=cholmod_factorize(A,L,&common);times.push_back(1e3*seconds(start));if(!ok||common.status!=CHOLMOD_OK)throw std::runtime_error("cholmod factor");}
    std::sort(times.begin(),times.end());factor_ms=times[1];factor_nnz=L->nzmax;
    B=cholmod_allocate_dense(n,1,n,CHOLMOD_REAL,&common);if(!B)throw std::runtime_error("cholmod rhs");
  }
  ~CholmodSolver(){if(X)cholmod_free_dense(&X,&common);if(Y)cholmod_free_dense(&Y,&common);if(workE)cholmod_free_dense(&workE,&common);if(B)cholmod_free_dense(&B,&common);if(L)cholmod_free_factor(&L,&common);if(A)cholmod_free_sparse(&A,&common);cholmod_finish(&common);}
  void solve(const double*b,double*x){std::memcpy(B->x,b,(size_t)n*sizeof(double));if(!cholmod_solve2(CHOLMOD_A,L,B,nullptr,&X,nullptr,&Y,&workE,&common))throw std::runtime_error("cholmod solve");std::memcpy(x,X->x,(size_t)n*sizeof(double));}
};

static SolveResult pcg_cholmod(DeviceSystem&s,CholmodSolver&solver,double tol){
  SolveResult out;std::vector<double> hr(s.n),hz(s.n);double nb=std::sqrt(s.dot(s.b,s.b));
  auto pre=[&](){auto a=Clock::now();CK(cudaMemcpy(hr.data(),s.r,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToHost));solver.solve(hr.data(),hz.data());CK(cudaMemcpy(s.z,hz.data(),(size_t)s.n*sizeof(double),cudaMemcpyHostToDevice));out.preconditioner_ms+=1e3*seconds(a);};
  CK(cudaMemset(s.x,0,(size_t)s.n*sizeof(double)));CK(cudaMemcpy(s.r,s.b,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));auto start=Clock::now();pre();CK(cudaMemcpy(s.p,s.z,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));double rz=s.dot(s.r,s.z);out.residual=1;
  for(;out.iterations<128;){apply(s,s.p,s.ap);++out.products;double pap=s.dot(s.p,s.ap);if(!(pap>0)){out.neg=true;break;}double alpha=rz/pap,minus=-alpha,one=1;cublasDaxpy(s.h,s.n,&alpha,s.p,1,s.x,1);cublasDaxpy(s.h,s.n,&minus,s.ap,1,s.r,1);++out.iterations;out.residual=std::sqrt(s.dot(s.r,s.r))/nb;
    if(out.residual<=tol||out.iterations==128){apply(s,s.x,s.ap);++out.products;double m=-1;cublasDscal(s.h,s.n,&m,s.ap,1);cublasDaxpy(s.h,s.n,&one,s.b,1,s.ap,1);out.residual=std::sqrt(s.dot(s.ap,s.ap))/nb;if(out.residual<=tol||out.iterations==128)break;CK(cudaMemcpy(s.r,s.ap,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));pre();CK(cudaMemcpy(s.p,s.z,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));rz=s.dot(s.r,s.z);continue;}
    pre();double next=s.dot(s.r,s.z),beta=next/rz;cublasDscal(s.h,s.n,&beta,s.p,1);cublasDaxpy(s.h,s.n,&one,s.z,1,s.p,1);rz=next;}
  CK(cudaDeviceSynchronize());out.wall_ms=1e3*seconds(start);out.hit=out.residual<=tol;return out;
}

#ifdef D11_HAVE_CUDSS
struct CudssSolver{
  int n=0,nnz=0;int*row=nullptr,*col=nullptr;double*val=nullptr;double*rhs=nullptr,*solution=nullptr;
  cudssHandle_t handle=nullptr;cudssConfig_t config=nullptr;cudssData_t data=nullptr;cudssMatrix_t A=nullptr,b=nullptr,x=nullptr;
  double transfer_ms=0,symbolic_ms=0,factor_ms=0;
  CudssSolver(const Eigen::SparseMatrix<double>&M,double*rhs_,double*solution_):rhs(rhs_),solution(solution_){
    n=M.rows();Eigen::SparseMatrix<double,Eigen::RowMajor> lower=M.triangularView<Eigen::Lower>();lower.makeCompressed();nnz=lower.nonZeros();
    auto start=Clock::now();CK(cudaMalloc(&row,(size_t)(n+1)*sizeof(int)));CK(cudaMalloc(&col,(size_t)nnz*sizeof(int)));CK(cudaMalloc(&val,(size_t)nnz*sizeof(double)));CK(cudaMemcpy(row,lower.outerIndexPtr(),(size_t)(n+1)*sizeof(int),cudaMemcpyHostToDevice));CK(cudaMemcpy(col,lower.innerIndexPtr(),(size_t)nnz*sizeof(int),cudaMemcpyHostToDevice));CK(cudaMemcpy(val,lower.valuePtr(),(size_t)nnz*sizeof(double),cudaMemcpyHostToDevice));transfer_ms=1e3*seconds(start);
    DSK(cudssCreate(&handle));DSK(cudssConfigCreate(&config));DSK(cudssDataCreate(handle,&data));
    DSK(cudssMatrixCreateDn(&b,n,1,n,rhs,CUDSS_R_64F,CUDSS_LAYOUT_COL_MAJOR));DSK(cudssMatrixCreateDn(&x,n,1,n,solution,CUDSS_R_64F,CUDSS_LAYOUT_COL_MAJOR));
    DSK(cudssMatrixCreateCsr(&A,n,n,nnz,row,nullptr,col,val,CUDSS_R_32I,CUDSS_R_32I,CUDSS_R_64F,CUDSS_MTYPE_SPD,CUDSS_MVIEW_LOWER,CUDSS_BASE_ZERO));
    start=Clock::now();DSK(cudssExecute(handle,CUDSS_PHASE_ANALYSIS,config,data,A,x,b));CK(cudaDeviceSynchronize());symbolic_ms=1e3*seconds(start);
    std::vector<double> times;for(int rep=0;rep<3;++rep){start=Clock::now();DSK(cudssExecute(handle,CUDSS_PHASE_FACTORIZATION,config,data,A,x,b));CK(cudaDeviceSynchronize());times.push_back(1e3*seconds(start));}
    std::sort(times.begin(),times.end());factor_ms=times[1];
  }
  ~CudssSolver(){if(A)cudssMatrixDestroy(A);if(b)cudssMatrixDestroy(b);if(x)cudssMatrixDestroy(x);if(data)cudssDataDestroy(handle,data);if(config)cudssConfigDestroy(config);if(handle)cudssDestroy(handle);cudaFree(row);cudaFree(col);cudaFree(val);}
  void solve(){DSK(cudssExecute(handle,CUDSS_PHASE_SOLVE,config,data,A,x,b));}
};

static SolveResult pcg_cudss(DeviceSystem&s,CudssSolver&solver,double tol){
  SolveResult out;double nb=std::sqrt(s.dot(s.b,s.b));auto pre=[&](){auto a=Clock::now();solver.solve();CK(cudaDeviceSynchronize());out.preconditioner_ms+=1e3*seconds(a);};
  CK(cudaMemset(s.x,0,(size_t)s.n*sizeof(double)));CK(cudaMemcpy(s.r,s.b,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));auto start=Clock::now();pre();CK(cudaMemcpy(s.p,s.z,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));double rz=s.dot(s.r,s.z);out.residual=1;
  for(;out.iterations<128;){apply(s,s.p,s.ap);++out.products;double pap=s.dot(s.p,s.ap);if(!(pap>0)){out.neg=true;break;}double alpha=rz/pap,minus=-alpha,one=1;cublasDaxpy(s.h,s.n,&alpha,s.p,1,s.x,1);cublasDaxpy(s.h,s.n,&minus,s.ap,1,s.r,1);++out.iterations;out.residual=std::sqrt(s.dot(s.r,s.r))/nb;
    if(out.residual<=tol||out.iterations==128){apply(s,s.x,s.ap);++out.products;double m=-1;cublasDscal(s.h,s.n,&m,s.ap,1);cublasDaxpy(s.h,s.n,&one,s.b,1,s.ap,1);out.residual=std::sqrt(s.dot(s.ap,s.ap))/nb;if(out.residual<=tol||out.iterations==128)break;CK(cudaMemcpy(s.r,s.ap,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));pre();CK(cudaMemcpy(s.p,s.z,(size_t)s.n*sizeof(double),cudaMemcpyDeviceToDevice));rz=s.dot(s.r,s.z);continue;}
    pre();double next=s.dot(s.r,s.z),beta=next/rz;cublasDscal(s.h,s.n,&beta,s.p,1);cublasDaxpy(s.h,s.n,&one,s.z,1,s.p,1);rz=next;}
  CK(cudaDeviceSynchronize());out.wall_ms=1e3*seconds(start);out.hit=out.residual<=tol;return out;
}
#endif

int main(int argc,char**argv){try{
  if(argc!=2){std::fprintf(stderr,"usage: %s CAPTURE_DIR\n",argv[0]);return 2;}std::string dir=argv[1];if(dir.back()!='/')dir+='/';
  int cd,nc,np,no;double sigma,radius,eta;FILE*f=std::fopen((dir+"dimensions.txt").c_str(),"r");
  if(!f||std::fscanf(f,"%d %d %d %d %lf %lf %lf",&cd,&nc,&np,&no,&sigma,&radius,&eta)!=7||cd!=9)throw std::runtime_error("dimensions");if(f)std::fclose(f);
  auto W=load_host<float>(dir+"W",(size_t)27*no);auto U=load_host<double>(dir+"U",(size_t)81*nc);auto R=load_host<double>(dir+"R",(size_t)6*np);
  auto E=load_host<double>(dir+"E",(size_t)9*nc);auto b=load_host<double>(dir+"b",(size_t)9*nc);auto cams=load_host<int>(dir+"cams",no);auto pts=load_host<int>(dir+"points",no);auto offs=load_host<int>(dir+"offsets",nc+1);
  Topology topology=build_topology(nc,np,no,cams,pts);
  size_t pairs2=selected_pair_count(2,np,topology.selected2,cams),pairs3=selected_pair_count(3,np,topology.selected3,cams);
  std::printf("TOPOLOGY nc=%d np=%d no=%d pair_visits=%lld graph_edges=%d selected_edges_q2=%zu selected_edges_q3=%zu graph_s=%.9g tree_s=%.9g selection_s=%.9g\n",nc,np,no,topology.graph_pairs,topology.graph_edges,pairs2,pairs3,topology.graph_seconds,topology.tree_seconds,topology.selection_seconds);std::fflush(stdout);
  if(std::getenv("D11_TOPOLOGY_ONLY"))return 0;
  DeviceSystem device(nc,np,no,sigma,W,U,R,E,b,cams,pts,offs);
  int only_q=std::getenv("D11_ONLY_Q")?std::atoi(std::getenv("D11_ONLY_Q")):-1;
  for(int q:{0,2,3}){
    if(const char* only=std::getenv("D11_ONLY_Q"))if(q!=std::atoi(only))continue;
    if(only_q>=0 && q!=only_q)continue;
    if(const char*only=std::getenv("D11_ONLY_Q")){if(q!=std::atoi(only))continue;}
    const std::vector<int> empty;const auto&sel=q==2?topology.selected2:(q==3?topology.selected3:empty);
    MatrixBuild mb=make_preconditioner(q,nc,np,no,sigma,W,U,R,E,cams,pts,sel);
    Solver solver;auto symbolic_start=Clock::now();solver.analyzePattern(mb.M);double symbolic_ms=1e3*seconds(symbolic_start);
    if(solver.info()!=Eigen::Success)throw std::runtime_error("symbolic q="+std::to_string(q));std::vector<double> factor_times;
    for(int rep=0;rep<3;++rep){auto a=Clock::now();solver.factorize(mb.M);double ms=1e3*seconds(a);if(solver.info()!=Eigen::Success)throw std::runtime_error("factor q="+std::to_string(q));factor_times.push_back(ms);}
    std::sort(factor_times.begin(),factor_times.end());long long lnnz=solver.matrixL().nestedExpression().nonZeros();double minD=solver.vectorD().minCoeff();
    SolveResult warm=pcg(device,solver,eta);(void)warm;
    for(int rep=0;rep<3;++rep){SolveResult sr=pcg(device,solver,eta);
      std::printf("GSP q=%d rep=%d eta=%.17g selected=%lld offdiag_blocks=%lld matrix_nnz=%lld factor_nnz=%lld min_D=%.17g assembly_ms=%.9g symbolic_ms=%.9g factor_ms=%.9g iterations=%d products=%d true_relative=%.17g hit=%d neg=%d solve_ms=%.9g preconditioner_ms=%.9g factor_plus_solve_ms=%.9g\n",
        q,rep,eta,mb.selected_factors,mb.offdiag_blocks,(long long)mb.M.nonZeros(),lnnz,minD,1e3*mb.seconds,symbolic_ms,factor_times[1],sr.iterations,sr.products,sr.residual,sr.hit,sr.neg,sr.wall_ms,sr.preconditioner_ms,factor_times[1]+sr.wall_ms);std::fflush(stdout);
    }
    if(q==3 && std::getenv("D11_CHOLMOD")){CholmodSolver chol(mb.M);SolveResult warm_chol=pcg_cholmod(device,chol,eta);(void)warm_chol;
      for(int rep=0;rep<3;++rep){SolveResult sr=pcg_cholmod(device,chol,eta);
        std::printf("GSP_CHOLMOD q=%d rep=%d eta=%.17g factor_nnz=%zu symbolic_ms=%.9g factor_ms=%.9g iterations=%d products=%d true_relative=%.17g hit=%d neg=%d solve_ms=%.9g preconditioner_ms=%.9g factor_plus_solve_ms=%.9g\n",q,rep,eta,chol.factor_nnz,chol.symbolic_ms,chol.factor_ms,sr.iterations,sr.products,sr.residual,sr.hit,sr.neg,sr.wall_ms,sr.preconditioner_ms,chol.factor_ms+sr.wall_ms);std::fflush(stdout);
      }
    }
    if(q==3 && std::getenv("D11_GPU_CHOL_AMD")){
      Eigen::PermutationMatrix<Eigen::Dynamic,Eigen::Dynamic,int> P=solver.permutationP();Eigen::SparseMatrix<double> pm=P*mb.M*P.transpose();pm.makeCompressed();std::vector<int> permutation(P.indices().data(),P.indices().data()+P.indices().size());
      GpuChol gpu(pm,permutation);SolveResult warm_gpu=pcg_gpu(device,gpu,eta);(void)warm_gpu;
      for(int rep=0;rep<3;++rep){SolveResult sr=pcg_gpu(device,gpu,eta);
        std::printf("GSP_GPU q=%d rep=%d eta=%.17g lower_nnz=%d transfer_ms=%.9g symbolic_ms=%.9g factor_ms=%.9g internal_bytes=%zu workspace_bytes=%zu iterations=%d products=%d true_relative=%.17g hit=%d neg=%d solve_ms=%.9g preconditioner_ms=%.9g factor_plus_solve_ms=%.9g\n",
          q,rep,eta,gpu.nnz,gpu.transfer_ms,gpu.symbolic_ms,gpu.factor_ms,gpu.internal_bytes,gpu.workspace_bytes,sr.iterations,sr.products,sr.residual,sr.hit,sr.neg,sr.wall_ms,sr.preconditioner_ms,gpu.factor_ms+sr.wall_ms);std::fflush(stdout);
      }
    }
    #ifdef D11_HAVE_CUDSS
    if(q==3 && std::getenv("D11_CUDSS")){CudssSolver ds(mb.M,device.r,device.z);SolveResult warm_ds=pcg_cudss(device,ds,eta);(void)warm_ds;
      for(int rep=0;rep<3;++rep){SolveResult sr=pcg_cudss(device,ds,eta);std::printf("GSP_CUDSS q=%d rep=%d eta=%.17g lower_nnz=%d transfer_ms=%.9g symbolic_ms=%.9g factor_ms=%.9g iterations=%d products=%d true_relative=%.17g hit=%d neg=%d solve_ms=%.9g preconditioner_ms=%.9g factor_plus_solve_ms=%.9g\n",q,rep,eta,ds.nnz,ds.transfer_ms,ds.symbolic_ms,ds.factor_ms,sr.iterations,sr.products,sr.residual,sr.hit,sr.neg,sr.wall_ms,sr.preconditioner_ms,ds.factor_ms+sr.wall_ms);std::fflush(stdout);}
    }
    #else
    if(q==3 && std::getenv("D11_CUDSS"))throw std::runtime_error("binary built without cuDSS; rerun build.py with D11_CUDSS_ROOT");
    #endif
  }
  return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"ERROR %s\n",e.what());return 1;}}
