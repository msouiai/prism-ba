#pragma once

// Short lifted robust opening for D9.  The scored objective remains L2; these
// routines are active only while the persistent confidence variables are part
// of the opening state.

struct W6LiftHostConfig {
  const double* weights = nullptr;
  double tau2 = 0;
  double lambda = 0;
  bool active = false;
};

inline W6LiftHostConfig w6_lift_host;

inline void W6SetLift(bool active, const double* weights, double tau2,
                      double lambda) {
  w6_lift_host = W6LiftHostConfig{weights, tau2, lambda, active};
}

__global__ void W6Fill(double* x, int n, double value) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i < n) x[i] = value;
}

// Apply the symmetric square root of
//   C = w^2 [I - r r^T / (||r||^2 + 2 tau^2 w^2 + lambda)]
// to every Jacobian column, and choose the transformed residual q so that
// J_t^T q is the exact RHS after eliminating the scalar weight increment.
template <int N>
__device__ __forceinline__ void W6LiftRows(
    double raw_rx, double raw_ry, double weight, double tau2, double lambda,
    double* gx, double* gy, double& rx, double& ry) {
  const double r2 = raw_rx * raw_rx + raw_ry * raw_ry;
  const double w2 = weight * weight;
  const double denom = r2 + 2.0 * tau2 * w2 + lambda;
  if (!(denom > 0.0) || !(w2 > 1e-300)) {
    rx = ry = 0.0;
    for (int i = 0; i < N; ++i) gx[i] = gy[i] = 0.0;
    return;
  }
  const double h = fmax((2.0 * tau2 * w2 + lambda) / denom, 1e-300);
  const double sqrt_h = sqrt(h);
  const double abs_w = fabs(weight);
  // Algebraically positive: w^2 [tau^2(w^2+1)+lambda] / denom.
  const double gfac = w2 *
      (1.0 - (r2 + tau2 * (w2 - 1.0)) / denom);
  const double rank = r2 > 0.0 ? (1.0 - sqrt_h) / r2 : 0.0;
  for (int i = 0; i < N; ++i) {
    const double x = gx[i], y = gy[i];
    const double dot = raw_rx * x + raw_ry * y;
    gx[i] = abs_w * (x - rank * raw_rx * dot);
    gy[i] = abs_w * (y - rank * raw_ry * dot);
  }
  const double residual_scale = gfac / (abs_w * sqrt_h);
  rx = residual_scale * raw_rx;
  ry = residual_scale * raw_ry;
}

template <int CD>
__global__ void W6ProposeWeights(
    const int* ci, const int* pi, const double* uv, const double* R,
    const double* t, const double* X, const double* f, const double* k1,
    const double* k2, const double* step, const double* current,
    int nobs, int ncam, double k2mask, double tau2, double lambda,
    double* proposed) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  if (o >= nobs) return;
  const int c = ci[o], p = pi[o];
  const double* Rc = R + 9 * c;
  const double* Xp = X + 3 * p;
  double gx[CD + 3], gy[CD + 3], rx, ry;
  if constexpr (CD == 9) {
    BalResidualGrad12(Rc[0], Rc[1], Rc[2], Rc[3], Rc[4], Rc[5],
        Rc[6], Rc[7], Rc[8], t[3*c], t[3*c+1], t[3*c+2],
        Xp[0], Xp[1], Xp[2], f[c], k1[c], k2[c], uv[2*o], uv[2*o+1],
        gx, gy, &rx, &ry);
    gx[8] *= k2mask; gy[8] *= k2mask;
  } else {
    double hx[81], hy[81];
    BalResidualGradHess(Rc[0], Rc[1], Rc[2], Rc[3], Rc[4], Rc[5],
        Rc[6], Rc[7], Rc[8], t[3*c], t[3*c+1], t[3*c+2],
        Xp[0], Xp[1], Xp[2], f[c], k1[c], k2[c], uv[2*o], uv[2*o+1],
        gx, gy, hx, hy);
    const double px = Rc[0]*Xp[0] + Rc[1]*Xp[1] + Rc[2]*Xp[2] + t[3*c];
    const double py = Rc[3]*Xp[0] + Rc[4]*Xp[1] + Rc[5]*Xp[2] + t[3*c+1];
    const double pz = Rc[6]*Xp[0] + Rc[7]*Xp[1] + Rc[8]*Xp[2] + t[3*c+2];
    const double xq = -px/pz, yq = -py/pz, rr = xq*xq + yq*yq;
    const double dist = 1.0 + k1[c]*rr + k2[c]*rr*rr;
    rx = f[c]*dist*xq - uv[2*o];
    ry = f[c]*dist*yq - uv[2*o+1];
  }
  const double* dc = step + CD * c;
  const double* dp = step + CD * ncam + 3 * p;
  double jx = 0.0, jy = 0.0;
  for (int q = 0; q < CD; ++q) { jx += gx[q] * dc[q]; jy += gy[q] * dc[q]; }
  for (int q = 0; q < 3; ++q) {
    jx += gx[CD+q] * dp[q]; jy += gy[CD+q] * dp[q];
  }
  const double w = current[o], w2 = w*w;
  const double r2 = rx*rx + ry*ry;
  const double denom = r2 + 2.0*tau2*w2 + lambda;
  const double num = r2 + tau2*(w2 - 1.0) + rx*jx + ry*jy;
  double next = denom > 0.0 ? w - w*num/denom : w;
  proposed[o] = isfinite(next) ? next : w;
}

__global__ void W6LiftedCostKernel(
    const int* ci, const int* pi, const double* uv, const double* R,
    const double* t, const double* X, const double* f, const double* k1,
    const double* k2, const double* weights, int nobs, double tau2,
    double* out) {
  int o = blockIdx.x * blockDim.x + threadIdx.x;
  double value = 0.0;
  if (o < nobs) {
    const int c = ci[o], p = pi[o];
    const double* Rc = R + 9*c; const double* Xp = X + 3*p;
    const double px = Rc[0]*Xp[0]+Rc[1]*Xp[1]+Rc[2]*Xp[2]+t[3*c];
    const double py = Rc[3]*Xp[0]+Rc[4]*Xp[1]+Rc[5]*Xp[2]+t[3*c+1];
    const double pz = Rc[6]*Xp[0]+Rc[7]*Xp[1]+Rc[8]*Xp[2]+t[3*c+2];
    const double xq = -px/pz, yq = -py/pz, rr = xq*xq+yq*yq;
    const double dist = 1.0+k1[c]*rr+k2[c]*rr*rr;
    const double rx = f[c]*dist*xq-uv[2*o];
    const double ry = f[c]*dist*yq-uv[2*o+1];
    const double w2 = weights[o]*weights[o];
    const double q = w2-1.0;
    value = 0.5*(w2*(rx*rx+ry*ry) + 0.5*tau2*q*q);
    if (!isfinite(value)) value = INFINITY;
  }
  __shared__ double sum[256]; sum[threadIdx.x] = value; __syncthreads();
  for (int d = 128; d > 0; d >>= 1) {
    if (threadIdx.x < d) sum[threadIdx.x] += sum[threadIdx.x+d];
    __syncthreads();
  }
  if (threadIdx.x == 0) atomicAdd(out, sum[0]);
}
