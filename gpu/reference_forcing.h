#pragma once
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cstdio>
#include <stdexcept>
struct PrismReferenceForcing {
  int mode=0,query_outer=-1,eta_outer=-1;
  bool have=false,disabled=false,verify=false,log=false;
  double previous_norm=0,previous_tau=0,reference_norm=0,eta=.5;
  double probe_seconds=0,max_identity_error=0;
  long queries=0,verifications=0;
  PrismReferenceForcing(){
    if(const char* v=getenv("OCA_RRF"))mode=std::atoi(v);
    if(mode<0||mode>3)throw std::runtime_error("invalid reference forcing mode");
    verify=getenv("OCA_RRF_VERIFY");log=getenv("OCA_RRF_LOG");
    if(mode && (getenv("OCA_RLA_FIXED_ETA")||getenv("OCA_RLA_POLICY")||getenv("OCA_RLC_POLICY")||getenv("OCA_RLD_EPISODE")||getenv("OCA_BAC")||getenv("OCA_RLD_LOAD")||getenv("OCA_RLD_SAVE")))
      throw std::runtime_error("reference forcing requires exclusive complete episodes");
  }
  bool NeedQuery(int k,long repairs){if(repairs)disabled=true;return mode&&!disabled&&have&&query_outer!=k;}
  void Reference(int k,double norm){
    if(!std::isfinite(norm)||norm<0)throw std::runtime_error("invalid reference norm");
    query_outer=k;reference_norm=norm;++queries;
  }
  double Forcing(int k,double original,long repairs){
    if(!mode)return original;
    if(repairs)disabled=true;
    double champion=std::clamp(2*original,1e-12,.5);
    if(mode==1||disabled)return champion;
    if(eta_outer!=k){
      double next=.5;
      if(have&&query_outer==k&&previous_norm>0){double q=reference_norm/previous_norm;next=1.8*q*q;}
      if(mode==3 && .9*eta*eta>.1)next=std::max(next,.9*eta*eta);
      eta=std::clamp(next,1e-12,.5);eta_outer=k;
    }
    if(log)std::printf("REFERENCE_CONTROL outer=%d before=%.17g after=%.17g tau_ref=%.17g eta=%.17g champion_eta=%.17g\n",k,previous_norm,reference_norm,previous_tau,eta,champion);
    return eta;
  }
  bool Accept(bool accepted,double norm,double tau){
    if(!mode||disabled||!accepted)return false;
    if(!(norm>0&&tau>0&&std::isfinite(norm)&&std::isfinite(tau)))return false;
    previous_norm=norm;previous_tau=tau;have=true;return true;
  }
};
