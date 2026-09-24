#include "repair_damping.h"
#include <cassert>
#include <cstdio>
#include <random>
#include <vector>

int main(){
  const double inf=std::numeric_limits<double>::infinity();
  const double nan=std::numeric_limits<double>::quiet_NaN();
  std::vector<double> v={-inf,-1e300,-10,-1,-0.,0.,1e-300,1.,10.,1e300,inf,nan};
  long checks=0,skips=0;
  auto check=[&](double f,double next,double g,double h){
    const bool eligible=PrismRepairDamping::ModelEligible(f,g,h);
    for(int mode=1;mode<=3;++mode){
      auto full=PrismRepairDamping::Decide(f,next,g,h,mode);
      auto gated=PrismRepairDamping::Decide(f,eligible?next:f,g,h,mode);
      assert(full.factor==gated.factor);
      assert(full.valid==gated.valid);
      assert(full.rho==gated.rho);
      assert(full.prediction==gated.prediction ||
        (std::isnan(full.prediction)&&std::isnan(gated.prediction)));
      ++checks;if(!eligible)++skips;
    }
  };
  for(double f:v)for(double n:v)for(double g:v)for(double h:v)check(f,n,g,h);
  // Exercise the strict prediction floor and both adjacent representable values.
  for(double f:{1.,100.,1e10}){
    double floor=64*std::numeric_limits<double>::epsilon()*f;
    for(double p:{std::nextafter(floor,0.),floor,std::nextafter(floor,inf)})
      check(f,std::nextafter(f,-inf),-p,0.);
  }
  std::mt19937_64 gen(73);std::uniform_real_distribution<double> dist(-100.,100.);
  for(int i=0;i<100000;++i)check(dist(gen),dist(gen),dist(gen),dist(gen));
  assert(PrismRepairDamping::ModelEligible(10,-2,1));
  assert(PrismRepairDamping::Decide(10,8,-2,1,2).factor==.5);
  std::printf("PASS checks=%ld skipped_cases=%ld\n",checks,skips);
}
