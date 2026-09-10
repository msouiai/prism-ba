#include "rl_damping.h"
#include <cassert>
#include <cstdlib>
#include <fstream>

static void valid(PrismRLDamping& p){
  p.history_count=1;p.history[0]=-3;p.history[2]=1;p.history[3]=-2;p.history[7]=1;
}
int main(int argc,char** argv){
  assert(argc==2);
  std::ofstream(argv[1])<<"PRISM_RLD_EPISODE_V1 3 2 .95 .125 1\n";
  setenv("OCA_RLD_EPISODE",argv[1],1);
  PrismRLDamping p;valid(p);
  assert(p.Action(1)==1);assert(p.Action(2)==0);assert(p.Action(3)==1);
  assert(p.Action(5)==0 && p.episode_actions==2);
  for(int field:{8,9}){
    PrismRLDamping q;valid(q);q.history[field]=1;
    assert(q.Action(1)==0 && q.episode_fallback);
    q.history[field]=0;assert(q.Action(3)==0);
  }
  for(double rho:{.1,2.}){
    PrismRLDamping q;valid(q);q.history[2]=rho;
    assert(q.Action(1)==0 && q.episode_fallback);
  }
  PrismRLDamping q;valid(q);q.history[3]=-8;
  assert(q.Action(1)==0 && q.episode_fallback);
  PrismRLDamping r;valid(r);r.history[0]=2;
  assert(r.Action(1)==0 && !r.episode_fallback);
  r.history[0]=-3;r.history[7]=0;assert(r.Action(2)==-1);
  PrismRLDamping failed;failed.Begin(0,0,0,100);
  failed.End(1,false,.1,.1,1e-16,1,1,0,1,1,.5,1,128,2,1,0,100,1,1,1);
  assert(failed.episode_fallback && !failed.previous_accepted);
  setenv("OCA_RLD_LOAD","unsupported",1);
  bool rejected=false;try{PrismRLDamping s;}catch(const std::runtime_error&){rejected=true;}
  assert(rejected);
}
