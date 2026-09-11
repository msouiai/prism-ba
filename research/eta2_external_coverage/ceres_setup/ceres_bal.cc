#include <ceres/ceres.h>
#include <cstdlib>
#include <algorithm>
#include <stdexcept>
#include <cstdint>
#include <ceres/rotation.h>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <memory>
#include <string>
#include <vector>
struct Residual {
  double u,v;
  template<class T> bool operator()(const T* c,const T* p,T* r)const {
    T q[3];ceres::AngleAxisRotatePoint(c,p,q);
    for(int j=0;j<3;++j)q[j]+=c[3+j];
    T x=-q[0]/q[2],y=-q[1]/q[2];
    T scale=c[6]*(T(1)+c[7]*(x*x+y*y));
    r[0]=scale*x-T(u);r[1]=scale*y-T(v);return true;
  }
};
struct Trace:ceres::IterationCallback {
  struct Item{int iter;double cost,time;bool accepted;int linear_iterations;};
  std::vector<Item> rows;
  double target=std::getenv("CERES_TARGET_COST")?std::atof(std::getenv("CERES_TARGET_COST")):0;
  ceres::CallbackReturnType operator()(const ceres::IterationSummary& s)override {
    rows.push_back({s.iteration,s.cost,s.cumulative_time_in_seconds,s.step_is_successful,s.linear_solver_iterations});
    std::printf("LIVE iter=%d cost=%.17g seconds=%.9f accepted=%d cg=%d\n",s.iteration,s.cost,s.cumulative_time_in_seconds,(int)s.step_is_successful,s.linear_solver_iterations);
    std::fflush(stdout);
    return target>0 && s.step_is_successful && s.cost<=target*(1.-1e-8) ? ceres::SOLVER_TERMINATE_SUCCESSFULLY : ceres::SOLVER_CONTINUE;
  }
};
int main(int argc,char**argv){
 if(argc<3){std::fprintf(stderr,"usage: ceres_bal BAL lm|dogleg [max_iter=600] [radius=10000] [threads=8]\n");return 1;}
 int nc,np,no;std::ifstream in(argv[1]);if(!(in>>nc>>np>>no))return 1;
 std::vector<int> ci(no),pi(no);std::vector<Residual> obs(no);
 for(int i=0;i<no;++i)in>>ci[i]>>pi[i]>>obs[i].u>>obs[i].v;
 std::vector<double> cams(8*nc),pts(3*np);
 for(int i=0;i<nc;++i){for(int j=0;j<8;++j)in>>cams[8*i+j];double k2;in>>k2;}
 for(auto&x:pts)in>>x;if(!in)return 1;
 auto cost=[&](){long double sum=0;for(int i=0;i<no;++i){double r[2];obs[i](cams.data()+8*ci[i],pts.data()+3*pi[i],r);sum+=.5L*((long double)r[0]*r[0]+(long double)r[1]*r[1]);}return (double)sum;};
 const double initial=cost();auto t0=std::chrono::steady_clock::now();
 const bool normalize=std::getenv("CERES_NORMALIZE") && std::atoi(std::getenv("CERES_NORMALIZE"));
 const bool strict=std::getenv("CERES_STRICT_STOP") && std::atoi(std::getenv("CERES_STRICT_STOP"));
 double center[3]={0.,0.,0.}; double world_scale=1.;
 if(normalize){
   std::vector<double> scratch(np);
   auto upper_median=[&](){auto mid=scratch.begin()+np/2;std::nth_element(scratch.begin(),mid,scratch.end());return *mid;};
   for(int j=0;j<3;++j){for(int i=0;i<np;++i)scratch[i]=pts[3*i+j];center[j]=upper_median();}
   for(int i=0;i<np;++i){scratch[i]=0.;for(int j=0;j<3;++j)scratch[i]+=std::abs(pts[3*i+j]-center[j]);}
   const double mad=upper_median();
   if(!(std::isfinite(mad)&&mad>0))throw std::runtime_error("Invalid normalization scale");
   world_scale=100./mad;
   for(int i=0;i<np;++i)for(int j=0;j<3;++j)pts[3*i+j]=world_scale*(pts[3*i+j]-center[j]);
   for(int i=0;i<nc;++i){double rotated_center[3];ceres::AngleAxisRotatePoint(cams.data()+8*i,center,rotated_center);
     for(int j=0;j<3;++j)cams[8*i+3+j]=world_scale*(cams[8*i+3+j]+rotated_center[j]);}
 }
 const double normalized_initial=cost();
 const double initial_relative_error=std::abs(initial-normalized_initial)/std::max(1.,std::abs(initial));
 if(!(std::isfinite(normalized_initial)&&initial_relative_error<1e-8))throw std::runtime_error("Normalization changed objective");
 std::printf("NORMALIZE enabled=%d center=%.17g,%.17g,%.17g scale=%.17g initial=%.17g transformed_initial=%.17g relerr=%.17g\n",(int)normalize,center[0],center[1],center[2],world_scale,initial,normalized_initial,initial_relative_error);
 std::fflush(stdout);
 ceres::Problem problem;auto ordering=std::make_shared<ceres::ParameterBlockOrdering>();
 for(int i=0;i<np;++i){problem.AddParameterBlock(pts.data()+3*i,3);ordering->AddElementToGroup(pts.data()+3*i,0);}
 for(int i=0;i<nc;++i){problem.AddParameterBlock(cams.data()+8*i,8);ordering->AddElementToGroup(cams.data()+8*i,1);}
 for(int i=0;i<no;++i)problem.AddResidualBlock(new ceres::AutoDiffCostFunction<Residual,2,8,3>(new Residual(obs[i])),nullptr,cams.data()+8*ci[i],pts.data()+3*pi[i]);
 ceres::Solver::Options options;options.max_num_iterations=argc>3?std::stoi(argv[3]):600;
 options.initial_trust_region_radius=argc>4?std::stod(argv[4]):10000;
 options.num_threads=argc>5?std::stoi(argv[5]):8;options.linear_solver_ordering=ordering;
 const bool dogleg=std::string(argv[2])=="dogleg";
 options.trust_region_strategy_type=dogleg?ceres::DOGLEG:ceres::LEVENBERG_MARQUARDT;
 options.linear_solver_type=dogleg?ceres::SPARSE_SCHUR:ceres::ITERATIVE_SCHUR;
 options.preconditioner_type=ceres::SCHUR_JACOBI;
 options.sparse_linear_algebra_library_type=ceres::SUITE_SPARSE;
 options.minimizer_progress_to_stdout=false;
 if(strict){options.gradient_tolerance=1e-16;options.function_tolerance=1e-16;options.parameter_tolerance=1e-16;}
 if(const char* e=std::getenv("CERES_INNER_ETA"))options.eta=std::stod(e);
 std::printf("SETUP_OPTIONS normalize=%d strict=%d eta=%.17g gradient_tolerance=%.17g function_tolerance=%.17g parameter_tolerance=%.17g\n",(int)normalize,(int)strict,options.eta,options.gradient_tolerance,options.function_tolerance,options.parameter_tolerance);
 Trace trace;options.callbacks.push_back(&trace);
 options.update_state_every_iteration=true;
 if(std::getenv("CERES_MAX_SECONDS"))options.max_solver_time_in_seconds=std::atof(std::getenv("CERES_MAX_SECONDS"));
 const double setup=std::chrono::duration<double>(std::chrono::steady_clock::now()-t0).count();
 auto solve0=std::chrono::steady_clock::now();ceres::Solver::Summary summary;ceres::Solve(options,&problem,&summary);
 const double elapsed=std::chrono::duration<double>(std::chrono::steady_clock::now()-solve0).count();
 if(normalize){
   for(int i=0;i<np;++i)for(int j=0;j<3;++j)pts[3*i+j]=pts[3*i+j]/world_scale+center[j];
   for(int i=0;i<nc;++i){double rotated_center[3];ceres::AngleAxisRotatePoint(cams.data()+8*i,center,rotated_center);
     for(int j=0;j<3;++j)cams[8*i+3+j]=cams[8*i+3+j]/world_scale-rotated_center[j];}
 }
 const double checked=cost();
 std::printf("INITIAL score=%.17g setup_seconds=%.9f\n",initial,setup);
 std::printf("RESULT exit=%d iters=%zu final_score=%.17g runtime=%.9f\n",(int)summary.termination_type,summary.iterations.size(),summary.final_cost,elapsed);
 for(const auto&t:trace.rows)std::printf("TRACE iter=%d cost=%.17g seconds=%.9f accepted=%d cg=%d\n",t.iter,t.cost,t.time,(int)t.accepted,t.linear_iterations);
 std::printf("CHECK final_score=%.17g\n",checked);
 std::printf("CERES %s\n",summary.FullReport().c_str());
 if(const char* path=std::getenv("CERES_STATE_OUT")) {
   std::ofstream out(path,std::ios::binary);
   out.write("PRISMS01",8);
   uint64_t dims[3]={(uint64_t)nc,(uint64_t)np,(uint64_t)no};out.write((char*)dims,sizeof(dims));
   std::vector<double> rotations(9*nc),translations(3*nc),intr(3*nc,0.);
   for(int i=0;i<nc;++i){
     ceres::AngleAxisToRotationMatrix(cams.data()+8*i,ceres::RowMajorAdapter3x3(rotations.data()+9*i));
     for(int j=0;j<3;++j)translations[3*i+j]=cams[8*i+3+j];
     intr[i]=cams[8*i+6];intr[nc+i]=cams[8*i+7];
   }
   for(const auto* v:{&rotations,&translations,&pts,&intr})out.write((const char*)v->data(),v->size()*sizeof(double));
   if(!out)return 3;
 }
 if(!summary.IsSolutionUsable()||!std::isfinite(checked)||std::abs(checked-summary.final_cost)>1e-6*std::max(1.,std::abs(checked)))return 2;
 return 0;
}
