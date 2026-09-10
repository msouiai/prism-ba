#pragma once
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cstdio>
#include <stdexcept>

// Experimental forcing signals. No convergence theorem is claimed for the
// clipped, damped GN system; acceptance and true-residual checks stay external.
struct PrismBAAccuracy {
  int mode=0,last_outer=-1;
  double c0=0,p0=0,gradient=0,previous=0,eta=.5,error=0;
  PrismBAAccuracy(){
    if(const char* s=std::getenv("OCA_BAC"))mode=std::atoi(s);
    if(mode<0||mode>5)throw std::runtime_error("invalid BA accuracy mode");
    if(mode && (std::getenv("OCA_RLA_FIXED_ETA")||std::getenv("OCA_RLA_POLICY")||
       std::getenv("OCA_RLC_POLICY")||std::getenv("OCA_RLD_EPISODE")))
      throw std::runtime_error("BA accuracy controller must be exclusive");
  }
  bool NeedsGradient()const{return mode==2||mode==4||mode==5;}
  void Gradient(double c,double p){
    if(!std::isfinite(c)||!std::isfinite(p))throw std::runtime_error("invalid gradient norm");
    if(c0==0){c0=std::max(c,1e-100);p0=std::max(p,1e-100);}
    gradient=std::hypot(c/c0,p/p0);
  }
  static double EW(double current,double old,double last){
    if(!(old>0))return .5;
    double q=current/old;
    double result=.9*q*q,safe=.9*last*last;
    if(safe>.1)result=std::max(result,safe);
    return std::clamp(result,1e-12,.5);
  }
  double Forcing(int outer,double original,double reduced){
    if(!mode)return original;
    if(mode==1)return .5;
    if(outer!=last_outer){
      double measure=NeedsGradient()?gradient:reduced;
      eta=EW(measure,previous,eta);previous=measure;last_outer=outer;
      // Model discrepancy is a heuristic accuracy floor, not a bound on
      // damped quadratic error. Suppress stale optimistic evidence on retries.
      if(mode>=4)eta=std::max(eta,std::min(.5,std::sqrt(error)));
    }
    return eta;
  }
  double NextLambda(bool accepted,double rho,double used,double next){
    if(!mode)return next;
    if(accepted && std::isfinite(rho))error=std::min(1.,std::abs(1-rho));
    if(mode==5 && accepted && next<used)
      next=std::max(next,used*std::clamp(std::sqrt(error),.1,1.));
    return next;
  }
};
