#pragma once

#include <cmath>
#include <cstddef>
#include <stdexcept>

namespace prism_agent_audit {

inline double StableFiniteNorm(const double* values, std::size_t count) {
  double norm = 0.0;
  for (std::size_t i = 0; i < count; ++i) {
    if (!std::isfinite(values[i]))
      throw std::runtime_error("nonfinite reduced-RHS entry");
    norm = std::hypot(norm, values[i]);
  }
  return norm;
}

inline double ForcingRatioSquared(double norm, double previous_norm) {
  if (!std::isfinite(norm) || !std::isfinite(previous_norm))
    throw std::runtime_error("nonfinite reduced-RHS norm");
  if (!(previous_norm > 0.0)) return 0.0;
  // Preserve the established expression whenever both squares are finite and
  // the denominator is nonzero.  Use the equivalent ratio-first expression
  // only at exceptional scales where direct squaring yields Inf/Inf or 0/0.
  const double n2 = norm * norm;
  const double p2 = previous_norm * previous_norm;
  if (std::fpclassify(n2) == FP_NORMAL && std::fpclassify(p2) == FP_NORMAL)
    return n2 / p2;
  const double ratio = norm / previous_norm;
  return ratio * ratio;
}

inline bool IsExactZeroReducedRhs(double norm) {
  if (!std::isfinite(norm))
    throw std::runtime_error("nonfinite reduced-RHS norm");
  return norm == 0.0;
}

}  // namespace prism_agent_audit
