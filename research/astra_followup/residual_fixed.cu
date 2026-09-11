#define PRISM_FIXED_LIBRARY
#include "../schur_physics_control/fixed.cu"
#include <chrono>
#include <numeric>

using Clock=std::chrono::steady_clock;
double millis(Clock::time_point t){return std::chrono::duration<double,std::milli>(Clock::now()-t).count();}

// Generalized selection uses current S, actual factored base M, and current b.
// V remains predecessor history. All current products and host work are charged.
int PrepareCurrent(System&s,PrismCoarse&c,cublasHandle_t h,bool energy,int wanted){
  c.handle=h;c.active=false;c.used=0;
  if(c.previous_depth<16||c.count<2)return 0;
  int m=c.count;double*currentAV=alloc<double>(size_t(s.n)*m);
  for(int j=0;j<m;++j)s.Apply(c.V+size_t(j)*s.n,currentAV+size_t(j)*s.n);
  Eigen::MatrixXd K=c.Gram(h,c.V,currentAV,m);
  Eigen::MatrixXd V(s.n,m);std::vector<double>L(81ul*s.nc),rhs(s.n);
  CK(cudaMemcpy(V.data(),c.V,size_t(s.n)*m*8,cudaMemcpyDeviceToHost));
  CK(cudaMemcpy(L.data(),s.B,L.size()*8,cudaMemcpyDeviceToHost));
  CK(cudaMemcpy(rhs.data(),s.b,s.n*8ul,cudaMemcpyDeviceToHost));
  Eigen::MatrixXd MV(s.n,m);
  for(int i=0;i<s.nc;++i){
    Eigen::Map<Eigen::Matrix<double,9,9,Eigen::RowMajor>> Li(L.data()+81ul*i);
    MV.middleRows(9*i,9)=Li*(Li.transpose()*V.middleRows(9*i,9));
  }
  Eigen::MatrixXd G=V.transpose()*MV;G=.5*(G+G.transpose()).eval();
  Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> ge(G);
  if(ge.info()!=Eigen::Success||!ge.eigenvalues().allFinite()){++c.rejects;cudaFree(currentAV);return m;}
  int first=0;double largest=ge.eigenvalues().maxCoeff();
  while(first<m&&ge.eigenvalues()[first]<=1e-10*largest)++first;
  int good=m-first;if(!good){++c.rejects;cudaFree(currentAV);return m;}
  Eigen::MatrixXd wh=ge.eigenvectors().rightCols(good);
  for(int j=0;j<good;++j)wh.col(j)/=std::sqrt(ge.eigenvalues()[first+j]);
  Eigen::MatrixXd small=wh.transpose()*K*wh;
  Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> se(.5*(small+small.transpose()).eval());
  if(se.info()!=Eigen::Success||!se.eigenvalues().allFinite()){++c.rejects;cudaFree(currentAV);return m;}
  Eigen::MatrixXd lift=wh*se.eigenvectors();
  Eigen::Map<Eigen::VectorXd> b(rhs.data(),s.n);
  Eigen::VectorXd projected=lift.transpose()*(V.transpose()*b);
  std::vector<int> order;
  for(int j=0;j<good;++j)if(se.eigenvalues()[j]>1e-12*se.eigenvalues().maxCoeff())order.push_back(j);
  if(energy)std::stable_sort(order.begin(),order.end(),[&](int a,int b){
    return projected[a]*projected[a]/se.eigenvalues()[a]>projected[b]*projected[b]/se.eigenvalues()[b];});
  c.used=std::min(wanted,int(order.size()));
  if(!c.used){++c.rejects;cudaFree(currentAV);return m;}
  Eigen::MatrixXd selected(m,c.used);
  double decrement=0,total=0;
  for(int j:order)total+=.5*projected[j]*projected[j]/se.eigenvalues()[j];
  for(int j=0;j<c.used;++j){selected.col(j)=lift.col(order[j]);decrement+=.5*projected[order[j]]*projected[order[j]]/se.eigenvalues()[order[j]];}
  CK(cudaMemcpy(c.dense,selected.data(),size_t(m)*c.used*8,cudaMemcpyHostToDevice));
  double one=1,zero=0;
  PrismCoarse::blas(cublasDgemm(h,CUBLAS_OP_N,CUBLAS_OP_N,s.n,c.used,m,&one,c.V,s.n,c.dense,m,&zero,c.Z,s.n));
  PrismCoarse::blas(cublasDgemm(h,CUBLAS_OP_N,CUBLAS_OP_N,s.n,c.used,m,&one,currentAV,s.n,c.dense,m,&zero,c.AZ,s.n));
  Eigen::MatrixXd selectedK=c.Gram(h,c.Z,c.AZ,c.used);
  Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> ke(selectedK);
  if(ke.info()!=Eigen::Success||!(ke.eigenvalues().minCoeff()>1e-12*ke.eigenvalues().maxCoeff())){
    ++c.rejects;c.used=0;cudaFree(currentAV);return m;
  }
  Eigen::LLT<Eigen::MatrixXd> llt(selectedK);
  Eigen::MatrixXd inverse=llt.solve(Eigen::MatrixXd::Identity(c.used,c.used));
  if(llt.info()!=Eigen::Success||!inverse.allFinite()){++c.rejects;c.used=0;cudaFree(currentAV);return m;}
  CK(cudaMemcpy(c.ki,inverse.data(),size_t(c.used)*c.used*8,cudaMemcpyHostToDevice));
  c.active=true;CK(cudaFree(currentAV));
  printf("MODE_DIAGNOSTIC energy=%d rank=%d retained=%d good=%d decrement=%.17g available_decrement=%.17g theta_min=%.17g theta_max=%.17g\n",
    energy,wanted,m,good,decrement,total,se.eigenvalues()[0],se.eigenvalues()[good-1]);
  return m;
}

int main(int argc,char**argv){
  if(argc<2||argc>3)return 2;
  System s(argv[1]);System*prev=argc==3?new System(argv[2]):nullptr;
  cublasHandle_t h;PrismCoarse::blas(cublasCreate(&h));
  int reps=getenv("ASTRA_SCHUR_REPS")?atoi(getenv("ASTRA_SCHUR_REPS")):3;
  const char*names[]={"plain","old2","old4","theta2","theta4","energy2","energy4"};
  for(int rep=-1;rep<reps;++rep){
    PrismCoarse c(s.n,16);Result prior;double prior_ms=0;
    if(prev){CK(cudaDeviceSynchronize());auto t=Clock::now();prev->Prepare();
      prior=Solve(*prev,h,&c,true);CK(cudaDeviceSynchronize());prior_ms=millis(t);}
    for(int j=0;j<7;++j){
      int arm=(j+std::max(rep,0))%7;bool advanced=arm>=3,energy=arm>=5;
      int rank=arm==0?0:(arm%2?2:4),refresh=0;
      c.active=false;c.used=0;c.rejects=0;c.rank=rank?rank:16;
      CK(cudaDeviceSynchronize());auto start=Clock::now();s.Prepare();
      if(rank){
        if(advanced)refresh=PrepareCurrent(s,c,h,energy,rank);
        else{c.Prepare(h,[&](const double*a,double*b){s.Apply(a,b);});refresh=c.used;}
      }
      CK(cudaDeviceSynchronize());double setup_ms=millis(start);
      Result result=Solve(s,h,rank?&c:nullptr,false);
      CK(cudaDeviceSynchronize());double wall_ms=millis(start);
      if(rep>=0)printf("ASTRA_FIXED rep=%d arm=%s prior_iterations=%d prior_hit=%d prior_ms=%.9g rank=%d used=%d active=%d rejects=%d refresh=%d setup_ms=%.9g solve_event_ms=%.9g wall_ms=%.9g iterations=%d products=%d true_relative=%.17g eta=%.17g hit=%d negative=%d\n",
        rep,names[arm],prior.iterations,prev?prior.hit:1,prior_ms,rank,c.used,c.active,c.rejects,refresh,
        setup_ms,result.ms,wall_ms,result.iterations,result.products+refresh,result.relative,s.eta,result.hit,result.negative);
      fflush(stdout);
    }
  }
  delete prev;cublasDestroy(h);
}
