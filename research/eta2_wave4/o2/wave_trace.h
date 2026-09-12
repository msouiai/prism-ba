#pragma once
#include <cmath>
#include <cstdio>
#include <stdexcept>
#include <vector>

// N.run-compatible scalar composition trace. No device copy, gauge projection,
// extra norm, synchronization, or operator application. Unreached values are
// JSON null, never carried over from the previous attempt.
struct O2WaveRow {
  int outer=0,retry=0,accepts_before=0,pcg_iterations=0;
  double stage=1,lambda=NAN,tau=NAN,radius_before=NAN,radius_effective=NAN;
  double raw_norm=NAN,eta=NAN,rho=NAN;
  double lambda_after=NAN,radius_after=NAN,floor_before=NAN,floor_after=NAN;
  double cost_stage_before=NAN,cost_stage_after=NAN,cost_original_before=NAN,cost_original_after=NAN;
  bool accepted=false,numeric_repair=false,curvature_cutoff=false,observed=false;
};
struct O2WaveTrace {
  FILE* file=nullptr;
  std::vector<O2WaveRow> rows;
  explicit O2WaveTrace(const char* path){
    file=std::fopen(path,"w");if(!file)throw std::runtime_error("cannot open OCA_WAVE_TRACE output");
    rows.reserve(2048);
  }
  ~O2WaveTrace(){
    auto num=[&](const char* key,double value){std::fprintf(file,",\"%s\":",key);
      if(std::isfinite(value))std::fprintf(file,"%.17g",value);else std::fputs("null",file);};
    std::fputs("[",file);
    for(size_t i=0;i<rows.size();++i){const auto& r=rows[i];
      std::fprintf(file,"%s{\"outer\":%d,\"retry\":%d,\"accepts_before\":%d",i?",":"",r.outer,r.retry,r.accepts_before);
      num("lambda",r.lambda);num("tau",r.tau);num("radius_before",r.radius_before);num("radius_effective",r.radius_effective);
      num("raw_norm",r.raw_norm);num("raw_radius_ratio",r.radius_before>0?r.raw_norm/r.radius_before:NAN);
      num("effective_raw_radius_ratio",r.radius_effective>0?r.raw_norm/r.radius_effective:NAN);
      num("eta",r.eta);num("rho",r.rho);num("stage",r.stage);
      num("lambda_after",r.lambda_after);num("radius_after",r.radius_after);
      num("numeric_floor_before",r.floor_before);num("numeric_floor_after",r.floor_after);
      num("cost_stage_before",r.cost_stage_before);num("cost_stage_after",r.cost_stage_after);
      num("cost_original_before",r.cost_original_before);num("cost_original_after",r.cost_original_after);
      std::fprintf(file,",\"gauge_fraction\":null,\"top5_fraction\":null,\"gauge_seconds\":0,\"gauge_measured\":false,\"pcg_iterations\":%d,\"accepted\":%s,\"numeric_repair\":%s,\"curvature_cutoff\":%s,\"observed\":%s}",
        r.pcg_iterations,r.accepted?"true":"false",r.numeric_repair?"true":"false",r.curvature_cutoff?"true":"false",r.observed?"true":"false");
    }
    std::fputs("]\n",file);if(std::fclose(file))std::fprintf(stderr,"OCA_WAVE_TRACE write failed\n");
  }
};
struct O2WaveAttempt {
  O2WaveTrace* owner;
  StcgAttemptClock& clock;
  const double& lambda;const double& radius;const double& floor;const double& cost;
  const O2Runtime& runtime;
  O2WaveRow row;
  O2WaveAttempt(O2WaveTrace* o,StcgAttemptClock& a,const O2Runtime& rt,int outer,int retry,int accepts,
      const double& l,const double& r,const double& f,const double& c)
      :owner(o),clock(a),lambda(l),radius(r),floor(f),cost(c),runtime(rt){
    if(owner){row.outer=outer;row.retry=retry;row.accepts_before=accepts;
      row.stage=rt.on?O2Runtime::Stage(rt.index):1.;row.lambda=l;row.radius_before=r;row.floor_before=f;
      row.cost_stage_before=c;row.cost_original_before=rt.on?rt.original_cost:c;}
  }
  ~O2WaveAttempt(){if(owner){row.pcg_iterations=clock.row.pcg_iterations;row.accepted=clock.row.accepted;
    row.numeric_repair=clock.row.numeric_repair;row.curvature_cutoff=clock.row.cutoff;
    row.lambda_after=lambda;row.radius_after=radius;row.floor_after=floor;
    row.cost_stage_after=cost;row.cost_original_after=runtime.on?runtime.original_cost:cost;
    owner->rows.push_back(row);}}
};
