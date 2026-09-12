#pragma once
#include <algorithm>
#include <cmath>
#include <limits>

namespace prism_stcg {

// Return the nonnegative root of ||x + tau p||_M = radius. Inputs are
// direct Gram products in the fixed, positive-definite attempt metric.
inline double boundary_tau(double xx, double xp, double pp, double radius) {
  if (!(std::isfinite(xx) && std::isfinite(xp) && std::isfinite(pp) &&
        std::isfinite(radius) && xx >= 0 && pp > 0 && radius > 0))
    return std::numeric_limits<double>::quiet_NaN();
  const long double a=pp, b=xp, rr=(long double)radius*radius;
  long double c=(long double)xx-rr;
  // A direct sum of nonnegative products can land a few ulps outside.
  const long double slack=64*std::numeric_limits<double>::epsilon()*
      std::max(rr,(long double)xx);
  if (c>slack) return std::numeric_limits<double>::quiet_NaN();
  c=std::min(c,(long double)0);
  const long double root=std::hypot(b,std::sqrt(a)*std::sqrt(-c));
  const long double t=b>=0 ? (root+b>0 ? -c/(root+b) : 0) : (root-b)/a;
  const double result=(double)t;
  return result>=0 && std::isfinite(result) ? result :
      std::numeric_limits<double>::quiet_NaN();
}

inline bool crosses(double xx,double xp,double pp,double alpha,double radius) {
  const long double a=alpha;
  return (long double)xx+2*a*xp+a*a*pp >= (long double)radius*radius;
}

}  // namespace prism_stcg
