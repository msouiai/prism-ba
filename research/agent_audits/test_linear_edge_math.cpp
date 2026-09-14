#include "linear_edge_math.h"

#include <cassert>
#include <cmath>
#include <limits>

int main() {
  using prism_agent_audit::ForcingRatioSquared;
  using prism_agent_audit::IsExactZeroReducedRhs;
  using prism_agent_audit::StableFiniteNorm;
  assert(ForcingRatioSquared(3.0, 4.0) == (3.0 * 3.0) / (4.0 * 4.0));
  assert(std::abs(ForcingRatioSquared(1e200, 2e200) - 0.25) < 1e-15);
  assert(std::abs(ForcingRatioSquared(1e-200, 2e-200) - 0.25) < 1e-15);
  assert(std::abs(ForcingRatioSquared(1e-162, 2e-162) - 0.25) < 1e-15);
  assert(IsExactZeroReducedRhs(0.0));
  assert(!IsExactZeroReducedRhs(1.0));
  const double tiny[1]={1e-200},large[1]={1e200},zeros[2]={0,0};
  assert(StableFiniteNorm(tiny,1)==1e-200);
  assert(StableFiniteNorm(large,1)==1e200);
  assert(StableFiniteNorm(zeros,2)==0.0);
  for (double bad : {std::numeric_limits<double>::infinity(),
                     std::numeric_limits<double>::quiet_NaN()}) {
    bool threw = false;
    try { (void)ForcingRatioSquared(bad, 1.0); } catch (...) { threw = true; }
    assert(threw);
    threw = false;
    try { (void)ForcingRatioSquared(1.0, bad); } catch (...) { threw = true; }
    assert(threw);
    threw = false;
    try { (void)IsExactZeroReducedRhs(bad); } catch (...) { threw = true; }
    assert(threw);
    threw = false;
    try { (void)StableFiniteNorm(&bad, 1); } catch (...) { threw = true; }
    assert(threw);
  }
  // Schur fixture: b = -(gc - W (V+lambda Dp)^-1 gp) = 0.
  const double gc=1, gp=2, W=1, Vlambda=2;
  const double reduced_rhs=-(gc-W*gp/Vlambda);
  const double dc=0, dp=-(gp+W*dc)/Vlambda;
  assert(reduced_rhs == 0.0 && dc == 0.0 && dp == -1.0);
}
