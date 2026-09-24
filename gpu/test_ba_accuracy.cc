#include "ba_accuracy.h"
#include <cassert>
int main(){
  assert(PrismBAAccuracy::EW(1,0,.5)==.5);
  assert(std::abs(PrismBAAccuracy::EW(.01,1,.5)-.225)<1e-15);
  assert(std::abs(PrismBAAccuracy::EW(.1,1,.1)-.009)<1e-15);
  PrismBAAccuracy a; assert(a.Forcing(0,.123,8)==.123);
  a.mode=2;a.Gradient(3,4);assert(a.Forcing(0,0,9)==.5);
  a.Gradient(.3,.4);double e=a.Forcing(1,0,2);assert(std::abs(e-.225)<1e-15);
  assert(a.Forcing(1,0,900)==e); // changed lambda/RHS within retry: same forcing
  a.mode=5;double x=a.NextLambda(true,.75,10,.1);assert(x==5);
  assert(a.NextLambda(false,-1,10,100)==100); // rejection escalation untouched
  assert(a.NextLambda(true,1,10,.1)==1);
  a.mode=0;assert(a.NextLambda(true,.25,10,.1)==.1);
  std::puts("PASS: forcing safeguards, retry idempotence, accepted-only damping control");
}
