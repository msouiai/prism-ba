// Gate: oca_core must reproduce the oca_cuda CLI on a real BAL problem.
// Same problem, same options -> same cost trajectory.
#include "oca_core.h"
#include <cmath>
#include <cstdio>
#include <fstream>
#include <vector>

int main(int argc, char** argv) {
  const char* path = argv[1];
  bool dof9 = argc > 2 && std::string(argv[2]) == "dof9";
  double tau = argc > 3 ? atof(argv[3]) : 3e-3;

  std::ifstream fh(path);
  int nc, np, no; fh >> nc >> np >> no;
  std::vector<int> ci(no), pi(no); std::vector<double> uv(2*no);
  for (int o = 0; o < no; ++o) fh >> ci[o] >> pi[o] >> uv[2*o] >> uv[2*o+1];
  std::vector<double> cams(9*nc), pts(3*np);
  for (auto& v : cams) fh >> v;
  for (auto& v : pts) fh >> v;

  std::vector<double> R(9*nc), t(3*nc), f(nc), k1(nc), k2(nc);
  for (int c = 0; c < nc; ++c) {
    const double* w = &cams[9*c];
    double th = std::sqrt(w[0]*w[0] + w[1]*w[1] + w[2]*w[2]);
    double kx = th ? w[0]/th : 0, ky = th ? w[1]/th : 0, kz = th ? w[2]/th : 0;
    double s = std::sin(th), cth = 1 - std::cos(th);
    double K[9] = {0,-kz,ky, kz,0,-kx, -ky,kx,0};
    double KK[9];
    for (int i=0;i<3;i++) for (int j=0;j<3;j++) {
      double a=0; for(int m=0;m<3;m++) a+=K[3*i+m]*K[3*m+j]; KK[3*i+j]=a; }
    for (int i=0;i<9;i++) R[9*c+i] = (i%4==0 ? 1.0 : 0.0) + s*K[i] + cth*KK[i];
    t[3*c]=w[3]; t[3*c+1]=w[4]; t[3*c+2]=w[5];
    f[c]=w[6]; k1[c]=w[7]; k2[c]=0.0;   // matches --zero_k2
  }

  oca::Problem pr;
  pr.num_cameras=nc; pr.num_points=np; pr.num_observations=no;
  pr.camera_index=ci.data(); pr.point_index=pi.data(); pr.observations=uv.data();
  oca::State st;
  st.rotations=R.data(); st.translations=t.data(); st.points=pts.data();
  st.focal=f.data(); st.k1=k1.data(); st.k2=k2.data();
  oca::Options opt;
  opt.max_iterations=61; opt.refine_intrinsics=dof9;
  opt.point_damping=tau; opt.use_fp32_fragments=true;

  oca::Result r = oca::Solve(pr, opt, &st);
  if (!r.success) { std::fprintf(stderr, "FAIL: %s\n", r.message.c_str()); return 1; }
  std::printf("CORE  final_cost=%.6f  medA %.6f -> %.6f  iters=%d\n",
              r.final_cost, r.initial_median_error_px, r.final_median_error_px,
              r.iterations);
  return 0;
}
