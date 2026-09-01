// Minimal CPU-only driver for the instrumented port (review use).
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <cstring>
#include <string>
#include <vector>
#include <omp.h>
#include "mfree_cpu_instr.h"
struct Bal{int ncam=0,npt=0,nobs=0;std::vector<int>cam,pt;std::vector<double>uv,R,t,f,k1,k2,X;};
static bool Load(const std::string&p,Bal*b){FILE*fp=fopen(p.c_str(),"r");if(!fp)return false;
 if(fscanf(fp,"%d %d %d",&b->ncam,&b->npt,&b->nobs)!=3)return false;
 b->cam.resize(b->nobs);b->pt.resize(b->nobs);b->uv.resize(2*(size_t)b->nobs);
 for(int i=0;i<b->nobs;++i)if(fscanf(fp,"%d %d %lf %lf",&b->cam[i],&b->pt[i],&b->uv[2*i],&b->uv[2*i+1])!=4)return false;
 b->R.resize(9*(size_t)b->ncam);b->t.resize(3*(size_t)b->ncam);b->f.resize(b->ncam);b->k1.resize(b->ncam);b->k2.resize(b->ncam);
 for(int c=0;c<b->ncam;++c){double w[3],v;
  for(int j=0;j<3;++j)if(fscanf(fp,"%lf",&w[j])!=1)return false;
  oca_cpu::ExpSO3(w,&b->R[9*c]);
  for(int j=0;j<3;++j){if(fscanf(fp,"%lf",&v)!=1)return false;b->t[3*c+j]=v;}
  if(fscanf(fp,"%lf %lf %lf",&b->f[c],&b->k1[c],&b->k2[c])!=3)return false;}
 b->X.resize(3*(size_t)b->npt);
 for(size_t i=0;i<b->X.size();++i)if(fscanf(fp,"%lf",&b->X[i])!=1)return false;
 fclose(fp);return true;}
int main(int argc,char**argv){
 if(argc<3){printf("usage: %s <bal> <iters>\n",argv[0]);return 1;}
 Bal b; if(!Load(argv[1],&b)){printf("cannot read\n");return 1;}
 printf("loaded %s: %d cams %d pts %d obs\n",argv[1],b.ncam,b.npt,b.nobs);
 oca_cpu::Problem cp; cp.num_cameras=b.ncam;cp.num_points=b.npt;cp.num_observations=b.nobs;
 cp.camera_index=b.cam.data();cp.point_index=b.pt.data();cp.observations=b.uv.data();
 oca_cpu::State st; st.rotations=b.R.data();st.translations=b.t.data();st.points=b.X.data();
 st.focal=b.f.data();st.k1=b.k1.data();st.k2=b.k2.data();
 oca_cpu::Options o; o.max_iterations=atoi(argv[2]);
 o.func_tolerance = getenv("MF_FUNC_TOL")?atof(getenv("MF_FUNC_TOL")):0.0;
 o.max_consecutive_failures = getenv("MF_MAX_FAIL")?atoi(getenv("MF_MAX_FAIL")):0;
 o.verbose = getenv("MF_VERBOSE")!=nullptr;
 if(getenv("MF_RHO")) o.rho_lambda=true;
 if(getenv("MF_NO_ALPHA")) o.use_alpha=false;
 if(const char*e=getenv("MF_TAU")) o.point_damping=atof(e);
 if(const char*e=getenv("MF_LAM0")) o.initial_lambda=atof(e);
 if(getenv("MF_THREADS")) o.num_threads=atoi(getenv("MF_THREADS"));
 auto r=oca_cpu::Solve(cp,o,&st);
 printf("RESULT: %d iters, cost %.9e -> %.9e (matvecs %ld, accepts %d, rejects %d)\n",
        r.iterations,r.initial_cost,r.final_cost,r.total_matvecs,r.accepts,r.rejects);
 return 0;}
