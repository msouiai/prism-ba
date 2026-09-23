// Copyright (c), ETH Zurich and UNC Chapel Hill.
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:
//
//     * Redistributions of source code must retain the above copyright
//       notice, this list of conditions and the following disclaimer.
//
//     * Redistributions in binary form must reproduce the above copyright
//       notice, this list of conditions and the following disclaimer in the
//       documentation and/or other materials provided with the distribution.
//
//     * Neither the name of ETH Zurich and UNC Chapel Hill nor the names of
//       its contributors may be used to endorse or promote products derived
//       from this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
// ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDERS OR CONTRIBUTORS BE
// LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
// CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
// SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
// INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
// CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
// ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
// POSSIBILITY OF SUCH DAMAGE.
//
// Ceres/C++ port of the consensus-ADMM bundle adjustment benchmark developed
// in /workspace/bundle_adjustment/muellcontainer_consensus_ba/ (Python) and
// /workspace/bundle_adjustment/venice_consensus_ba/. Same BAL problem, same
// algorithm (centralized LM+Schur baseline vs per-camera consensus ADMM with
// bounded adaptive-rho residual balancing), reimplemented with real Ceres
// solves per subproblem instead of hand-rolled Gauss-Newton, and real
// std::thread parallelism instead of Python's multiprocessing workaround
// (no GIL to escape in C++, so plain threads suffice for true parallelism).
//
// Both the centralized problem and each ADMM agent's local problem hold
// camera intrinsics (f, k1, k2) constant and only refine pose (6 DoF) +
// structure, matching every prior experiment in this investigation.

#include <ceres/ceres.h>
#include <ceres/rotation.h>

#include <Eigen/Core>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <iostream>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace {

using Clock = std::chrono::steady_clock;
double ElapsedSeconds(Clock::time_point t0) {
  return std::chrono::duration<double>(Clock::now() - t0).count();
}

// ---------------------------------------------------------------- BAL model
// Matches ceres-solver's own examples/snavely_reprojection_error.h exactly,
// which is also the model bal.py (the Python side of this investigation)
// implements: angle-axis rotation, negative-z projection, 2-term radial
// distortion. camera[0..8] = (angle-axis[3], t[3], f, k1, k2).
struct BalReprojectionError {
  BalReprojectionError(double observed_x, double observed_y)
      : observed_x(observed_x), observed_y(observed_y) {}

  template <typename T>
  bool operator()(const T* const camera,
                   const T* const point,
                   T* residuals) const {
    T p[3];
    ceres::AngleAxisRotatePoint(camera, point, p);
    p[0] += camera[3];
    p[1] += camera[4];
    p[2] += camera[5];

    const T xp = -p[0] / p[2];
    const T yp = -p[1] / p[2];

    const T& l1 = camera[7];
    const T& l2 = camera[8];
    const T r2 = xp * xp + yp * yp;
    const T distortion = 1.0 + r2 * (l1 + l2 * r2);

    const T& focal = camera[6];
    residuals[0] = focal * distortion * xp - T(observed_x);
    residuals[1] = focal * distortion * yp - T(observed_y);
    return true;
  }

  static ceres::CostFunction* Create(double observed_x, double observed_y) {
    return new ceres::AutoDiffCostFunction<BalReprojectionError, 2, 9, 3>(
        new BalReprojectionError(observed_x, observed_y));
  }

  double observed_x;
  double observed_y;
};

// -------------------------------------------------------------- BAL loading
struct BalProblem {
  int num_cameras = 0;
  int num_points = 0;
  int num_observations = 0;
  std::vector<int> cam_idx;
  std::vector<int> pt_idx;
  std::vector<double> uv;       // 2 * num_observations
  std::vector<double> cameras;  // 9 * num_cameras
  std::vector<double> points;   // 3 * num_points
};

BalProblem LoadBal(const std::string& path) {
  std::ifstream fh(path);
  if (!fh) {
    std::cerr << "Failed to open " << path << std::endl;
    std::exit(EXIT_FAILURE);
  }
  BalProblem prob;
  fh >> prob.num_cameras >> prob.num_points >> prob.num_observations;
  prob.cam_idx.resize(prob.num_observations);
  prob.pt_idx.resize(prob.num_observations);
  prob.uv.resize(2 * prob.num_observations);
  for (int i = 0; i < prob.num_observations; ++i) {
    fh >> prob.cam_idx[i] >> prob.pt_idx[i] >> prob.uv[2 * i] >>
        prob.uv[2 * i + 1];
  }
  prob.cameras.resize(9 * prob.num_cameras);
  for (double& v : prob.cameras) fh >> v;
  prob.points.resize(3 * prob.num_points);
  for (double& v : prob.points) fh >> v;
  return prob;
}

double TotalCost(const BalProblem& p,
                  const std::vector<double>& cameras,
                  const std::vector<double>& points) {
  double sum_sq = 0.0;
  for (int i = 0; i < p.num_observations; ++i) {
    const double* cam = &cameras[9 * p.cam_idx[i]];
    const double* pt = &points[3 * p.pt_idx[i]];
    double res[2];
    BalReprojectionError functor(p.uv[2 * i], p.uv[2 * i + 1]);
    functor(cam, pt, res);
    sum_sq += res[0] * res[0] + res[1] * res[1];
  }
  return 0.5 * sum_sq;
}

double Rmse(double cost, int num_observations) {
  return std::sqrt(cost * 2.0 / num_observations);
}

// Consensus-penalty residual: sqrt(rho) * (point - target), i.e. the
// residual of ceres::NormalPrior(sqrt(rho)*I, target) -- but implemented as
// a templated AutoDiffCostFunction functor (like BalReprojectionError)
// rather than using ceres::NormalPrior directly. NormalPrior is a
// precompiled, non-template class in libceres.a that stores Eigen::Matrix /
// Eigen::Vector as direct value members; passing Eigen types across that
// library-ABI boundary segfaulted (free() on a bogus pointer inside
// ~NormalPrior) when this file's Eigen config didn't exactly match how the
// prebuilt library was compiled. AutoDiffCostFunction is header-only and
// instantiated entirely within this translation unit, so it has no such
// boundary to mismatch across.
struct ConsensusPriorError {
  ConsensusPriorError(double sqrt_rho, const double* target)
      : sqrt_rho(sqrt_rho) {
    target_[0] = target[0];
    target_[1] = target[1];
    target_[2] = target[2];
  }

  template <typename T>
  bool operator()(const T* const point, T* residuals) const {
    residuals[0] = T(sqrt_rho) * (point[0] - T(target_[0]));
    residuals[1] = T(sqrt_rho) * (point[1] - T(target_[1]));
    residuals[2] = T(sqrt_rho) * (point[2] - T(target_[2]));
    return true;
  }

  static ceres::CostFunction* Create(double sqrt_rho, const double* target) {
    return new ceres::AutoDiffCostFunction<ConsensusPriorError, 3, 3>(
        new ConsensusPriorError(sqrt_rho, target));
  }

  double sqrt_rho;
  double target_[3];
};

// Fixes f, k1, k2 (indices 6,7,8) of a 9-param camera block, leaving the
// angle-axis rotation + translation (indices 0..5) variable. Matches the
// Python side, which never touches f/k1/k2 in either solver.
ceres::Manifold* FixIntrinsicsManifold() {
  return new ceres::SubsetManifold(9, {6, 7, 8});
}

// ---------------------------------------------------------- centralized (baseline)
struct CentralizedResult {
  double wall_seconds = 0.0;
  double final_cost = 0.0;
  double final_rmse = 0.0;
  int iterations_used = 0;
  std::vector<double> cameras;
  std::vector<double> points;
};

CentralizedResult SolveCentralized(const BalProblem& p, int max_iterations) {
  CentralizedResult result;
  result.cameras = p.cameras;
  result.points = p.points;

  ceres::Problem problem;
  for (int i = 0; i < p.num_observations; ++i) {
    ceres::CostFunction* cost_function =
        BalReprojectionError::Create(p.uv[2 * i], p.uv[2 * i + 1]);
    problem.AddResidualBlock(cost_function,
                              nullptr,
                              &result.cameras[9 * p.cam_idx[i]],
                              &result.points[3 * p.pt_idx[i]]);
  }
  for (int c = 0; c < p.num_cameras; ++c) {
    problem.SetManifold(&result.cameras[9 * c], FixIntrinsicsManifold());
  }

  ceres::Solver::Options options;
  options.max_num_iterations = max_iterations;
  options.linear_solver_type = ceres::SPARSE_SCHUR;
  options.num_threads = static_cast<int>(std::thread::hardware_concurrency());
  options.minimizer_progress_to_stdout = true;

  ceres::Solver::Summary summary;
  const auto t0 = Clock::now();
  ceres::Solve(options, &problem, &summary);
  result.wall_seconds = ElapsedSeconds(t0);
  result.final_cost = TotalCost(p, result.cameras, result.points);
  result.final_rmse = Rmse(result.final_cost, p.num_observations);
  result.iterations_used = static_cast<int>(summary.iterations.size());
  std::cout << summary.BriefReport() << std::endl;
  return result;
}

// ------------------------------------------------------------- ADMM (consensus)
struct AgentIndex {
  std::vector<int> local_point_ids;      // sorted unique global point ids
  std::vector<int> obs_indices;          // indices into global obs arrays
  std::vector<int> obs_local_point_pos;  // position within local_point_ids
};

std::vector<AgentIndex> BuildAgentIndex(const BalProblem& p) {
  std::vector<AgentIndex> agents(p.num_cameras);
  std::vector<std::vector<int>> cam_obs(p.num_cameras);
  for (int i = 0; i < p.num_observations; ++i) {
    cam_obs[p.cam_idx[i]].push_back(i);
  }
  for (int j = 0; j < p.num_cameras; ++j) {
    AgentIndex& a = agents[j];
    a.obs_indices = cam_obs[j];
    std::vector<int> pids;
    pids.reserve(a.obs_indices.size());
    for (int oi : a.obs_indices) pids.push_back(p.pt_idx[oi]);
    a.local_point_ids = pids;
    std::sort(a.local_point_ids.begin(), a.local_point_ids.end());
    a.local_point_ids.erase(
        std::unique(a.local_point_ids.begin(), a.local_point_ids.end()),
        a.local_point_ids.end());
    a.obs_local_point_pos.resize(a.obs_indices.size());
    for (size_t k = 0; k < a.obs_indices.size(); ++k) {
      const int gp = p.pt_idx[a.obs_indices[k]];
      const auto it = std::lower_bound(
          a.local_point_ids.begin(), a.local_point_ids.end(), gp);
      a.obs_local_point_pos[k] =
          static_cast<int>(it - a.local_point_ids.begin());
    }
  }
  return agents;
}

// Solves one camera's local subproblem: its own pose (intrinsics fixed) +
// local copies of the points it observes, with a NormalPrior residual per
// local point pulling it toward `targets[k] = Z[local_point_ids[k]] - dual`.
// This is the direct analogue of agent_solve() in the Python code, but each
// local linearized step is now a real ceres::Solve instead of hand-rolled
// Gauss-Newton.
void AgentSolve(const BalProblem& p,
                 const AgentIndex& agent,
                 double rho,
                 int n_inner_iters,
                 double* camera,       // 9 values, in/out
                 std::vector<double>* local_points,  // 3*|local_point_ids|, in/out
                 const std::vector<double>& targets) {  // 3*|local_point_ids|
  ceres::Problem problem;
  for (size_t k = 0; k < agent.obs_indices.size(); ++k) {
    const int oi = agent.obs_indices[k];
    const int lp = agent.obs_local_point_pos[k];
    ceres::CostFunction* cost_function =
        BalReprojectionError::Create(p.uv[2 * oi], p.uv[2 * oi + 1]);
    problem.AddResidualBlock(
        cost_function, nullptr, camera, &(*local_points)[3 * lp]);
  }
  problem.SetManifold(camera, FixIntrinsicsManifold());

  // Consensus penalty: rho * ||x_local - target||^2, i.e. a residual
  // sqrt(rho)*(x - target) per local point (matches the Python
  // agent_solve's `V[...] += rho; gpt += rho*(Xloc - Ztgt)` term exactly).
  const double sqrt_rho = std::sqrt(rho);
  for (size_t lp = 0; lp < agent.local_point_ids.size(); ++lp) {
    problem.AddResidualBlock(
        ConsensusPriorError::Create(sqrt_rho, &targets[3 * lp]),
        nullptr,
        &(*local_points)[3 * lp]);
  }

  ceres::Solver::Options options;
  options.max_num_iterations = n_inner_iters;
  options.linear_solver_type = ceres::DENSE_SCHUR;
  options.num_threads = 1;
  options.minimizer_progress_to_stdout = false;
  options.logging_type = ceres::SILENT;
  ceres::Solver::Summary summary;
  ceres::Solve(options, &problem, &summary);
}

struct AdmmOptions {
  int n_outer = 40;
  double rho = 1e4;
  double alpha = 1.7;
  int n_inner_iters = 3;
  int num_threads = 1;  // 1 = serial dispatch, >1 = real std::thread parallel
  bool adaptive = false;
  double mu = 10.0;
  double tau_incr = 2.0;
  double tau_decr = 2.0;
  int adapt_until = -1;  // -1 = n_outer
  double rho_bound_decades = 1.0;
};

struct AdmmIterLog {
  int iter;
  double wall;
  double agent_phase;
  double coord_phase;
  double cost;
  double rmse;
  double primal_res;
  double dual_res;
  double rho;
};

struct AdmmResult {
  double wall_seconds = 0.0;
  double final_cost = 0.0;
  double final_rmse = 0.0;
  std::vector<AdmmIterLog> log;
};

// Splits agents into `num_threads` dynamically-claimed tasks, one worker
// std::thread per outer-iteration call. Real OS threads -- unlike Python,
// there is no GIL to route around, so this alone gives genuine parallelism
// without the process-pool/IPC machinery the Python side needed.
//
// Tried switching this to OpenMP (`#pragma omp parallel for`, both
// schedule(dynamic) and schedule(static)) on the theory that its runtime
// keeps a persistent worker pool alive across repeated parallel regions,
// avoiding the thread creation/teardown this function pays every outer
// iteration -- the analogue of the Python side's fix (persistent
// multiprocessing pool instead of spawning workers per round). Measured
// result: OpenMP was slower in both scheduling modes (7.0-7.9s vs 3.8-3.9s
// on the muellcontainer problem, 60 outer iters) -- its parallel-region
// fork-join overhead outweighs the thread-spawn cost it was meant to avoid,
// at least for tasks this short (single-digit-ms Ceres solves). A hand-rolled
// persistent thread pool (workers parked on a condition variable between
// rounds, not tied to a fork-join primitive) is the natural next thing to
// try if closing further; not implemented here since the OpenMP experiment
// already answered "is this worth pursuing further" with real numbers.
void RunAgentsThreaded(int num_cameras,
                        int num_threads,
                        const std::function<void(int)>& solve_one) {
  if (num_threads <= 1) {
    for (int j = 0; j < num_cameras; ++j) solve_one(j);
    return;
  }
  std::vector<std::thread> workers;
  std::atomic<int> next{0};
  for (int t = 0; t < num_threads; ++t) {
    workers.emplace_back([&]() {
      int j;
      while ((j = next.fetch_add(1)) < num_cameras) {
        solve_one(j);
      }
    });
  }
  for (auto& w : workers) w.join();
}

AdmmResult SolveAdmm(const BalProblem& p,
                      const std::vector<AgentIndex>& agents,
                      const AdmmOptions& opts) {
  AdmmResult result;
  const int adapt_until =
      opts.adapt_until < 0 ? opts.n_outer : opts.adapt_until;
  double rho = opts.rho;
  const double rho_min = opts.rho / std::pow(10.0, opts.rho_bound_decades);
  const double rho_max = opts.rho * std::pow(10.0, opts.rho_bound_decades);

  std::vector<double> cameras = p.cameras;
  std::vector<double> Z = p.points;  // shared consensus points
  std::vector<std::vector<double>> local_points(p.num_cameras);
  std::vector<std::vector<double>> dual(p.num_cameras);
  for (int j = 0; j < p.num_cameras; ++j) {
    const auto& lp_ids = agents[j].local_point_ids;
    local_points[j].resize(3 * lp_ids.size());
    dual[j].assign(3 * lp_ids.size(), 0.0);
    for (size_t k = 0; k < lp_ids.size(); ++k) {
      for (int d = 0; d < 3; ++d) {
        local_points[j][3 * k + d] = Z[3 * lp_ids[k] + d];
      }
    }
  }

  std::vector<int> point_owner_count(p.num_points, 0);
  for (int j = 0; j < p.num_cameras; ++j) {
    for (int gp : agents[j].local_point_ids) point_owner_count[gp]++;
  }

  double wall = 0.0;
  for (int k = 0; k < opts.n_outer; ++k) {
    // ---- agent phase: each camera solves its local subproblem ----
    const auto tic_agents = Clock::now();
    std::vector<std::vector<double>> targets(p.num_cameras);
    for (int j = 0; j < p.num_cameras; ++j) {
      const auto& lp_ids = agents[j].local_point_ids;
      targets[j].resize(3 * lp_ids.size());
      for (size_t lp = 0; lp < lp_ids.size(); ++lp) {
        for (int d = 0; d < 3; ++d) {
          targets[j][3 * lp + d] =
              Z[3 * lp_ids[lp] + d] - dual[j][3 * lp + d];
        }
      }
    }
    RunAgentsThreaded(p.num_cameras, opts.num_threads, [&](int j) {
      AgentSolve(p,
                 agents[j],
                 rho,
                 opts.n_inner_iters,
                 &cameras[9 * j],
                 &local_points[j],
                 targets[j]);
    });
    const double agent_phase = ElapsedSeconds(tic_agents);

    // ---- coordination: consensus average, over-relaxation, dual update ----
    const auto tic_coord = Clock::now();
    std::vector<double> Zprev = Z;
    std::vector<double> acc(3 * p.num_points, 0.0);
    std::vector<std::vector<double>> xhat(p.num_cameras);
    for (int j = 0; j < p.num_cameras; ++j) {
      const auto& lp_ids = agents[j].local_point_ids;
      xhat[j].resize(3 * lp_ids.size());
      for (size_t lp = 0; lp < lp_ids.size(); ++lp) {
        const int gp = lp_ids[lp];
        for (int d = 0; d < 3; ++d) {
          const double xh = opts.alpha * local_points[j][3 * lp + d] +
                             (1.0 - opts.alpha) * Zprev[3 * gp + d];
          xhat[j][3 * lp + d] = xh;
          acc[3 * gp + d] += xh + dual[j][3 * lp + d];
        }
      }
    }
    for (int gp = 0; gp < p.num_points; ++gp) {
      const int cnt = point_owner_count[gp];
      if (cnt == 0) continue;
      for (int d = 0; d < 3; ++d) Z[3 * gp + d] = acc[3 * gp + d] / cnt;
    }
    double primal_sq = 0.0, dual_res_sq = 0.0;
    for (int j = 0; j < p.num_cameras; ++j) {
      const auto& lp_ids = agents[j].local_point_ids;
      for (size_t lp = 0; lp < lp_ids.size(); ++lp) {
        const int gp = lp_ids[lp];
        for (int d = 0; d < 3; ++d) {
          dual[j][3 * lp + d] += xhat[j][3 * lp + d] - Z[3 * gp + d];
          const double r = local_points[j][3 * lp + d] - Z[3 * gp + d];
          primal_sq += r * r;
        }
      }
    }
    for (int gp = 0; gp < p.num_points; ++gp) {
      const int cnt = point_owner_count[gp];
      for (int d = 0; d < 3; ++d) {
        const double dz = Z[3 * gp + d] - Zprev[3 * gp + d];
        dual_res_sq += static_cast<double>(cnt) * cnt * dz * dz;
      }
    }
    const double r_norm = std::sqrt(primal_sq);
    const double s_norm = rho * std::sqrt(dual_res_sq);

    if (opts.adaptive && k < adapt_until) {
      double rho_new = rho;
      if (r_norm > opts.mu * s_norm && rho < rho_max) {
        rho_new = std::min(rho * opts.tau_incr, rho_max);
      } else if (s_norm > opts.mu * r_norm && rho > rho_min) {
        rho_new = std::max(rho / opts.tau_decr, rho_min);
      }
      if (rho_new != rho) {
        const double scale = rho / rho_new;
        for (auto& dj : dual) {
          for (double& v : dj) v *= scale;
        }
        rho = rho_new;
      }
    }
    const double coord_phase = ElapsedSeconds(tic_coord);

    wall += agent_phase + coord_phase;
    const double cost = TotalCost(p, cameras, Z);
    const double rmse = Rmse(cost, p.num_observations);
    result.log.push_back({k + 1,
                           wall,
                           agent_phase,
                           coord_phase,
                           cost,
                           rmse,
                           r_norm,
                           s_norm,
                           rho});
  }
  result.wall_seconds = wall;
  result.final_cost = result.log.back().cost;
  result.final_rmse = result.log.back().rmse;
  return result;
}

void PrintAdmmTrace(const std::string& label, const AdmmResult& r) {
  for (const auto& l : r.log) {
    if (l.iter % 10 != 0 && l.iter != 1) continue;
    std::printf(
        "  [%s] it%3d cost=%.5e rmse=%.4f primal=%.3e dual_res=%.3e "
        "rho=%.2e agents=%.3fs coord=%.3fs wall=%.1fs\n",
        label.c_str(),
        l.iter,
        l.cost,
        l.rmse,
        l.primal_res,
        l.dual_res,
        l.rho,
        l.agent_phase,
        l.coord_phase,
        l.wall);
  }
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) {
    std::cerr << "Usage: " << argv[0]
               << " <bal_problem.txt> [n_outer] [rho] [alpha]\n"
                  "  rho is problem-scale-dependent (not portable across BAL "
                  "files): 1e4 for muellcontainer, 1e6 for Venice, per the "
                  "hand-tuning in the Python side of this investigation."
               << std::endl;
    return EXIT_FAILURE;
  }
  const std::string bal_path = argv[1];
  const int n_outer = argc > 2 ? std::atoi(argv[2]) : 40;
  const double rho0 = argc > 3 ? std::atof(argv[3]) : 1e4;
  const double alpha0 = argc > 4 ? std::atof(argv[4]) : 1.7;

  const BalProblem p = LoadBal(bal_path);
  std::cout << "loaded " << bal_path << ": ncam=" << p.num_cameras
            << " npt=" << p.num_points << " nobs=" << p.num_observations
            << std::endl;
  const double init_cost = TotalCost(p, p.cameras, p.points);
  std::cout << "init cost=" << init_cost
            << " rmse=" << Rmse(init_cost, p.num_observations) << "px\n"
            << std::endl;

  const unsigned hw_threads = std::thread::hardware_concurrency();
  const int n_workers =
      std::min<int>(p.num_cameras, static_cast<int>(hw_threads));
  std::cout << "machine: " << hw_threads << " hw threads -> " << n_workers
            << " ADMM worker threads for " << p.num_cameras << " agents\n"
            << std::endl;

  std::cout << "== centralized Ceres SPARSE_SCHUR (baseline) ==" << std::endl;
  const CentralizedResult central = SolveCentralized(p, 15);
  std::printf(
      "centralized: wall=%.2fs iters=%d final cost=%.5e rmse=%.4fpx\n\n",
      central.wall_seconds,
      central.iterations_used,
      central.final_cost,
      central.final_rmse);

  const auto agents = BuildAgentIndex(p);
  const int n_inner = 3;

  std::cout << "== consensus ADMM: serial (1 thread), fixed rho ==" << std::endl;
  AdmmOptions serial_opts;
  serial_opts.n_outer = n_outer;
  serial_opts.rho = rho0;
  serial_opts.alpha = alpha0;
  serial_opts.n_inner_iters = n_inner;
  serial_opts.num_threads = 1;
  const AdmmResult serial = SolveAdmm(p, agents, serial_opts);
  PrintAdmmTrace("serial  ", serial);
  std::printf("serial ADMM (fixed rho): wall=%.2fs final cost=%.5e rmse=%.4fpx\n\n",
              serial.wall_seconds,
              serial.final_cost,
              serial.final_rmse);

  std::cout << "== consensus ADMM: parallel (" << n_workers
            << " std::thread), fixed rho ==" << std::endl;
  AdmmOptions parallel_opts = serial_opts;
  parallel_opts.num_threads = n_workers;
  const AdmmResult parallel = SolveAdmm(p, agents, parallel_opts);
  PrintAdmmTrace("parallel", parallel);
  std::printf(
      "parallel ADMM (fixed rho): wall=%.2fs final cost=%.5e rmse=%.4fpx\n\n",
      parallel.wall_seconds,
      parallel.final_cost,
      parallel.final_rmse);

  std::cout << "== consensus ADMM: parallel (" << n_workers
            << " std::thread), adaptive rho ==" << std::endl;
  AdmmOptions adaptive_opts = parallel_opts;
  adaptive_opts.adaptive = true;
  adaptive_opts.adapt_until = n_outer * 3 / 4;
  const AdmmResult adaptive = SolveAdmm(p, agents, adaptive_opts);
  PrintAdmmTrace("adaptive", adaptive);
  std::printf(
      "parallel ADMM (adaptive rho): wall=%.2fs final cost=%.5e rmse=%.4fpx "
      "final rho=%.2e\n\n",
      adaptive.wall_seconds,
      adaptive.final_cost,
      adaptive.final_rmse,
      adaptive.log.back().rho);

  std::cout << "== summary ==" << std::endl;
  std::printf("centralized (baseline):        wall=%7.2fs  cost=%.5e rmse=%.4fpx\n",
              central.wall_seconds, central.final_cost, central.final_rmse);
  std::printf("ADMM serial, fixed rho:        wall=%7.2fs  cost=%.5e rmse=%.4fpx\n",
              serial.wall_seconds, serial.final_cost, serial.final_rmse);
  std::printf("ADMM parallel(%dt), fixed rho:  wall=%7.2fs  cost=%.5e rmse=%.4fpx  speedup=%.2fx\n",
              n_workers, parallel.wall_seconds, parallel.final_cost,
              parallel.final_rmse, serial.wall_seconds / parallel.wall_seconds);
  std::printf("ADMM parallel(%dt), adaptive:   wall=%7.2fs  cost=%.5e rmse=%.4fpx\n",
              n_workers, adaptive.wall_seconds, adaptive.final_cost, adaptive.final_rmse);

  return EXIT_SUCCESS;
}
