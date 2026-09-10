#include <ceres/ceres.h>
#include <cstdlib>
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
  struct Item{int iter;double cost,time;bool accepted;};
  std::vector<Item> rows;
  double target=std::getenv("CERES_TARGET_COST")?std::atof(std::getenv("CERES_TARGET_COST")):0;
  ceres::CallbackReturnType operator()(const ceres::IterationSummary& s)override {
    rows.push_back({s.iteration,s.cost,s.cumulative_time_in_seconds,s.step_is_successful});
    return target>0 && s.cost<=target ? ceres::SOLVER_TERMINATE_SUCCESSFULLY : ceres::SOLVER_CONTINUE;
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
 Trace trace;options.callbacks.push_back(&trace);
 options.update_state_every_iteration=true;
 if(std::getenv("CERES_MAX_SECONDS"))options.max_solver_time_in_seconds=std::atof(std::getenv("CERES_MAX_SECONDS"));
 const double setup=std::chrono::duration<double>(std::chrono::steady_clock::now()-t0).count();
 auto solve0=std::chrono::steady_clock::now();ceres::Solver::Summary summary;ceres::Solve(options,&problem,&summary);
 const double elapsed=std::chrono::duration<double>(std::chrono::steady_clock::now()-solve0).count();
 const double checked=cost();
 std::printf("INITIAL score=%.17g setup_seconds=%.9f\n",initial,setup);
 std::printf("RESULT exit=%d iters=%zu final_score=%.17g runtime=%.9f\n",(int)summary.termination_type,summary.iterations.size(),summary.final_cost,elapsed);
 for(const auto&t:trace.rows)std::printf("TRACE iter=%d cost=%.17g seconds=%.9f accepted=%d\n",t.iter,t.cost,t.time,(int)t.accepted);
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
