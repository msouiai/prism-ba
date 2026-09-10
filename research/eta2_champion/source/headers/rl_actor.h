#pragma once
#include "rl_curvature.h"
#include <random>

// On-policy research actor. Policy inference is CPU-only; targets and timing
// references are reward-side information and are not actor inputs.
struct PrismRLActor : PrismCurvatureDamping {
  static constexpr int NAF=20;
  bool actor=false,sample=false,repair_stop=false;
  int na=3,moves=0,last_move=-1000000,sampled_outer=-1,mark_outer=-1;
  double fixed_eta=1,action_eta=1,initial_cost=0,current_cost=0;
  std::array<double,5*NAF> actor_weights{};
  std::mt19937_64 rng{0};
  std::chrono::steady_clock::time_point clock;
  PrismRLActor(){
    if(const char* value=getenv("OCA_RLA_FIXED_ETA")){
      fixed_eta=std::stod(value);
      if(!std::isfinite(fixed_eta)||fixed_eta<=0||fixed_eta>2)
        throw std::runtime_error("invalid fixed forcing factor");
      enabled=true;
    }
    if(const char* path=getenv("OCA_RLA_POLICY")){
      if(controller||policy||episode||getenv("OCA_RLD_ACTION")||getenv("OCA_RLD_OPENING")||
         getenv("OCA_RLD_SAVE")||getenv("OCA_RLD_LOAD")||getenv("OCA_RLA_FIXED_ETA"))
        throw std::runtime_error("RL actor requires exclusive complete episodes");
      std::ifstream in(path);std::string magic;int nf=0;in>>magic>>na>>nf;
      if(magic!="PRISM_RLA_V1"||(na!=3&&na!=5)||nf!=NAF)
        throw std::runtime_error("invalid actor header");
      for(int i=0;i<na*NAF;++i){in>>actor_weights[i];if(!in||!std::isfinite(actor_weights[i]))
        throw std::runtime_error("invalid actor weights");}
      if(const char* seed=getenv("OCA_RLA_SAMPLE")){rng.seed(std::stoull(seed));sample=true;}
      actor=true;collect=true;enabled=true;alphas.reserve(128);betas.reserve(128);
    }
  }
  double Elapsed()const{return std::chrono::duration<double>(std::chrono::steady_clock::now()-clock).count();}
  void Mark(int outer,double cost){
    if(!initial_cost)initial_cost=cost;
    current_cost=cost;
    if(outer!=mark_outer){mark_outer=outer;action_eta=1;}
  }
  std::array<double,NAF> Features()const{
    const double la=model_valid?Log(quad_alpha):0;
    const double lp=previous_quad_alpha>0?Log(previous_quad_alpha):0;
    std::array<double,NAF> x={1,history[0]/8,history[2]/1.5,history[7],history[4]/3,
      history[6]/.5,la/2,double(model_valid),spectrum_valid?Log(condition)/6:0,
      double(spectrum_valid),history[3]/8,Log(current_cost/std::max(initial_cost,1e-300))/5,
      history_count>1?(history[2]-history[NF+2])/1.5:0,(la-lp)/2,
      history[11]/8,history[12]/4,history[7]*history[2]/1.5,history[7]*la/2,
      double(history[4]>0),double(3-moves)/3};
    for(double& v:x)v=std::clamp(Fin(v),-2.,2.);
    return x;
  }
  std::array<double,5> Probabilities(const std::array<double,NAF>& x)const{
    std::array<double,5> p{};double maximum=-INFINITY,sum=0;
    for(int a=0;a<na;++a){for(int j=0;j<NAF;++j)p[a]+=actor_weights[a*NAF+j]*x[j];maximum=std::max(maximum,p[a]);}
    for(int a=0;a<na;++a){p[a]=std::exp(p[a]-maximum);sum+=p[a];}
    for(int a=0;a<na;++a)p[a]/=sum;
    return p;
  }
  int Action(int outer){
    if(!actor)return PrismCurvatureDamping::Action(outer);
    // Poor agreement/rejection causes temporary abstention. Numerical repair
    // permanently ends interventions; true-objective safeguards always apply.
    if(history[9]>0)repair_stop=true;
    if(!history_count||repair_stop||moves>=3||sampled_outer==outer||outer-last_move<=1||
       history[8]>0||history[2]<.25||history[2]>1.5||history[3]<-7||history[0]<-12||history[0]>1)return 0;
    sampled_outer=outer;auto x=Features();auto probs=Probabilities(x);int a=0;
    if(sample){double u=std::generate_canonical<double,53>(rng),c=0;
      a=na-1;for(int j=0;j<na;++j){c+=probs[j];if(u<c){a=j;break;}}}
    else for(int j=1;j<na;++j)if(probs[j]>probs[a])a=j;
    if(a){++moves;last_move=outer;}
    action_eta=a==3?.5:a==4?2.:1.;
    if(file){
      std::fprintf(file,"{\"type\":\"actor\",\"outer\":%d,\"action\":%d,\"sampled\":%d,\"seconds\":%.17g,\"cost\":%.17g,\"initial_cost\":%.17g,\"features\":[",outer,a,int(sample),Elapsed(),current_cost,initial_cost);
      for(int j=0;j<NAF;++j)std::fprintf(file,"%s%.17g",j?",":"",x[j]);
      std::fprintf(file,"],\"probabilities\":[");for(int j=0;j<na;++j)std::fprintf(file,"%s%.17g",j?",":"",probs[j]);
      std::fprintf(file,"],\"moves\":%d}\n",moves);
    }
    return a;
  }
  double LambdaFactor(int action)const{
    if(!actor)return std::pow(10.,action);
    return action==1?.5:action==2?2.:1.;
  }
  double Forcing(double eta)const{
    const double factor=actor?action_eta:fixed_eta;
    return factor==1?eta:std::clamp(eta*factor,1e-12,.5);
  }
  void End(int outer,bool accepted,double used,double next,double floor,double rho,double pred,
      double raw_norm,double radius,double nb,double eta,int cg,int maxck,long mv,long rejects,
      long repairs,double cost,int nobs,int nc,int np){
    PrismCurvatureDamping::End(outer,accepted,used,next,floor,rho,pred,raw_norm,radius,nb,eta,cg,maxck,
                              mv,rejects,repairs,cost,nobs,nc,np);
    if(actor&&history[9]>0)repair_stop=true;
    if(actor&&file)std::fprintf(file,"{\"type\":\"actor_outer\",\"outer\":%d,\"seconds\":%.17g,\"cost\":%.17g,\"eta\":%.17g,\"moves\":%d}\n",outer,Elapsed(),cost,eta,moves);
  }
};
