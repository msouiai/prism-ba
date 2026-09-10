#pragma once
#include <array>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <stdexcept>
#include <string>

// Research controller. History is checkpointed; instrumentation needs no GPU
// kernels. A null policy/action zero leaves damping arithmetic untouched.
struct PrismRLDamping {
  static constexpr int NF=16, NH=4, NX=NF*NH;
  bool enabled=false, previous_accepted=false;
  int history_count=0,previous_action=0,fork_outer=-1;
  double previous_lambda=0;
  std::array<double,NX> history{};
  std::array<double,NX> mean{},sd{};
  std::array<double,3*(NX+1)> weights{};
  bool policy=false;
  bool episode=false,episode_fallback=false;
  int episode_mode=0,episode_budget=0,episode_actions=0,episode_last=-1000000,episode_cooldown=1;
  double episode_rho=.95,episode_cg=.125;
  FILE* file=nullptr;
  long start_mv=0,start_rej=0,start_rep=0;
  double start_cost=0;
  std::chrono::steady_clock::time_point start;
  PrismRLDamping(){
    for(const char* key:{"OCA_RLD_LOG","OCA_RLD_SAVE","OCA_RLD_LOAD","OCA_RLD_ACTION","OCA_RLD_POLICY","OCA_RLD_OPENING","OCA_RLD_EPISODE"})
      if(getenv(key))enabled=true;
    if(const char* path=getenv("OCA_RLD_LOG")){
      file=std::fopen(path,"w");if(!file)throw std::runtime_error("cannot open RLD log");
    }
    if(const char* path=getenv("OCA_RLD_POLICY")){
      std::ifstream in(path);std::string magic;int n=0;in>>magic>>n;
      if(magic!="PRISM_RLD_LINEAR_V1"||n!=NX)throw std::runtime_error("invalid RLD policy");
      for(double& x:mean)in>>x;for(double& x:sd)in>>x;for(double& x:weights)in>>x;
      if(!in)throw std::runtime_error("truncated RLD policy");
      for(double x:mean)if(!std::isfinite(x))throw std::runtime_error("nonfinite RLD mean");
      for(double x:sd)if(!(x>0&&std::isfinite(x)))throw std::runtime_error("invalid RLD scale");
      for(double x:weights)if(!std::isfinite(x))throw std::runtime_error("nonfinite RLD coefficient");
      policy=true;
    }
    if(const char* path=getenv("OCA_RLD_EPISODE")){
      if(policy || getenv("OCA_RLD_OPENING") || getenv("OCA_RLD_ACTION") ||
         getenv("OCA_RLD_SAVE") || getenv("OCA_RLD_LOAD"))
        throw std::runtime_error("episode policy requires an exclusive complete solve; replay unsupported");
      std::ifstream in(path);std::string magic;
      in>>magic>>episode_mode>>episode_budget>>episode_rho>>episode_cg>>episode_cooldown;
      if(!in || magic!="PRISM_RLD_EPISODE_V1" || episode_mode<0 || episode_mode>3 ||
         episode_budget<0 || episode_budget>8 || !std::isfinite(episode_rho) ||
         episode_rho<.25 || episode_rho>1.5 || !std::isfinite(episode_cg) ||
         episode_cg<0 || episode_cg>1 || episode_cooldown<1 || episode_cooldown>8)
        throw std::runtime_error("invalid episode damping policy");
      episode=true;
    }
  }
  ~PrismRLDamping(){if(file)std::fclose(file);}
  static double Log(double x){return std::log10(std::max(std::abs(x),1e-30));}
  static double Fin(double x){return std::isfinite(x)?x:0.;}
  int Action(int outer){
    if(episode){
      if(history_count<1 || episode_mode==0)return 0;
      // Fall back permanently after poor agreement, negligible progress,
      // rejection or numerical repair. This preserves baseline safeguards;
      // it cannot undo trajectory changes caused by earlier interventions.
      if(history[8]>0 || history[9]>0 || history[2]<.25 || history[2]>1.5 || history[3]<-7)
        episode_fallback=true;
      if(episode_fallback || episode_actions>=episode_budget ||
         outer-episode_last<=episode_cooldown || history[0]<-12 || history[0]>1)return 0;
      int action=0;
      if((episode_mode==2 || episode_mode==3) && history[7]>=.99)action=1;
      else if((episode_mode==1 || episode_mode==3) && history[2]>=episode_rho &&
              history[7]<=episode_cg)action=-1;
      if(action){++episode_actions;episode_last=outer;}
      return action;
    }
    if(const char* p=getenv("OCA_RLD_ACTION")){
      int k=fork_outer;
      if(const char* at=getenv("OCA_RLD_ACTION_AT"))k=std::atoi(at);
      if(outer==k){int a=std::atoi(p);if(a<-1||a>1)throw std::runtime_error("RLD action must be -1/0/1");return a;}
    }
    // Fixed comparator: accelerate only the first N accepted boundaries.
    // It is deliberately independent of learned predictions and scene identity.
    if(const char* p=getenv("OCA_RLD_OPENING")){
      const int n=std::atoi(p);
      if(n<0)throw std::runtime_error("RLD opening length must be nonnegative");
      return outer>0 && outer<=n ? -1 : 0;
    }
    if(!policy)return 0;
    // Predict normalized advantage; zero is the baseline, ties use it.
    double best=0.;int action=0;
    for(int a:{-1,1}){
      int off=(a+1)*(NX+1);double value=weights[off+NX];
      for(int j=0;j<NX;++j)value+=weights[off+j]*std::clamp((history[j]-mean[j])/sd[j],-5.,5.);
      if(value>best){best=value;action=a;}
    }
    return action;
  }
  void Decision(int outer,double base,double lambda,double radius,double floor){
    if(file){std::fprintf(file,"{\"type\":\"decision\",\"outer\":%d,\"action\":%d,\"base_lambda\":%.17g,\"lambda\":%.17g,\"radius\":%.17g,\"floor\":%.17g,\"features\":[",outer,previous_action,base,lambda,radius,floor);
      for(int j=0;j<NX;++j)std::fprintf(file,"%s%.17g",j?",":"",history[j]);
      std::fprintf(file,"],\"episode_actions\":%d,\"episode_fallback\":%d}\n",episode_actions,int(episode_fallback));}
  }
  void Begin(long mv,long rejects,long repairs,double cost){
    start=std::chrono::steady_clock::now();start_mv=mv;start_rej=rejects;start_rep=repairs;start_cost=cost;
  }
  void End(int outer,bool accepted,double used,double next,double floor,double rho,double pred,
      double raw_norm,double radius,double nb,double eta,int cg,int maxck,long mv,long rejects,
      long repairs,double cost,int nobs,int nc,int np){
    double dt=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    for(int j=NX-1;j>=NF;--j)history[j]=history[j-NF];
    double rel=(start_cost-cost)/std::max(start_cost,1e-300);
    std::array<double,NF> f={Log(next),Log(next/std::max(floor,1e-30)),Fin(rho),Log(rel),
      Log(raw_norm/std::max(radius,1e-30)),Log(nb),Fin(eta),double(cg)/std::max(1,maxck),
      double(rejects-start_rej),double(repairs-start_rep),Log(cost/std::max(1,nobs)),
      Log(nobs),Log(double(np)/std::max(1,nc)),double(previous_action),double(accepted),
      previous_lambda>0?Log(used/previous_lambda):0.};
    for(int j=0;j<NF;++j)history[j]=Fin(f[j]);
    ++history_count;previous_accepted=accepted;previous_lambda=used;
    // An exhausted rejected outer skips Action at the next boundary. Latch
    // here too, so it cannot silently erase the fallback trigger later.
    if(episode && (history[8]>0 || history[9]>0 || history[2]<.25 ||
       history[2]>1.5 || history[3]<-7))episode_fallback=true;
    if(file)std::fprintf(file,"{\"type\":\"outer\",\"outer\":%d,\"accepted\":%d,\"lambda_used\":%.17g,\"lambda_next\":%.17g,\"cost0\":%.17g,\"cost\":%.17g,\"rho\":%.17g,\"prediction\":%.17g,\"rho_valid\":%d,\"cg\":%d,\"matvecs\":%ld,\"rejects\":%ld,\"repairs\":%ld,\"dt\":%.17g}\n",outer,int(accepted),used,next,start_cost,cost,Fin(rho),Fin(pred),int(std::isfinite(rho)&&std::isfinite(pred)&&pred>0),cg,mv-start_mv,rejects-start_rej,repairs-start_rep,dt);
  }
};
