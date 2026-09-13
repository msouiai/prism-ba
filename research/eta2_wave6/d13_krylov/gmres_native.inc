// D13: right-preconditioned restarted GMRES.  This branch is restricted by
// build_d13.py to the frozen champion's single-shift classical-LM path.
// Arnoldi minimizes the same Euclidean residual used by the forcing gate.
{
  if (L != 1 || CD != 9 || shared_intr || block_on || poly_on || mf_fp32 ||
      !classical_lm || !pcg || recycle_mode || cg_projection)
    throw std::runtime_error(
        "OCA_PCG_GMRES requires frozen single-shift unshared Hcc-PCG classical LM");

  const int cycle_width = d13_gmres->m;
  const int iteration_limit = std::min(maxck, 128);
  int total_iterations = 0;
  int products = 0;
  int cycles = 0;
  bool hit = false;
  bool breakdown = false;
  double maximum_estimate_error = 0.0;

  while (total_iterations < iteration_limit) {
    ++cycles;
    const double beta = std::sqrt(std::max((Scalar)0, rr));
    if (beta <= eta * nb) {
      hit = true;
      break;
    }

    Scalar* const V = d13_gmres->V;
    CUDA_CHECK(cudaMemcpy(V, r_, (size_t)n_c * sizeof(Scalar),
                          cudaMemcpyDeviceToDevice));
    const Scalar inverse_beta = 1.0 / beta;
    CUBLAS_CHECK(cublasDscal(blas, n_c, &inverse_beta, V, 1));

    std::vector<double> H((size_t)(cycle_width + 1) * cycle_width, 0.0);
    std::vector<double> cosine(cycle_width, 0.0), sine(cycle_width, 0.0);
    std::vector<double> g(cycle_width + 1, 0.0);
    g[0] = beta;
    int used = 0;
    double residual_estimate = beta;

    for (int j = 0; j < cycle_width && total_iterations < iteration_limit; ++j) {
      pcg->Apply(V + (size_t)j * n_c);
      KvS(pcg->z, Ap_);
      { const Scalar shift = shifts[0];
        CUBLAS_CHECK(cublasDaxpy(blas, n_c, &shift, pcg->z, 1, Ap_, 1)); }
      ++products;
      ++total_iterations;

      // Two-pass MGS keeps the small Arnoldi identity accurate even when the
      // BA spectrum spans many decades.
      for (int pass = 0; pass < 2; ++pass) {
        for (int i = 0; i <= j; ++i) {
          double coefficient = 0.0;
          CUBLAS_CHECK(cublasDdot(blas, n_c, V + (size_t)i * n_c, 1,
                                  Ap_, 1, &coefficient));
          H[(size_t)j * (cycle_width + 1) + i] += coefficient;
          coefficient = -coefficient;
          CUBLAS_CHECK(cublasDaxpy(blas, n_c, &coefficient,
                                   V + (size_t)i * n_c, 1, Ap_, 1));
        }
      }

      double next_norm = 0.0;
      CUBLAS_CHECK(cublasDnrm2(blas, n_c, Ap_, 1, &next_norm));
      H[(size_t)j * (cycle_width + 1) + j + 1] = next_norm;
      used = j + 1;
      if (next_norm > 1e-14 * beta) {
        CUDA_CHECK(cudaMemcpy(V + (size_t)(j + 1) * n_c, Ap_,
                              (size_t)n_c * sizeof(Scalar),
                              cudaMemcpyDeviceToDevice));
        const Scalar inverse_norm = 1.0 / next_norm;
        CUBLAS_CHECK(cublasDscal(blas, n_c, &inverse_norm,
                                 V + (size_t)(j + 1) * n_c, 1));
      } else {
        breakdown = true;
      }

      for (int i = 0; i < j; ++i) {
        const double a = H[(size_t)j * (cycle_width + 1) + i];
        const double b = H[(size_t)j * (cycle_width + 1) + i + 1];
        H[(size_t)j * (cycle_width + 1) + i] = cosine[i] * a + sine[i] * b;
        H[(size_t)j * (cycle_width + 1) + i + 1] =
            -sine[i] * a + cosine[i] * b;
      }
      const double a = H[(size_t)j * (cycle_width + 1) + j];
      const double b = H[(size_t)j * (cycle_width + 1) + j + 1];
      const double diagonal = std::hypot(a, b);
      if (!(diagonal > 0.0) || !std::isfinite(diagonal)) {
        breakdown = true;
        break;
      }
      cosine[j] = a / diagonal;
      sine[j] = b / diagonal;
      H[(size_t)j * (cycle_width + 1) + j] = diagonal;
      H[(size_t)j * (cycle_width + 1) + j + 1] = 0.0;
      const double old_g = g[j];
      g[j] = cosine[j] * old_g;
      g[j + 1] = -sine[j] * old_g;
      residual_estimate = std::abs(g[j + 1]);
      if (residual_estimate <= eta * nb || breakdown) break;
    }

    if (!used) break;
    std::vector<double> y(used, 0.0);
    for (int i = used - 1; i >= 0; --i) {
      double rhs = g[i];
      for (int j = i + 1; j < used; ++j)
        rhs -= H[(size_t)j * (cycle_width + 1) + i] * y[j];
      const double diagonal = H[(size_t)i * (cycle_width + 1) + i];
      if (!(std::abs(diagonal) > 0.0) || !std::isfinite(diagonal)) {
        breakdown = true;
        break;
      }
      y[i] = rhs / diagonal;
    }
    if (breakdown && !std::isfinite(y[0])) break;

    // Reapply the fixed Hcc inverse rather than storing M^-1 V.  This keeps
    // device storage at m+1 vectors and adds no Schur products.
    for (int j = 0; j < used; ++j) {
      pcg->Apply(V + (size_t)j * n_c);
      const Scalar coefficient = y[j];
      CUBLAS_CHECK(cublasDaxpy(blas, n_c, &coefficient, pcg->z, 1, xs[0], 1));
    }

    KvS(xs[0], Ap_);
    { const Scalar shift = shifts[0];
      CUBLAS_CHECK(cublasDaxpy(blas, n_c, &shift, xs[0], 1, Ap_, 1)); }
    ++products;
    CUDA_CHECK(cudaMemcpy(r_, bprime, (size_t)n_c * sizeof(Scalar),
                          cudaMemcpyDeviceToDevice));
    { const Scalar minus_one = -1.0;
      CUBLAS_CHECK(cublasDaxpy(blas, n_c, &minus_one, Ap_, 1, r_, 1)); }
    CUBLAS_CHECK(cublasDdot(blas, n_c, r_, 1, r_, 1, &rr));
    const double explicit_norm = std::sqrt(std::max((Scalar)0, rr));
    if (!std::isfinite(explicit_norm))
      throw std::runtime_error("D13 GMRES produced a non-finite residual");
    const double estimate_error =
        std::abs(explicit_norm - residual_estimate) /
        std::max(explicit_norm, 1e-300);
    maximum_estimate_error = std::max(maximum_estimate_error, estimate_error);
    if (estimate_error > 1e-8)
      throw std::runtime_error("D13 GMRES Arnoldi residual identity failed");
    if (explicit_norm <= eta * nb) {
      hit = true;
      break;
    }
    if (breakdown) break;
  }

  // Exact damped-quadratic decrease: b^T x - .5 x^T A x
  // = .5 x^T(b+r), using the explicit residual already paid above.
  CUDA_CHECK(cudaMemcpy(pv_, bprime, (size_t)n_c * sizeof(Scalar),
                        cudaMemcpyDeviceToDevice));
  { const Scalar one = 1.0;
    CUBLAS_CHECK(cublasDaxpy(blas, n_c, &one, r_, 1, pv_, 1)); }
  CUBLAS_CHECK(cublasDdot(blas, n_c, xs[0], 1, pv_, 1, &preds[0]));
  preds[0] *= 0.5;

  pcg->last_depth = total_iterations;
  cg_broke = hit;
  cg_it = hit ? std::max(0, total_iterations - 1) : total_iterations;
  std::printf(
      "D13_GMRES o=%d retry=%d m=%d iterations=%d products=%d cycles=%d "
      "true_relative=%.17g eta=%.17g hit=%d breakdown=%d estimate_error=%.3e\n",
      k, retries, cycle_width, total_iterations, products, cycles,
      std::sqrt(std::max((Scalar)0, rr)) / std::max((Scalar)1e-300, nb),
      (double)eta, (int)hit, (int)breakdown, maximum_estimate_error);
  ++d13_gmres_solves;
  d13_gmres_iterations += total_iterations;
  d13_gmres_products += products;
  if (prof) {
    cudaDeviceSynchronize();
    t_mv += std::chrono::duration<double>(now() - t0).count();
  }
}
