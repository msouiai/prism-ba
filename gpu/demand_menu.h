#pragma once
#include <algorithm>
#include <cmath>
// A deterministic screening rule, not a fitted policy. Mode 1 changes only
// menu scheduling; mode 2 additionally retains and escalates the damping pair.
struct PrismDemandMenu {
  bool wide=false,pair_known=false;
  double lambda=0,tau=0;
  static bool Expand(bool improving,double relative_gain,double previous_gain,double ftol){
    return !improving || relative_gain<std::max(10*ftol,.25*previous_gain);
  }
  void Accept(double winning_lambda,double used_tau,bool relax,double floor){
    // Keep the successful pair as the anchor, then cautiously relax both
    // halves after useful unrescued descent. Exact indefinite retention would
    // freeze a large cold-start point damping even as cameras become easy.
    const double factor=relax?.5:1.0;
    lambda=std::max(floor,winning_lambda*factor);
    tau=std::max(1e-7,used_tau*factor);pair_known=true;wide=false;
  }
  void Reject(double center,double used_tau,double floor){
    lambda=std::min(1e8,std::max(floor,center)*10);
    tau=std::min(1e8,std::max(1e-7,used_tau)*10);
    pair_known=true;wide=true;
  }
};
