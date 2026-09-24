#pragma once
#include <cmath>
// Pick the nearest historical absolute shift among candidates retaining keep
// of the best positive reduction. Exact distance ties prefer lower cost/index.
inline int PrismHysteresisChoice(double current, const double* costs,
                                const double* shifts, int count,
                                double prior, double keep) {
  if (!(prior>0) || !std::isfinite(prior) || !(keep>0 && keep<=1)) return -1;
  double gain=0;
  for(int j=0;j<count;++j) if(std::isfinite(costs[j])) gain=std::fmax(gain,current-costs[j]);
  if(!(gain>0)) return -1;
  int best=-1; double distance=INFINITY;
  for(int j=0;j<count;++j){
    if(!std::isfinite(costs[j]) || !(shifts[j]>0) || !std::isfinite(shifts[j]) ||
       !(current-costs[j]>=keep*gain)) continue;
    double d=std::fabs(std::log(shifts[j])-std::log(prior));
    if(d<distance || (d==distance && (best<0 || costs[j]<costs[best]))){best=j;distance=d;}
  }
  return best;
}
