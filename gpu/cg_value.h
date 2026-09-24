#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <stdexcept>

// Surrogate model-gain rate, not a bound on remaining CG error.
struct PrismCGValue {
  int mode=0, depth=0, streak=0;
  bool eligible=false, reliable=true, disabled=false, stopped=false, verify=false;
  double gain=0, setup=0, last_post=0, last_time=0, max_error=0;
  std::array<double,3> gains{}, times{};
  long attempts=0, observations=0, proposals=0, stops=0, checks=0;
  PrismCGValue(){
    if(const char* s=std::getenv("OCA_CGV"))mode=std::atoi(s);
    verify=std::getenv("OCA_CGV_VERIFY")!=nullptr;
    if(mode<0||mode>4)throw std::runtime_error("invalid CG value mode");
    if(mode && (std::getenv("OCA_RRF")||std::getenv("OCA_BAC")||
       std::getenv("OCA_RLA_POLICY")||std::getenv("OCA_RLC_POLICY")||
       std::getenv("OCA_RLD_EPISODE")||std::getenv("OCA_RLD_LOAD")||std::getenv("OCA_RLD_SAVE")))
      throw std::runtime_error("CG value requires exclusive full-trajectory control");
  }
  void Begin(double setup_seconds,int retries,long repairs){
    if(repairs)disabled=true;
    eligible=!disabled&&reliable&&retries==0;
    setup=std::max(0.,setup_seconds)+last_post;
    gain=last_time=0;depth=streak=0;stopped=false;gains.fill(0);times.fill(0);++attempts;
  }
  bool Observe(double delta,double elapsed,double relative_residual,double eta){
    if(!mode)return false;
    ++observations;
    if(!(delta>=0&&std::isfinite(delta)&&std::isfinite(elapsed)&&elapsed>last_time)){
      eligible=false;return false;
    }
    const int slot=depth%3;
    gains[slot]=delta;times[slot]=elapsed-last_time;
    last_time=elapsed;gain+=delta;++depth;
    double dg=0,dt=0;for(int i=0;i<3;++i){dg+=gains[i];dt+=times[i];}
    const double theta=mode==3?.1:1.;
    // mode4: work-count comparator; modes1/2: elapsed-time rate, mode1 passive.
    const bool low=mode==4 ? dg/3<=gain/depth : dg/dt<=theta*gain/(setup+elapsed);
    const bool valid=eligible&&depth>=3&&gain>0&&relative_residual<=.5&&
                     relative_residual>eta&&std::isfinite(relative_residual)&&low;
    streak=valid?streak+1:0;
    const bool proposed=streak>=2;
    if(proposed)++proposals;
    if(mode!=1&&proposed){stopped=true;++stops;return true;}
    return false;
  }
  void Finish(bool accepted,double rho,double post_seconds){
    reliable=accepted&&std::isfinite(rho)&&rho>=.25;
    if(std::isfinite(post_seconds)&&post_seconds>=0)last_post=post_seconds;
  }
};
