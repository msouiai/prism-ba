#include "linear_edge_math.h"
#include <cassert>
#include <cmath>
#include <limits>

int main(){
  using prism_linear_edges::ScaledFiniteNorm; using prism_linear_edges::ForcingRatioSquared;
  const double z[2]={0,0}, ordinary[2]={3,4}, quantized[1]={1.6e-162};
  const double tiny[1]={1e-200}, large[1]={1e200}, mixed[2]={1e200,1e-200};
  assert(ScaledFiniteNorm(z,2).all_zero&&ScaledFiniteNorm(z,2).norm==0);
  assert(ScaledFiniteNorm(ordinary,2).norm==5&&!ScaledFiniteNorm(ordinary,2).all_zero);
  assert(ScaledFiniteNorm(quantized,1).norm==quantized[0]);
  assert(ScaledFiniteNorm(tiny,1).norm==tiny[0]&&!ScaledFiniteNorm(tiny,1).all_zero);
  assert(ScaledFiniteNorm(large,1).norm==large[0]);
  assert(ScaledFiniteNorm(mixed,2).norm==large[0]);
  assert(ForcingRatioSquared(3,4)==9.0/16.0);
  assert(std::abs(ForcingRatioSquared(1e200,2e200)-.25)<1e-15);
  assert(std::abs(ForcingRatioSquared(1e-200,2e-200)-.25)<1e-15);
  assert(std::isinf(ForcingRatioSquared(1e200,1e-200)));
  assert(ForcingRatioSquared(1e-200,1e200)==0.0);
  assert(ForcingRatioSquared(1.0,0.0)==0.0);
  for(double bad:{std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN()}){
    bool threw=false;try{ScaledFiniteNorm(&bad,1);}catch(...){threw=true;}assert(threw);
    threw=false;try{ForcingRatioSquared(bad,1);}catch(...){threw=true;}assert(threw);
    threw=false;try{ForcingRatioSquared(1,bad);}catch(...){threw=true;}assert(threw);
  }
  const double vmax=std::numeric_limits<double>::max(); const double ov[2]={vmax,vmax};
  bool threw=false;try{ScaledFiniteNorm(ov,2);}catch(...){threw=true;}assert(threw);
  // Exact damped Schur fixture: reduced camera RHS is zero while point step is not.
  const double gc=1,gp=2,W=1,Vlambda=2;
  const double reduced_rhs=-(gc-W*gp/Vlambda),dc=0,dp=-(gp+W*dc)/Vlambda;
  assert(reduced_rhs==0&&dc==0&&dp==-1);
}
