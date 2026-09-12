#pragma once
#include "geometry.h"
#include "attempt_trace.h"

namespace prism_coarse {
constexpr int MAX_RANK=56, TRI=1596, POINT_WARPS=4, POINT_THREADS=128;

__global__ void CameraMatrix(int nc,int rank,const int* label,const int* local_rank,const int* offset,
 const double* Z,const double* E,const double* H,double lambda,double* Ac){
  int c=blockIdx.x,k=label[c],r=local_rank[k],a=threadIdx.x/r,b=threadIdx.x%r;
  if(c>=nc||a>=r||b>a)return;
  double s=0;for(int i=0;i<9;++i){
    double x=Z[(9ul*c+i)*7+a],y=Z[(9ul*c+i)*7+b];s+=lambda*x*y;
    for(int j=0;j<9;++j)s+=x*E[9*c+i]*H[81ul*c+9*i+j]*E[9*c+j]*Z[(9ul*c+j)*7+b];
  }
  atomicAdd(Ac+(offset[k]+a)*rank+offset[k]+b,s);
}

// Each warp gathers one point's actual observing clusters. No npoint-by-rank
// buffer or AZ allocation: only 3*56 values per warp and a block accumulator.
template<class Fragment>
__global__ void PointMatrix(int np,int no,const int* poff,const int* plist,const int* ci,
 const int* obs_slot,const Fragment* W,const double* R,const double* E,const double* Z,
 const int* label,const int* local_rank,const int* offset,int K,int rank,
 const int* pair_i,const int* pair_j,double* partial){
  __shared__ double T[POINT_WARPS][3*MAX_RANK];
  __shared__ double sums[TRI];
  __shared__ int slots[POINT_WARPS][MAX_RANK];
  int tid=threadIdx.x,lane=tid%32,warp=tid/32;
  for(int a=tid;a<TRI;a+=POINT_THREADS)sums[a]=0;
  __syncthreads();
  for(int p=blockIdx.x*POINT_WARPS+warp;p<np;p+=gridDim.x*POINT_WARPS){
    for(int a=lane;a<3*MAX_RANK;a+=32)T[warp][a]=0;
    __syncwarp();unsigned mask=0;
    for(int q=poff[p];q<poff[p+1];++q){
      int o=plist[q],c=ci[o],k=label[c],r=local_rank[k],s=obs_slot?obs_slot[o]:o;mask|=1u<<k;
      for(int a=lane;a<3*r;a+=32){int mode=a/3,j=a%3;double value=0;
        for(int i=0;i<9;++i)value+=(double)W[(3ul*i+j)*no+s]*E[9*c+i]*Z[(9ul*c+i)*7+mode];
        T[warp][3*(7*k+mode)+j]+=value;
      }
      __syncwarp();
    }
    int count=0;for(int k=0;k<K;++k)if(mask&(1u<<k))for(int a=0;a<local_rank[k];++a){if(lane==0)slots[warp][count]=7*k+a;++count;}
    __syncwarp();
    const double* f=R+6ul*p;
    for(int q=lane;q<count;q+=32){int a=3*slots[warp][q];double y0=T[warp][a]/f[0];double y1=(T[warp][a+1]-f[1]*y0)/f[3];double y2=(T[warp][a+2]-f[2]*y0-f[4]*y1)/f[5];T[warp][a]=y0;T[warp][a+1]=y1;T[warp][a+2]=y2;}
    __syncwarp();
    for(int q=lane;q<count*(count+1)/2;q+=32){
      int a=slots[warp][pair_i[q]],b=slots[warp][pair_j[q]];
      double value=0;for(int j=0;j<3;++j)value+=T[warp][3*a+j]*T[warp][3*b+j];
      int ga=offset[a/7]+a%7,gb=offset[b/7]+b%7;
      // Cluster ordering makes ga>=gb, including rank-six singleton blocks.
      atomicAdd(sums+ga*(ga+1)/2+gb,-value);
    }
    __syncwarp();
  }
  __syncthreads();
  for(int q=tid;q<rank*(rank+1)/2;q+=POINT_THREADS)partial[(size_t)blockIdx.x*TRI+q]=sums[q];
}
__global__ void FinishMatrix(int rank,int blocks,const int* pair_i,const int* pair_j,const double* partial,double* Ac){
  int q=blockIdx.x*blockDim.x+threadIdx.x;if(q>=rank*(rank+1)/2)return;
  double s=0;for(int b=0;b<blocks;++b)s+=partial[(size_t)b*TRI+q];
  int i=pair_i[q],j=pair_j[q];s+=Ac[i*rank+j];Ac[i*rank+j]=s;Ac[j*rank+i]=s;
}
__global__ void Restrict(int rank,const int* global_cluster,const int* global_mode,
 const int* member_offsets,const int* members,const double* Z,const double* r,double* small){
  int a=blockIdx.x;if(a>=rank)return;int k=global_cluster[a],m=global_mode[a];double s=0;
  for(int q=member_offsets[k]+threadIdx.x;q<member_offsets[k+1];q+=blockDim.x){int c=members[q];for(int i=0;i<9;++i)s+=Z[(9ul*c+i)*7+m]*r[9*c+i];}
  __shared__ double work[256];work[threadIdx.x]=s;__syncthreads();
  for(int d=128;d;d/=2){if(threadIdx.x<d)work[threadIdx.x]+=work[threadIdx.x+d];__syncthreads();}
  if(threadIdx.x==0)small[a]=work[0];
}
__global__ void SmallSolve(int rank,const double* L,const double* rhs,double* x){
  if(threadIdx.x||blockIdx.x)return;
  double y[MAX_RANK];for(int i=0;i<rank;++i){double v=rhs[i];for(int j=0;j<i;++j)v-=L[i*rank+j]*y[j];y[i]=v/L[i*rank+i];}
  for(int i=rank-1;i>=0;--i){double v=y[i];for(int j=i+1;j<rank;++j)v-=L[j*rank+i]*x[j];x[i]=v/L[i*rank+i];}
}
__global__ void Prolong(int nc,const int* label,const int* local_rank,const int* offset,const double* Z,const double* small,double* z){
  int q=blockIdx.x*blockDim.x+threadIdx.x;if(q>=9*nc)return;int c=q/9,k=label[c];double s=0;for(int a=0;a<local_rank[k];++a)s+=Z[7ul*q+a]*small[offset[k]+a];z[q]+=s;
}
__global__ void BasisColumn(int nc,int column,const int* label,const int* local_rank,const int* offset,const double* Z,double* x){
  int q=blockIdx.x*blockDim.x+threadIdx.x;if(q>=9*nc)return;int k=label[q/9],a=column-offset[k];x[q]=a>=0&&a<local_rank[k]?Z[7ul*q+a]:0;
}

class Native {
 public:
  using Clock=std::chrono::steady_clock;
  int nc,np,no,blocks;Geometry geometry;
  bool activated=false,usable=false,oracle=false;int activation_outer=-1;
  long attempts=0,applications=0,fallbacks=0,oracle_products=0;
  double setup_seconds=0,apply_enqueue_seconds=0;
  double *Z=nullptr,*Ac=nullptr,*L=nullptr,*small=nullptr,*solution=nullptr,*partial=nullptr;
  int *label=nullptr,*local_rank=nullptr,*offset=nullptr,*member_offsets=nullptr,*members=nullptr,
      *global_cluster=nullptr,*global_mode=nullptr,*pair_i=nullptr,*pair_j=nullptr;
  std::vector<double> hostR,hostt,hostE;Eigen::MatrixXd matrix;
  explicit Native(int cams,int points,int obs):nc(cams),np(points),no(obs),blocks(std::min(512,std::max(1,(points+POINT_WARPS-1)/POINT_WARPS))),geometry(cams){oracle=getenv("OCA_COARSE_ORACLE")&&atoi(getenv("OCA_COARSE_ORACLE"))!=0;}
  ~Native(){
    for(double* p:{Z,Ac,L,small,solution,partial})if(p)cudaFree(p);
    for(int* p:{label,local_rank,offset,member_offsets,members,global_cluster,global_mode,pair_i,pair_j})if(p)cudaFree(p);
    std::printf("COARSE_SUMMARY activated=%d activation_outer=%d rank=%d attempts=%ld applications=%ld fallbacks=%ld oracle_products=%ld setup_seconds=%.9g apply_enqueue_seconds=%.9g\n",(int)activated,activation_outer,geometry.rank,attempts,applications,fallbacks,oracle_products,setup_seconds,apply_enqueue_seconds);
  }
  template<class T>void Allocate(T*& p,size_t n){CUDA_CHECK(cudaMalloc(&p,sizeof(T)*n));}
  template<class T>void Upload(T* p,const std::vector<T>& v){CUDA_CHECK(cudaMemcpy(p,v.data(),sizeof(T)*v.size(),cudaMemcpyHostToDevice));}
  void Initialize(){
    Allocate(Z,63ul*nc);for(double** p:{&Ac,&L})Allocate(*p,MAX_RANK*MAX_RANK);
    for(double** p:{&small,&solution})Allocate(*p,MAX_RANK);Allocate(partial,(size_t)blocks*TRI);
    Allocate(label,nc);Allocate(members,nc);Allocate(local_rank,8);Allocate(offset,9);Allocate(member_offsets,9);
    for(int** p:{&global_cluster,&global_mode})Allocate(*p,MAX_RANK);for(int** p:{&pair_i,&pair_j})Allocate(*p,TRI);
    std::vector<int> a,b;for(int i=0;i<MAX_RANK;++i)for(int j=0;j<=i;++j){a.push_back(i);b.push_back(j);}Upload(pair_i,a);Upload(pair_j,b);
    hostR.resize(9ul*nc);hostt.resize(3ul*nc);hostE.resize(9ul*nc);
  }
  void RestrictVector(const double* r){Restrict<<<geometry.rank,256>>>(geometry.rank,global_cluster,global_mode,member_offsets,members,Z,r,small);}
  template<class Product>bool Oracle(cublasHandle_t blas,Product&& product,double lambda){
    double *v=nullptr,*Av=nullptr;Allocate(v,9ul*nc);Allocate(Av,9ul*nc);
    Eigen::MatrixXd reference(geometry.rank,geometry.rank);std::vector<double> h(geometry.rank);
    for(int a=0;a<geometry.rank;++a){
      BasisColumn<<<(9*nc+255)/256,256>>>(nc,a,label,local_rank,offset,Z,v);
      product(v,Av);CUBLAS_CHECK(cublasDaxpy(blas,9*nc,&lambda,v,1,Av,1));++oracle_products;
      RestrictVector(Av);CUDA_CHECK(cudaMemcpy(h.data(),small,8*h.size(),cudaMemcpyDeviceToHost));
      for(int i=0;i<geometry.rank;++i)reference(i,a)=h[i];
    }
    cudaFree(v);cudaFree(Av);
    double rel=(reference-matrix).norm()/std::max(reference.norm(),1e-300);
    double symmetry=(reference-reference.transpose()).norm()/std::max(reference.norm(),1e-300);
    bool okay=std::isfinite(rel)&&rel<=1e-7&&symmetry<=1e-7;
    std::printf("COARSE_ORACLE rank=%d relative=%.17g symmetry=%.17g pass=%d\n",geometry.rank,rel,symmetry,(int)okay);
    return okay;
  }
  template<class Fragment,class Product>
  void Prepare(const DeviceProblem& p,const DeviceState& s,const double* E,const double* H,
    const Fragment* W,const int* obs_slot,const double* R,double lambda,int outer,int retry,
    int accepted,double last_rel,cublasHandle_t blas,Product&& product){
    usable=false;
    if(!activated&&!(accepted>=8&&last_rel<1e-3&&lambda<1e-3))return;
    auto start=Clock::now();++attempts;
    if(!activated){Initialize();activated=true;activation_outer=outer;std::printf("COARSE_ACTIVATE o=%d accepts=%d last_rel=%.17g lambda=%.17g K=%d\n",outer,accepted,last_rel,lambda,geometry.K);}
    CUDA_CHECK(cudaMemcpy(hostR.data(),s.R,8*hostR.size(),cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(hostt.data(),s.t,8*hostt.size(),cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(hostE.data(),E,8*hostE.size(),cudaMemcpyDeviceToHost));
    try {geometry.Build(hostR,hostt,hostE);}catch(const std::exception& e){
      ++fallbacks;double dt=std::chrono::duration<double>(Clock::now()-start).count();setup_seconds+=dt;
      std::printf("COARSE_PREP o=%d retry=%d fallback=geometry reason=%s seconds=%.9g\n",outer,retry,e.what(),dt);return;
    }
    Upload(Z,geometry.Z);Upload(label,geometry.label);Upload(local_rank,geometry.local_rank);Upload(offset,geometry.offset);
    Upload(member_offsets,geometry.member_offsets);Upload(members,geometry.members);
    std::vector<int> gc,gm;for(int k=0;k<geometry.K;++k)for(int a=0;a<geometry.local_rank[k];++a){gc.push_back(k);gm.push_back(a);}Upload(global_cluster,gc);Upload(global_mode,gm);
    int rank=geometry.rank;CUDA_CHECK(cudaMemset(Ac,0,8ul*rank*rank));
    CameraMatrix<<<nc,64>>>(nc,rank,label,local_rank,offset,Z,E,H,lambda,Ac);
    PointMatrix<Fragment><<<blocks,POINT_THREADS>>>(np,no,p.point_obs_offsets,p.point_obs_list,p.cam_idx,obs_slot,W,R,E,Z,label,local_rank,offset,geometry.K,rank,pair_i,pair_j,partial);
    FinishMatrix<<<(rank*(rank+1)/2+255)/256,256>>>(rank,blocks,pair_i,pair_j,partial,Ac);
    std::vector<double> h((size_t)rank*rank);CUDA_CHECK(cudaMemcpy(h.data(),Ac,8*h.size(),cudaMemcpyDeviceToHost));
    matrix=Eigen::Map<Eigen::Matrix<double,Eigen::Dynamic,Eigen::Dynamic,Eigen::RowMajor>>(h.data(),rank,rank);
    bool parity=!oracle||Oracle(blas,product,lambda);
    Eigen::LLT<Eigen::MatrixXd> chol(matrix);usable=parity&&matrix.allFinite()&&chol.info()==Eigen::Success;
    if(usable){Eigen::Matrix<double,Eigen::Dynamic,Eigen::Dynamic,Eigen::RowMajor> factor=chol.matrixL();CUDA_CHECK(cudaMemcpy(L,factor.data(),8ul*rank*rank,cudaMemcpyHostToDevice));}
    else ++fallbacks;
    double dt=std::chrono::duration<double>(Clock::now()-start).count();setup_seconds+=dt;
    std::printf("COARSE_PREP o=%d retry=%d rank=%d usable=%d fallback=%s seconds=%.9g blocks=%d lloyd=%d empty_repairs=%d\n",outer,retry,rank,(int)usable,usable?"none":!parity?"parity":!matrix.allFinite()?"nonfinite":"not_spd",dt,blocks,geometry.lloyd_iterations,geometry.empty_repairs);
  }
  void Apply(const double* r,double* z){if(!usable)return;auto start=Clock::now();
    RestrictVector(r);SmallSolve<<<1,1>>>(geometry.rank,L,small,solution);
    Prolong<<<(9*nc+255)/256,256>>>(nc,label,local_rank,offset,Z,solution,z);
    ++applications;apply_enqueue_seconds+=std::chrono::duration<double>(Clock::now()-start).count();
  }
};
} // namespace prism_coarse
