#pragma once
#include "geometry.h"
#include "attempt_trace.h"
namespace prism_passenger {
__device__ inline void Cross(const double* a,const double* b,double* c){c[0]=a[1]*b[2]-a[2]*b[1];c[1]=a[2]*b[0]-a[0]*b[2];c[2]=a[0]*b[1]-a[1]*b[0];}
__global__ void Normal(const int* ci,const int* pi,const double* uv,const double* R,const double* t,const double* X,const double* intr,
    int nc,int no,const int* cl,const int* pl,const double* mu,const double* T,const int* offset,const int* ranks,int n,double* H,double* g,unsigned long long* crossing){
  int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=no)return;int i=ci[o],j=pi[o],kc=cl[i],kp=pl[j];if(kc==kp)return;
  if(kp<0)return;atomicAdd(crossing,1ULL);
  const double* r=R+9*i;const double* x=X+3*j;double C[3],Y[3];
  for(int a=0;a<3;++a){C[a]=-(r[a]*t[3*i]+r[3+a]*t[3*i+1]+r[6+a]*t[3*i+2]);Y[a]=r[3*a]*x[0]+r[3*a+1]*x[1]+r[3*a+2]*x[2]+t[3*i+a];}
  double z=Y[2],u=-Y[0]/z,v=-Y[1]/z,rr=u*u+v*v,f=intr[i],k=intr[nc+i],scale=1+k*rr;
  double dxx=f*(scale+2*k*u*u),dxy=2*f*k*u*v,dyy=f*(scale+2*k*v*v);
  double d[6]={-dxx/z,-dxy/z,-(dxx*u+dxy*v)/z,-dxy/z,-dyy/z,-(dxy*u+dyy*v)/z};
  double residual[2]={f*scale*u-uv[2*o],f*scale*v-uv[2*o+1]};
  int ra=ranks[kc],rb=ranks[kp],nt=ra+rb;int ids[14];for(int a=0;a<ra;++a)ids[a]=offset[kc]+a;for(int a=0;a<rb;++a)ids[ra+a]=offset[kp]+a;
  double J[28]={0};
  for(int axis=0;axis<2;++axis){double a[3],xc[3],xp[3],cc[3],wc[3],wp[3];
    for(int m=0;m<3;++m){a[m]=d[3*axis]*r[m]+d[3*axis+1]*r[3+m]+d[3*axis+2]*r[6+m];xc[m]=x[m]-mu[3*kc+m];xp[m]=x[m]-mu[3*kp+m];cc[m]=C[m]-mu[3*kc+m];}
    Cross(a,xc,wc);Cross(a,xp,wp);double cam[7]={wc[0],wc[1],wc[2],-a[0],-a[1],-a[2],-(a[0]*cc[0]+a[1]*cc[1]+a[2]*cc[2])};
    double point[7]={-wp[0],-wp[1],-wp[2],a[0],a[1],a[2],a[0]*xp[0]+a[1]*xp[1]+a[2]*xp[2]};
    for(int c=0;c<ra;++c)for(int m=0;m<7;++m)J[14*axis+c]+=cam[m]*T[49*kc+7*m+c];
    for(int c=0;c<rb;++c)for(int m=0;m<7;++m)J[14*axis+ra+c]+=point[m]*T[49*kp+7*m+c];
  }
  for(int a=0;a<nt;++a){atomicAdd(g+ids[a],J[a]*residual[0]+J[14+a]*residual[1]);for(int b=0;b<nt;++b)atomicAdd(H+ids[a]*n+ids[b],J[a]*J[b]+J[14+a]*J[14+b]);}
}
__global__ void MoveCamera(int nc,const double* R,const double* t,const int* label,const double* mu,const double* action,double* newR,double* newt){
  int i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=nc)return;int k=label[i];const double* r=R+9*i;const double* a=action+13*k;const double* m=mu+3*k;
  double C[3],delta[3];for(int c=0;c<3;++c)C[c]=-(r[c]*t[3*i]+r[3+c]*t[3*i+1]+r[6+c]*t[3*i+2]);
  for(int c=0;c<3;++c)delta[c]=m[c]-(a[c]*m[0]+a[3+c]*m[1]+a[6+c]*m[2])-(a[c]*a[9]+a[3+c]*a[10]+a[6+c]*a[11])-a[12]*(C[c]-m[c]);
  for(int row=0;row<3;++row){newt[3*i+row]=t[3*i+row]+r[3*row]*delta[0]+r[3*row+1]*delta[1]+r[3*row+2]*delta[2];
    for(int col=0;col<3;++col)newR[9*i+3*row+col]=r[3*row]*a[3*col]+r[3*row+1]*a[3*col+1]+r[3*row+2]*a[3*col+2];}
}
__global__ void MovePoint(int np,const double* X,const int* label,const double* mu,const double* action,double* out){
  int j=blockIdx.x*blockDim.x+threadIdx.x;if(j>=np)return;int k=label[j];if(k<0){for(int a=0;a<3;++a)out[3*j+a]=X[3*j+a];return;}
  const double* a=action+13*k;const double* m=mu+3*k;double v[3];for(int c=0;c<3;++c)v[c]=X[3*j+c]-m[c];
  for(int c=0;c<3;++c){double q=(a[3*c]-(c==0))*v[0]+(a[3*c+1]-(c==1))*v[1]+(a[3*c+2]-(c==2))*v[2];out[3*j+c]=X[3*j+c]+a[12]*v[c]+(1+a[12])*q+a[9+c];}
}
struct Native {
  using Clock=std::chrono::steady_clock;
  int nc,np,no;Geometry geometry;std::vector<void*> allocations;DeviceState trial{};
  int *cl=nullptr,*pl=nullptr,*offset=nullptr,*ranks=nullptr;double *mu=nullptr,*T=nullptr,*action=nullptr,*dH=nullptr,*dg=nullptr;unsigned long long* dcross=nullptr;
  bool ready=false;long total_attempts=0,total_accepted=0,total_backtracks=0,total_scores=0,total_normals=0;double total_seconds=0,setup_seconds=0;
  Native(int c,int p,int o):nc(c),np(p),no(o),geometry(c,p,o){}
  ~Native(){for(void* x:allocations)cudaFree(x);if(ready)std::printf("PASSENGER_SUMMARY attempts=%ld accepted=%ld backtracks=%ld full_scores=%ld normal_assemblies=%ld episode_seconds=%.9g setup_seconds=%.9g pcg_products=0\n",total_attempts,total_accepted,total_backtracks,total_scores,total_normals,total_seconds,setup_seconds);}
  template<class A> A* Alloc(size_t n){A* p;CUDA_CHECK(cudaMalloc(&p,n*sizeof(A)));allocations.push_back(p);return p;}
  template<class A> std::vector<A> Download(const A* p,size_t n){std::vector<A> h(n);CUDA_CHECK(cudaMemcpy(h.data(),p,n*sizeof(A),cudaMemcpyDeviceToHost));return h;}
  template<class A> A* Upload(const std::vector<A>& h){A* p=Alloc<A>(h.size());CUDA_CHECK(cudaMemcpy(p,h.data(),h.size()*sizeof(A),cudaMemcpyHostToDevice));return p;}
  void Setup(const DeviceProblem& p,const DeviceState& s,const double* E,const double* Cdiag,double lambda,double tau){
    auto begin=Clock::now();auto R=Download(s.R,9ul*nc),t=Download(s.t,3ul*nc),X=Download(s.X,3ul*np),e=Download(E,9ul*nc),cd=Download(Cdiag,3ul*np);
    auto ci=Download(p.cam_idx,no),pi=Download(p.pt_idx,no);geometry.Build(R,t,X,e,cd,ci,pi,lambda,tau);
    cl=Upload(geometry.cluster.label);pl=Upload(geometry.point_label);offset=Upload(geometry.offset);ranks=Upload(geometry.local_rank);mu=Upload(geometry.mu);T=Upload(geometry.T);
    action=Alloc<double>(13*geometry.K);dH=Alloc<double>(geometry.rank*geometry.rank);dg=Alloc<double>(geometry.rank);dcross=Alloc<unsigned long long>(1);
    trial.R=Alloc<double>(9ul*nc);trial.t=Alloc<double>(3ul*nc);trial.X=Alloc<double>(3ul*np);trial.intr=Alloc<double>(3ul*nc);trial.ncam_for_intr=nc;
    CUDA_CHECK(cudaMemcpy(trial.intr,s.intr,24ul*nc,cudaMemcpyDeviceToDevice));ready=true;setup_seconds=std::chrono::duration<double>(Clock::now()-begin).count();
    std::printf("PASSENGER_SETUP K=%d rank=%d whitening=%.17g seconds=%.9g camera_counts=",geometry.K,geometry.rank,geometry.whitening_error,setup_seconds);
    for(int c:geometry.cluster.count)std::printf("%d,",c);std::printf("\n");
  }
  std::pair<Eigen::MatrixXd,Eigen::VectorXd> Assemble(const DeviceProblem& p,const DeviceState& s,unsigned long long* cross=nullptr){
    int n=geometry.rank;CUDA_CHECK(cudaMemset(dH,0,8ul*n*n));CUDA_CHECK(cudaMemset(dg,0,8ul*n));CUDA_CHECK(cudaMemset(dcross,0,8));
    Normal<<<(no+127)/128,128>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,s.intr,nc,no,cl,pl,mu,T,offset,ranks,n,dH,dg,dcross);
    auto h=Download(dH,n*n),g=Download(dg,n);auto count=Download(dcross,1);if(cross)*cross=count[0];++total_normals;
    Eigen::MatrixXd H=Eigen::Map<Eigen::Matrix<double,Eigen::Dynamic,Eigen::Dynamic,Eigen::RowMajor>>(h.data(),n,n);
    return {(.5*(H+H.transpose())).eval(),Eigen::Map<Eigen::VectorXd>(g.data(),n)};
  }
  void Transform(const DeviceState& s,const std::vector<double>& q){auto a=geometry.Action(q);CUDA_CHECK(cudaMemcpy(action,a.data(),8ul*a.size(),cudaMemcpyHostToDevice));
    MoveCamera<<<(nc+127)/128,128>>>(nc,s.R,s.t,cl,mu,action,trial.R,trial.t);MovePoint<<<(np+255)/256,256>>>(np,s.X,pl,mu,action,trial.X);}
  bool Run(const DeviceProblem& p,DeviceState& s,const double* E,const double* Cdiag,double lambda,double tau,double& cost,int outer){
    auto begin=Clock::now();double initial=cost,coarse_lambda=lambda;Setup(p,s,E,Cdiag,lambda,tau);
    double checked=ComputeCost(p,s);++total_scores;double parity=std::abs(checked-cost)/std::max(1.,std::abs(cost));
    std::printf("PASSENGER_BEGIN outer=%d score_init=%.17g checked=%.17g score_relative=%.17g lambda=%.17g tau=%.17g\n",outer,cost,checked,parity,lambda,tau);
    if(!(std::isfinite(checked)&&parity<=1e-10))throw std::runtime_error("passenger: initial full score parity");
    bool any=false,dirty=true;Eigen::MatrixXd H;Eigen::VectorXd g;unsigned long long cross=0;
    for(int it=0;it<3;++it){++total_attempts;if(dirty){auto normal=Assemble(p,s,&cross);H=normal.first;g=normal.second;dirty=false;}
      Eigen::MatrixXd A=H+coarse_lambda*Eigen::MatrixXd::Identity(geometry.rank,geometry.rank);Eigen::LLT<Eigen::MatrixXd> factor(A);
      if(!H.allFinite()||!g.allFinite()||factor.info()!=Eigen::Success){std::printf("PASSENGER_ATTEMPT outer=%d it=%d lambda=%.17g accepted=0 reason=normal_or_factor\n",outer,it,coarse_lambda);coarse_lambda*=10;continue;}
      Eigen::VectorXd y=factor.solve(-g);double linear=g.dot(y),quad=y.dot(H*y),decrement=-.5*linear;bool accepted=false;int halves=0;
      double residual=(A*y+g).norm()/std::max(g.norm(),1e-300);
      for(;halves<=8;++halves){double alpha=std::ldexp(1.,-halves),pred=-alpha*linear-.5*alpha*alpha*quad;
        auto q=geometry.Parameters(y,alpha);Transform(s,q);double candidate=ComputeCost(p,trial);++total_scores;
        double gain=cost-candidate,rho=pred>0?gain/pred:0;accepted=std::isfinite(candidate)&&pred>0&&gain>0&&rho>.1;
        std::printf("PASSENGER_TRIAL outer=%d it=%d half=%d alpha=%.17g lambda=%.17g cost0=%.17g cost=%.17g gain=%.17g pred=%.17g rho=%.17g accepted=%d decrement=%.17g residual=%.17g cross=%llu\n",outer,it,halves,alpha,coarse_lambda,cost,candidate,gain,pred,rho,(int)accepted,decrement,residual,cross);
        if(accepted){CopyState(s,trial,nc,np);cost=candidate;dirty=true;any=true;++total_accepted;if(rho>.75)coarse_lambda*=.1;break;}
      }
      total_backtracks+=std::min(halves,8);if(!accepted)coarse_lambda*=10;
    }
    CUDA_CHECK(cudaDeviceSynchronize());total_seconds=std::chrono::duration<double>(Clock::now()-begin).count();
    std::printf("PASSENGER_END outer=%d accepted=%ld initial=%.17g cost=%.17g gain=%.17g seconds=%.9g fine_lambda=%.17g\n",outer,total_accepted,initial,cost,initial-cost,total_seconds,lambda);
    return any;
  }
};
} // namespace prism_passenger
