#pragma once
#include "../coarse/native/coarse.cuh"
#include "mode_math.h"
#include "attempt_trace.h"

namespace prism_soft {
class Native {
 public:
 using Clock=std::chrono::steady_clock;
 int nc,np,no;long interventions=0,admitted=0,skipped=0,scores=0,models=0,restorations=0;
 double seconds=0,restore_seconds=0,pre_cost=0;bool saved=false;
 DeviceState snapshot{};
 std::unique_ptr<prism_coarse::Native> coarse;
 double *v=nullptr,*Av=nullptr,*direction=nullptr;
 explicit Native(int cams,int pts,int obs):nc(cams),np(pts),no(obs){}
 ~Native(){for(double* p:{v,Av,direction,snapshot.R,snapshot.t,snapshot.X,snapshot.intr})if(p)cudaFree(p);
  std::printf("SOFT_KICK_SUMMARY interventions=%ld admitted=%ld skipped=%ld scores=%ld model_passes=%ld restorations=%ld seconds=%.9g restore_seconds=%.9g\n",interventions,admitted,skipped,scores,models,restorations,seconds,restore_seconds);}
 template<class Product>bool Try(const DeviceProblem& p,DeviceState& s,DeviceState& trial,
  const double* E,const double* H,const float* W,const int* obs_slot,const double* Rf,
  const double* factor,double lambda,double radius,double budget,int outer,
  cublasHandle_t blas,Product&& product,PrismFullModel& full_model,double k2mask,double* w,double* uu,double& cost){
  ++interventions;auto start=Clock::now();std::string reason="invalid";Mode mode;double slope=0,curvature=0,alpha=0,newcost=std::numeric_limits<double>::quiet_NaN(),cnorm=0;
  bool applied=false;double initial=cost;
  do {
   coarse=std::make_unique<prism_coarse::Native>(nc,np,no);coarse->Initialize();coarse->activated=true;coarse->activation_outer=outer;coarse->attempts=1;
   auto& c=*coarse;
   CUDA_CHECK(cudaMemcpy(c.hostR.data(),s.R,8*c.hostR.size(),cudaMemcpyDeviceToHost));
   CUDA_CHECK(cudaMemcpy(c.hostt.data(),s.t,8*c.hostt.size(),cudaMemcpyDeviceToHost));
   CUDA_CHECK(cudaMemcpy(c.hostE.data(),E,8*c.hostE.size(),cudaMemcpyDeviceToHost));
   try{c.geometry.Build(c.hostR,c.hostt,c.hostE);}catch(const std::exception& e){reason=std::string("geometry_")+e.what();break;}
   c.Upload(c.Z,c.geometry.Z);c.Upload(c.label,c.geometry.label);c.Upload(c.local_rank,c.geometry.local_rank);c.Upload(c.offset,c.geometry.offset);
   c.Upload(c.member_offsets,c.geometry.member_offsets);c.Upload(c.members,c.geometry.members);
   std::vector<int> gc,gm;for(int k=0;k<c.geometry.K;++k)for(int a=0;a<c.geometry.local_rank[k];++a){gc.push_back(k);gm.push_back(a);}c.Upload(c.global_cluster,gc);c.Upload(c.global_mode,gm);
   int rank=c.geometry.rank;CUDA_CHECK(cudaMemset(c.Ac,0,8ul*rank*rank));
   prism_coarse::CameraMatrix<<<nc,64>>>(nc,rank,c.label,c.local_rank,c.offset,c.Z,E,H,lambda,c.Ac);
   prism_coarse::PointMatrix<float><<<c.blocks,prism_coarse::POINT_THREADS>>>(np,no,p.point_obs_offsets,p.point_obs_list,p.cam_idx,obs_slot,W,Rf,E,c.Z,c.label,c.local_rank,c.offset,c.geometry.K,rank,c.pair_i,c.pair_j,c.partial);
   prism_coarse::FinishMatrix<<<(rank*(rank+1)/2+255)/256,256>>>(rank,c.blocks,c.pair_i,c.pair_j,c.partial,c.Ac);
   std::vector<double> matrix((size_t)rank*rank),factors(81ul*nc);
   CUDA_CHECK(cudaMemcpy(matrix.data(),c.Ac,8*matrix.size(),cudaMemcpyDeviceToHost));
   CUDA_CHECK(cudaMemcpy(factors.data(),factor,8*factors.size(),cudaMemcpyDeviceToHost));
   c.matrix=Eigen::Map<Eigen::Matrix<double,Eigen::Dynamic,Eigen::Dynamic,Eigen::RowMajor>>(matrix.data(),rank,rank);
   if(getenv("OCA_SOFT_KICK_ORACLE")&&!c.Oracle(blas,product,lambda)){reason="coarse_operator_parity";break;}
   mode=SelectMode(c.geometry,c.matrix,c.hostR,c.hostt,c.hostE,factors);
   if(!mode.usable){reason=mode.reason;break;}
   CUDA_CHECK(cudaMalloc(&v,9ul*nc*8));CUDA_CHECK(cudaMalloc(&Av,9ul*nc*8));CUDA_CHECK(cudaMalloc(&direction,(9ul*nc+3ul*np)*8));
   CUDA_CHECK(cudaMemcpy(c.solution,mode.coefficients.data(),8ul*rank,cudaMemcpyHostToDevice));CUDA_CHECK(cudaMemset(v,0,9ul*nc*8));
   prism_coarse::Prolong<<<(9*nc+255)/256,256>>>(nc,c.label,c.local_rank,c.offset,c.Z,c.solution,v);
   product(v,Av); // Native product leaves w=E*v and uu=V^-1 W^T w.
   CUDA_CHECK(cudaMemcpy(direction,w,9ul*nc*8,cudaMemcpyDeviceToDevice));
   CUDA_CHECK(cudaMemcpy(direction+9ul*nc,uu,3ul*np*8,cudaMemcpyDeviceToDevice));
   KernelNegateInPlace<<<GridSize(3*np),256>>>(direction+9ul*nc,3*np);
   auto model=full_model.Evaluate(p,s,direction,k2mask);++models;slope=model.slope;curvature=model.curvature;
   double sign=1;if(slope<0)sign=-1;
   else if(slope==0){std::vector<double> host(9ul*nc+3ul*np);CUDA_CHECK(cudaMemcpy(host.data(),direction,8*host.size(),cudaMemcpyDeviceToHost));size_t best=0;for(size_t i=1;i<host.size();++i)if(std::abs(host[i])>std::abs(host[best]))best=i;if(host[best]<0)sign=-1;}
   slope*=sign;alpha=Amplitude(slope,curvature,budget);
   if(!(alpha>0&&std::isfinite(alpha))){reason="ray_energy";break;}
   double scale=sign*alpha;CUBLAS_CHECK(cublasDscal(blas,9*nc+3*np,&scale,direction,1));
   CUBLAS_CHECK(cublasDnrm2(blas,9*nc,v,1,&cnorm));cnorm*=alpha;
   RetractDof9(p,s,direction,trial);newcost=ComputeCost(p,trial,0,0);++scores;
   if(!(std::isfinite(newcost)&&newcost<=initial+2*budget)){reason="true_cost_bound";break;}
   AllocState(snapshot,nc,np,true);CopyState(snapshot,s,nc,np);pre_cost=initial;saved=true;
   CopyState(s,trial,nc,np);cost=newcost;++admitted;applied=true;reason="admitted";
  }while(false);
  if(!applied)++skipped;
  const double elapsed=std::chrono::duration<double>(Clock::now()-start).count();seconds+=elapsed;
  std::printf("SOFT_KICK_EVENT o=%d applied=%d reason=%s rank=%d gauge_rank=%d eigenvalue=%.17g negative=%d gauge_representation=%.17g gauge_leakage=%.17g ritz_residual=%.17g metric_norm=%.17g cost0=%.17g trial_cost=%.17g budget=%.17g slope=%.17g curvature=%.17g alpha=%.17g camera_norm=%.17g old_radius=%.17g seconds=%.9g\n",outer,(int)applied,reason.c_str(),mode.rank,mode.gauge_rank,mode.eigenvalue,mode.negative,mode.gauge_representation,mode.gauge_leakage,mode.ritz_residual,mode.metric_norm,initial,newcost,budget,slope,curvature,alpha,cnorm,radius,elapsed);
  std::printf("SOFT_KICK_SPECTRUM o=%d values=",outer);for(int i=0;i<mode.eigenvalues.size();++i)std::printf("%s%.17g",i?",":"",mode.eigenvalues[i]);std::printf("\n");
  return applied;
 }
 bool RestoreBest(const DeviceProblem& p,DeviceState& s,double& cost){
  if(!saved)return false;auto begin=Clock::now();bool restore=!(std::isfinite(cost)&&cost<=pre_cost);
  const double before=cost;
  if(restore){CopyState(s,snapshot,nc,np);cost=pre_cost;++restorations;}
  const double checked=ComputeCost(p,s,0,0);++scores;
  if(!(std::isfinite(checked)&&std::abs(checked-cost)<=1e-10*std::max(1.,std::abs(cost))))throw std::runtime_error("soft kick returned state/cost mismatch");
  restore_seconds+=std::chrono::duration<double>(Clock::now()-begin).count();
  std::printf("SOFT_KICK_RETURN restored=%d cost_before=%.17g pre_kick=%.17g cost=%.17g checked=%.17g seconds=%.9g\n",(int)restore,before,pre_cost,cost,checked,restore_seconds);
  return restore;
 }
};
} // namespace prism_soft
