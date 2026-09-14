#pragma once
#include <cmath>
#include <cstddef>
#include <limits>
#include <stdexcept>

namespace prism_linear_edges {
struct NormResult { double norm; bool all_zero; };

inline NormResult ScaledFiniteNorm(const double* x, std::size_t n) {
  double scale=0.0, ssq=1.0; bool all_zero=true;
  for(std::size_t i=0;i<n;++i){
    const double v=x[i];
    if(!std::isfinite(v)) throw std::runtime_error("nonfinite reduced-RHS entry");
    const double a=std::abs(v); if(a==0.0) continue; all_zero=false;
    if(scale<a){const double q=scale/a;ssq=1.0+ssq*q*q;scale=a;}
    else {const double q=a/scale;ssq+=q*q;}
  }
  if(all_zero) return {0.0,true};
  const double result=scale*std::sqrt(ssq);
  if(!std::isfinite(result)) throw std::runtime_error("unrepresentable reduced-RHS norm");
  return {result,false};
}

inline double ForcingRatioSquared(double norm,double previous_norm){
  if(!std::isfinite(norm)||!std::isfinite(previous_norm))
    throw std::runtime_error("nonfinite reduced-RHS norm history");
  if(!(previous_norm>0.0)) return 0.0;
  const double n2=norm*norm,p2=previous_norm*previous_norm;
  if(std::fpclassify(n2)==FP_NORMAL&&std::fpclassify(p2)==FP_NORMAL)return n2/p2;
  const double r=norm/previous_norm;
  if(!std::isfinite(r)) return std::numeric_limits<double>::infinity();
  return r*r;
}
}

