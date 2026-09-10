// Standalone BAL driver for the vendored Symforce-Caspar generated solver.
// Mirrors colmap_ba_compare's COLMAP_BAL_SIMPLE_RADIAL mapping exactly:
//   R_colmap = diag(1,-1,-1) * AA(aa),  t_colmap = diag(1,-1,-1) * t_bal,
//   pixel = (u, -v), camera = SIMPLE_RADIAL [f, k1] + pp (0,0), k2 dropped
// Double state and factors; independent CPU costs use original double pixels.
// Default settings mirror COLMAP; optional "paper" selects a different profile.
#include "solver.h"
#include "solver_params.h"
#include <cmath>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <fstream>
#include <vector>
#include <cstdint>

int main(int argc, char** argv) {
  if (argc < 2) { std::fprintf(stderr, "usage: %s bal.txt [max_iter]\n", argv[0]); return 1; }
  const int max_iter = argc > 2 ? std::atoi(argv[2]) : 200;

  std::ifstream fh(argv[1]);
  if (!fh.good()) { std::fprintf(stderr, "cannot open %s\n", argv[1]); return 1; }
  int ncam, npt, nobs;
  fh >> ncam >> npt >> nobs;
  std::vector<int> ocam(nobs), opt(nobs);
  std::vector<double> ou(nobs), ov(nobs);
  for (int i = 0; i < nobs; ++i) fh >> ocam[i] >> opt[i] >> ou[i] >> ov[i];
  std::vector<double> cp(9 * ncam);
  for (double& v : cp) fh >> v;
  std::vector<double> ptsd(3 * npt);
  for (double& v : ptsd) fh >> v;
  std::vector<double> pts(ptsd.begin(), ptsd.end());
  std::printf("loaded %s: %d cams %d pts %d obs (SIMPLE_RADIAL, k2 dropped)\n",
              argv[1], ncam, npt, nobs);


  // Node data.
  std::vector<double> pose(7 * ncam), calib(4 * ncam);
  for (int c = 0; c < ncam; ++c) {
    // Rodrigues
    const double ax=cp[9*c+0], ay=cp[9*c+1], az=cp[9*c+2];
    const double th=std::sqrt(ax*ax+ay*ay+az*az);
    double R[9]={1,0,0, 0,1,0, 0,0,1};
    if (th>1e-16){
      const double x=ax/th,y=ay/th,z=az/th,ct=std::cos(th),st=std::sin(th),vt=1-ct;
      R[0]=ct+x*x*vt;   R[1]=x*y*vt-z*st; R[2]=x*z*vt+y*st;
      R[3]=y*x*vt+z*st; R[4]=ct+y*y*vt;   R[5]=y*z*vt-x*st;
      R[6]=z*x*vt-y*st; R[7]=z*y*vt+x*st; R[8]=ct+z*z*vt;
    }
    // flip = diag(1,-1,-1): Rc = flip*R negates rows 1,2; tc likewise.
    double Rc[9]={R[0],R[1],R[2], -R[3],-R[4],-R[5], -R[6],-R[7],-R[8]};
    const double tc0=cp[9*c+3], tc1=-cp[9*c+4], tc2=-cp[9*c+5];
    // rotation matrix -> quaternion (w,x,y,z), standard Shepperd
    double qw,qx,qy,qz;
    const double tr=Rc[0]+Rc[4]+Rc[8];
    if (tr>0){ double s2=std::sqrt(tr+1.0)*2; qw=0.25*s2; qx=(Rc[7]-Rc[5])/s2; qy=(Rc[2]-Rc[6])/s2; qz=(Rc[3]-Rc[1])/s2; }
    else if (Rc[0]>Rc[4] && Rc[0]>Rc[8]){ double s2=std::sqrt(1.0+Rc[0]-Rc[4]-Rc[8])*2; qw=(Rc[7]-Rc[5])/s2; qx=0.25*s2; qy=(Rc[1]+Rc[3])/s2; qz=(Rc[2]+Rc[6])/s2; }
    else if (Rc[4]>Rc[8]){ double s2=std::sqrt(1.0+Rc[4]-Rc[0]-Rc[8])*2; qw=(Rc[2]-Rc[6])/s2; qx=(Rc[1]+Rc[3])/s2; qy=0.25*s2; qz=(Rc[5]+Rc[7])/s2; }
    else { double s2=std::sqrt(1.0+Rc[8]-Rc[0]-Rc[4])*2; qw=(Rc[3]-Rc[1])/s2; qx=(Rc[2]+Rc[6])/s2; qy=(Rc[5]+Rc[7])/s2; qz=0.25*s2; }
    pose[7*c+0]=qx; pose[7*c+1]=qy; pose[7*c+2]=qz; pose[7*c+3]=qw;
    pose[7*c+4]=tc0; pose[7*c+5]=tc1; pose[7*c+6]=tc2;
    // merged SimpleRadialCalib layout: [focal_and_extra (f,k) | principal_point (cx,cy)]
    calib[4*c+0]=cp[9*c+6]; calib[4*c+1]=cp[9*c+7]; calib[4*c+2]=0.0; calib[4*c+3]=0.0;
  }
  // Factors (BASE variant: everything tunable, merged calib).
  std::vector<unsigned> f_pose(nobs), f_calib(nobs), f_point(nobs);
  std::vector<double> f_pix(2 * nobs);
  for (int i = 0; i < nobs; ++i) {
    f_pose[i]  = static_cast<unsigned>(ocam[i]);
    f_calib[i] = static_cast<unsigned>(ocam[i]);
    f_point[i] = static_cast<unsigned>(opt[i]);
    f_pix[2*i+0] = ou[i];
    f_pix[2*i+1] = -ov[i];
  }

  caspar::SolverParams<double> params;
  // Defaults = CasparBundleAdjustmentOptions in COLMAP, i.e. the exact config
  // every local run in this study used. argv[3]=="paper" switches to the
  // Caspar paper settings (diag_init 100, CG tol 1e-3).
  params.solver_iter_max = max_iter > 0 ? max_iter : 200;
  params.pcg_iter_max = 20;
  params.diag_init = 1.0;
  params.diag_scaling_down = 0.333333;
  params.pcg_rel_error_exit = 1e-4;
  if (argc > 3 && std::string(argv[3]) == "paper") {
    params.diag_init = 100.0;
    params.pcg_rel_error_exit = 1e-3;
  }

  // Benchmark-only native target. Final raw-z CPU cost must independently qualify.
  if(const char* e=std::getenv("CASPAR_TARGET_COST")) {
    const double target=std::atof(e);
    if(!(std::isfinite(target) && target>0)) return 3;
    params.score_exit_value=static_cast<double>(target);
  }

  const auto setup_start = std::chrono::steady_clock::now();
  caspar::GraphSolver solver(
      params,
      /*PinholeCalib*/0, /*PinholeFocal*/0, /*PinholePose*/0, /*PinholePP*/0,
      /*Point*/ (size_t)npt,
      /*SimpleRadialCalib*/ 0,
      /*SimpleRadialFocalAndExtra*/ (size_t)ncam,
      /*SimpleRadialPose*/ (size_t)ncam,
      /*SimpleRadialPP*/0,
      /*simple_radial (BASE)*/ 0,
      0,0,0,   // sr fixed_pose / fixed_point / fixed_pose_fixed_point
      0,0,0,0, // pinhole variants
      // sr_split slots: fixed_fae, FIXED_PP <-- ours, then 9 more
      0,(size_t)nobs,0,0,0,0,0,0,0,0,0,
      0,0,0,0,0,0,0,0,0,0,0, // pinhole_split variants (11)
      /*device*/0);

  // Order mirrors the COLMAP backend exactly: nodes, then factors, then
  // finish_indices() LAST (adaptive reordering derives its permutation there).
  // FIXED_PP split variant: matches COLMAP default refine_principal_point=0,
  // i.e. the exact objective of every local Caspar run in the study.
  std::vector<double> fae(2 * (size_t)ncam);
  for (int c = 0; c < ncam; ++c) { fae[2*c+0]=calib[4*c+0]; fae[2*c+1]=calib[4*c+1]; }
  solver.SetPointNodesFromStackedHost(pts.data(), 0, npt);
  solver.SetSimpleRadialPoseNodesFromStackedHost(pose.data(), 0, ncam);
  solver.SetSimpleRadialFocalAndExtraNodesFromStackedHost(fae.data(), 0, ncam);

  solver.SetSimpleRadialSplitFixedPrincipalPointPoseIndicesFromHost(f_pose.data(), nobs);
  solver.SetSimpleRadialSplitFixedPrincipalPointFocalAndExtraIndicesFromHost(f_calib.data(), nobs);
  solver.SetSimpleRadialSplitFixedPrincipalPointPointIndicesFromHost(f_point.data(), nobs);
  solver.SetSimpleRadialSplitFixedPrincipalPointPixelDataFromStackedHost(f_pix.data(), 0, nobs);
  std::vector<double> sfr(7 * (size_t)nobs, 0.0);
  for (int i = 0; i < nobs; ++i) sfr[7*(size_t)i + 3] = 1.0;
  solver.SetSimpleRadialSplitFixedPrincipalPointSensorFromRigDataFromStackedHost(sfr.data(), 0, nobs);
  std::vector<double> ppc(2 * (size_t)nobs, 0.0);  // pp constant (0,0) per factor
  solver.SetSimpleRadialSplitFixedPrincipalPointPrincipalPointDataFromStackedHost(ppc.data(), 0, nobs);
  solver.finish_indices();

  auto CheckCost = [&](double projection_epsilon = 0.0) -> double {
  solver.GetPointNodesToStackedHost(pts.data(), 0, npt);
  solver.GetSimpleRadialPoseNodesToStackedHost(pose.data(), 0, ncam);
  solver.GetSimpleRadialFocalAndExtraNodesToStackedHost(fae.data(), 0, ncam);
  long double checked_score = 0;
  for (int i = 0; i < nobs; ++i) {
    const double* q = pose.data() + 7 * ocam[i];
    const double* p = pts.data() + 3 * opt[i];
    const double x=q[0], y=q[1], z=q[2], w=q[3];
    const double px=(1-2*(y*y+z*z))*p[0]+2*(x*y-z*w)*p[1]+2*(x*z+y*w)*p[2]+q[4];
    const double py=2*(x*y+z*w)*p[0]+(1-2*(x*x+z*z))*p[1]+2*(y*z-x*w)*p[2]+q[5];
    const double pz=2*(x*z-y*w)*p[0]+2*(y*z+x*w)*p[1]+(1-2*(x*x+y*y))*p[2]+q[6];
    const double denominator = projection_epsilon>0
        ? pz+std::copysign(projection_epsilon,pz) : pz;
    const double u=px/denominator, v=py/denominator;
    const double scale=fae[2*ocam[i]]*(1+fae[2*ocam[i]+1]*(u*u+v*v));
    const double du=scale*u-ou[i], dv=scale*v+ov[i];
    checked_score += 0.5L*(static_cast<long double>(du)*du+static_cast<long double>(dv)*dv);
  }
  return static_cast<double>(checked_score);
  };
  cudaDeviceSynchronize();
  const auto setup_end = std::chrono::steady_clock::now();
  std::printf("CHECK_INITIAL score=%.17g precision=f64\n", CheckCost());
  const char* audit_epsilon_env=std::getenv("CASPAR_AUDIT_EPSILON");
  const double audit_epsilon=audit_epsilon_env?std::atof(audit_epsilon_env):0;
  if(audit_epsilon>0) std::printf("CHECK_GUARDED_INITIAL epsilon=%.17g score=%.17g\n",
                                audit_epsilon,CheckCost(audit_epsilon));
  cudaDeviceSynchronize();
  const auto solve_start = std::chrono::steady_clock::now();
  const double setup_seconds = std::chrono::duration<double>(setup_end - setup_start).count();
  const caspar::SolveResult r = solver.solve(/*print_progress=*/true,
                                             /*verbose_logging=*/true);
  std::printf("RESULT exit=%d iters=%d final_score=%.17g runtime=%.9f\n",
              static_cast<int>(r.exit_reason), r.iteration_count, r.final_score, r.runtime);
  std::printf("INITIAL score=%.17g setup_seconds=%.9f\n", r.initial_score, setup_seconds);
  double previous_score = r.initial_score;
  for (const auto& it : r.iterations) {
    std::printf("TRACE iter=%d cost=%.17g seconds=%.9f accepted=%d pcg=%d\n",
                it.solver_iter, it.score_best, it.dt_tot,
                static_cast<int>(it.score_best < previous_score), it.pcg_iter);
    previous_score = it.score_best;
  }
  const double checked_score = CheckCost();
  std::printf("CHECK final_score=%.17g native_relerr=%.9g\n", checked_score,
              std::abs(checked_score-r.final_score)/std::max(1.0,std::abs(checked_score)));
  if(audit_epsilon>0) std::printf("CHECK_GUARDED_FINAL epsilon=%.17g score=%.17g\n",
                                audit_epsilon,CheckCost(audit_epsilon));
  if(const char* path=std::getenv("CASPAR_STATE_OUT")) {
    FILE* fs=std::fopen(path,"wbx");if(!fs) return 4;
    auto write=[&](const void* ptr,size_t bytes){if(std::fwrite(ptr,1,bytes,fs)!=bytes)throw std::runtime_error("state export failed");};
    uint64_t dims[3]={(uint64_t)ncam,(uint64_t)npt,(uint64_t)nobs};write("PRISMS01",8);write(dims,sizeof(dims));
    std::vector<double> rotations(9*ncam),translations(3*ncam),points(pts.begin(),pts.end()),intr(3*ncam,0);
    for(int c=0;c<ncam;++c){
      const double x=pose[7*c],y=pose[7*c+1],z=pose[7*c+2],w=pose[7*c+3];
      double R[9]={1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)};
      for(int i=0;i<9;++i)rotations[9*c+i]=(i<3?1:-1)*R[i];
      for(int i=0;i<3;++i)translations[3*c+i]=(i==0?1:-1)*pose[7*c+4+i];
      intr[c]=fae[2*c];intr[ncam+c]=fae[2*c+1];
    }
    for(const auto* v:{&rotations,&translations,&points,&intr})write(v->data(),v->size()*sizeof(double));
    if(std::fclose(fs))return 4;
  }
  if (!std::isfinite(checked_score)) return 2;
  return 0;
}
