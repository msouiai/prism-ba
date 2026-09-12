#pragma once
// Included after both stage-aware ComputeCost and ComputeOriginalCost.
__global__ void O2InitialDepth(const int* ci,const int* pi,const double* R,
 const double* t,const double* X,int n,double* depth){
  int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=n)return;
  int c=ci[o],p=pi[o];const double* r=R+9*c;const double* x=X+3*p;
  depth[o]=r[6]*x[0]+r[7]*x[1]+r[8]*x[2]+t[3*c+2];
}
struct O2Runtime {
  bool on=false,have_diagnostic=false,was_below=false;
  int index=0,attempts=0,accepts=0,pending=-1,incomplete=0,transitions=0;
  long total_attempts=0,total_accepts=0;
  double* depth=nullptr;
  double original_cost=0,target=0;
  const char* reason="initial";
  static double Stage(int i){const double a[6]={0,.25,.5,.75,.9,1};return a[i];}
  O2Runtime(bool enabled,const DeviceProblem& p,const DeviceState& state,double registered_target):on(enabled),target(registered_target){
    if(!on)return;
    if(o2_context_active)throw std::runtime_error("O2 prototype permits only one serialized solver context");
    o2_context_active=true;
    CUDA_CHECK(cudaMalloc(&depth,(size_t)p.nobs*sizeof(double)));
    O2InitialDepth<<<GridSize(p.nobs),256>>>(p.cam_idx,p.pt_idx,state.R,state.t,state.X,p.nobs,depth);
    CUDA_CHECK(cudaMemcpyToSymbol(o2_depth_device,&depth,sizeof(depth)));
    SetStage(0);
    original_cost=ComputeOriginalCost(p,state);
    if(!std::isfinite(original_cost))throw std::runtime_error("O2 initial original L2 is nonfinite");
    std::printf("O2_CONFIG stages=0,.25,.5,.75,.9,1 accepted_per_stage=2 surrogate_attempt_cap=18 signed_depth=1 full_distortion=1 target_stage=1 depth_bytes=%zu\n",(size_t)p.nobs*sizeof(double));
  }
  ~O2Runtime(){if(on){double one=1.;const double* none=nullptr;
    cudaMemcpyToSymbol(o2_stage_device,&one,sizeof(one));cudaMemcpyToSymbol(o2_depth_device,&none,sizeof(none));
    cudaFree(depth);o2_stage_host=1.;o2_context_active=false;}}
  O2Runtime(const O2Runtime&)=delete;
  void SetStage(int next){index=next;o2_stage_host=Stage(next);CUDA_CHECK(cudaMemcpyToSymbol(o2_stage_device,&o2_stage_host,sizeof(double)));}
  bool Surrogate()const{return on && index<5;}
  bool Due()const{return Surrogate() && (pending>=0 || attempts>=18);}
  void Tick(){if(on){++attempts;++total_attempts;}}
  void Observe(bool accepted){if(!on)return;if(accepted){++accepts;++total_accepts;
    if(Surrogate() && accepts>=2){pending=index+1;reason="two_accepts";}
    if(index==5 && accepts==2)std::printf("O2_FINAL_STAGE two_accepts=1 full_schedule_completed=%d ordinary_eta2=1\n",(int)(incomplete==0));}}
  void Stop(){if(Surrogate()){pending=5;reason="stage_stop";++incomplete;}}
  double Transition(const DeviceProblem& p,const DeviceState& state,int outer,double lambda,double radius,double floor){
    int previous=index,old_attempts=attempts,old_accepts=accepts;
    if(pending<0){pending=5;reason="attempt_cap";++incomplete;}
    SetStage(pending);pending=-1;attempts=accepts=0;++transitions;
    double cost=ComputeCost(p,state);
    if(!std::isfinite(cost) && index<5){
      std::printf("O2_STAGE_DOMAIN_FAILURE stage=%.17g outer=%d\n",Stage(index),outer);
      ++incomplete;SetStage(5);reason="stage_domain_failure";cost=ComputeCost(p,state);
    }
    if(!std::isfinite(cost))throw std::runtime_error("O2 original stage became nonfinite");
    std::printf("O2_TRANSITION outer=%d from=%.17g to=%.17g reason=%s attempts=%d accepts=%d cost_stage=%.17g lambda=%.17g radius=%.17g floor=%.17g reset=rhs_norm,ftol,previous_cost,confirmation,controller_observation,factors preserve=state,lambda,radius,floor,cumulative_work,warmup\n",
      outer,Stage(previous),Stage(index),reason,old_attempts,old_accepts,cost,lambda,radius,floor);
    return cost;
  }
  void Diagnostic(const DeviceProblem& p,const DeviceState& state,int outer,bool accepted,double stage_cost){
    if(!on)return;
    if(index==5)original_cost=stage_cost;
    else if(accepted || !have_diagnostic)original_cost=ComputeOriginalCost(p,state);
    const bool below=target>0 && original_cost<=target*(1.-1e-8);
    const char* crossing=!have_diagnostic?"initial":below&&!was_below?"down":!below&&was_below?"up":"none";
    std::printf("O2_TRACE outer=%d stage=%.17g stage_attempts=%d stage_accepts=%d accepted=%d cost_stage=%.17g cost_original=%.17g target_below=%d crossing=%s scored_eligible=%d\n",
      outer,Stage(index),attempts,accepts,(int)accepted,stage_cost,original_cost,(int)below,crossing,(int)(index==5));
    have_diagnostic=true;was_below=below;
  }
  void Finish(){if(on)std::printf("O2_SUMMARY stage=%.17g transitions=%d incomplete_events=%d attempts=%ld accepts=%ld cost_original=%.17g full_objective_entered=%d opening_complete=%d schedule_complete=%d\n",
    Stage(index),transitions,incomplete,total_attempts,total_accepts,original_cost,(int)(index==5),(int)(index==5 && incomplete==0),(int)(index==5 && incomplete==0 && accepts>=2));}
};
