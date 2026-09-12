#pragma once
#include <chrono>
#include <cstdio>
#include <stdexcept>
#include <vector>

struct StcgAttemptRow {
  int outer=0,retry_index=0,pcg_iterations=0;
  bool retry_entry=false,accepted=false,cutoff=false,numeric_repair=false;
  long matvecs=0;
  double seconds=0;
};

struct StcgAttemptTrace {
  FILE* file=nullptr;
  std::vector<StcgAttemptRow> rows;
  explicit StcgAttemptTrace(const char* path) {
    file=std::fopen(path,"w");
    if(!file)throw std::runtime_error("cannot open STCG attempt trace");
    rows.reserve(1024);
  }
  ~StcgAttemptTrace() {
    long accepted=0,cutoffs=0,cutoff_accepts=0,pcg=0,mv=0,numeric=0;
    double total=0,retry=0,rejected=0,repair=0;
    std::fprintf(file,"{\"clock\":\"host_steady_no_added_gpu_sync\",\"rows\":[");
    for(size_t i=0;i<rows.size();++i){
      const auto& r=rows[i];
      accepted+=r.accepted;cutoffs+=r.cutoff;cutoff_accepts+=r.cutoff&&r.accepted;
      pcg+=r.pcg_iterations;mv+=r.matvecs;numeric+=r.numeric_repair;
      total+=r.seconds;if(r.retry_entry)retry+=r.seconds;
      if(!r.accepted)rejected+=r.seconds;if(r.numeric_repair)repair+=r.seconds;
      std::fprintf(file,"%s{\"outer\":%d,\"retry_index\":%d,\"retry_entry\":%s,\"accepted\":%s,\"curvature_cutoff\":%s,\"numeric_repair\":%s,\"pcg_iterations\":%d,\"matvecs\":%ld,\"seconds\":%.17g}",
        i?",":"",r.outer,r.retry_index,r.retry_entry?"true":"false",r.accepted?"true":"false",
        r.cutoff?"true":"false",r.numeric_repair?"true":"false",r.pcg_iterations,r.matvecs,r.seconds);
    }
    std::fprintf(file,"],\"totals\":{\"attempts\":%zu,\"accepted\":%ld,\"not_accepted\":%zu,\"curvature_cutoffs\":%ld,\"cutoff_accepts\":%ld,\"numeric_repairs\":%ld,\"pcg_iterations\":%ld,\"matvecs\":%ld,\"attempt_seconds\":%.17g,\"retry_entry_seconds\":%.17g,\"not_accepted_seconds\":%.17g,\"numeric_repair_seconds\":%.17g,\"retry_entry_wall_fraction\":%.17g,\"not_accepted_wall_fraction\":%.17g}}\n",
      rows.size(),accepted,rows.size()-accepted,cutoffs,cutoff_accepts,numeric,pcg,mv,total,retry,rejected,repair,
      total>0?retry/total:0,total>0?rejected/total:0);
    if(std::fclose(file))std::fprintf(stderr,"STCG attempt trace failed to close\n");
  }
};

// Lifetime is one entire attempt scope. A `continue` for numerical repair
// therefore records its work instead of disappearing from retry accounting.
// Native blocking dot products/cost evaluation define synchronization; this
// scope adds no CUDA call or barrier. Output is buffered until solver exit.
struct StcgAttemptClock {
  StcgAttemptTrace* owner;
  StcgAttemptRow row;
  const long* matvec_count;
  long start_matvecs=0;
  std::chrono::steady_clock::time_point start;
  StcgAttemptClock(StcgAttemptTrace* trace,int outer,int retry,bool reentry,const long* count)
      :owner(trace),matvec_count(count){
    if(owner){row.outer=outer;row.retry_index=retry;row.retry_entry=reentry;
      start_matvecs=*count;start=std::chrono::steady_clock::now();}
  }
  ~StcgAttemptClock(){
    if(owner){row.seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
      row.matvecs=*matvec_count-start_matvecs;owner->rows.push_back(row);}
  }
};
