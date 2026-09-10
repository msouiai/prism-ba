#pragma once
#include <algorithm>
#include <cmath>
struct PrismAdaptiveMenu {
  double value=1.0;
  bool force=true;
  bool Wide(int outer, int rejected) const {
    return outer<2 || outer%8==0 || rejected>0 || force || value>=1.0;
  }
  void Observe(double anchor_gain,double extra_gain,double anchor_seconds,
               double extra_seconds,bool measured,bool failed,bool boundary) {
    if(measured && extra_seconds>0 && anchor_seconds>0){
      double ratio=0;
      if(extra_gain>0)
        ratio=anchor_gain>0 ? (extra_gain/extra_seconds)/(anchor_gain/anchor_seconds) : 4.0;
      value=.5*value+.5*std::min(4.0,std::max(0.0,ratio));
    }
    force=failed||boundary;
  }
};
