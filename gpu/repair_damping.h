#pragma once
#include <algorithm>
#include <cmath>
#include <limits>
// An experimental feedback law for the actual accepted mixed direction.
// It does not assert that this direction solves a new LM system.
struct PrismRepairDamping {
  struct Decision {double prediction=0,rho=0,factor=1;bool valid=false;};
  // A failed model prerequisite forces factor 1 for every possible trial cost.
  static bool ModelEligible(double current,double slope,double curvature){
    const double prediction=-slope-.5*curvature;
    const double floor=64*std::numeric_limits<double>::epsilon()*std::max(1.,current);
    return std::isfinite(current)&&std::isfinite(slope)&&std::isfinite(curvature)&&
      std::isfinite(prediction)&&slope<0&&curvature>=0&&prediction>floor;
  }
  static Decision Decide(double current,double next,double slope,double curvature,int mode){
    Decision d;d.prediction=-slope-.5*curvature;
    const double floor=64*std::numeric_limits<double>::epsilon()*std::max(1.,current);
    if(!std::isfinite(current)||!std::isfinite(next)||!std::isfinite(slope)||
       !std::isfinite(curvature)||!std::isfinite(d.prediction)||current<=next||
       !(slope<0)||curvature<0||!(d.prediction>floor))return d;
    d.rho=(current-next)/d.prediction;
    if(!std::isfinite(d.rho))return d;d.valid=true;
    const double band=64*std::numeric_limits<double>::epsilon()*std::max(1.,std::abs(d.rho));
    if(mode>=2 && d.rho>.75+band)d.factor=.5;
    else if(mode==3 && d.rho<.25-band)d.factor=2;
    return d;
  }
};
