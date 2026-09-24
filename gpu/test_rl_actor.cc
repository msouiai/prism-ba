#include "rl_actor.h"
#include <cassert>
#include <iostream>
int main(){
  PrismRLActor a;a.actor=true;a.na=5;a.history_count=1;a.history[0]=-3;
  a.history[2]=1;a.history[3]=-2;a.initial_cost=100;a.current_cost=50;
  auto x=a.Features();auto p=a.Probabilities(x);double sum=0;for(double v:p)sum+=v;
  assert(std::abs(sum-1)<1e-14);
  a.actor_weights[4*PrismRLActor::NAF]=5;
  a.Mark(1,50);assert(a.Action(1)==4);assert(a.LambdaFactor(4)==1);
  assert(a.Forcing(.1)==.2 && a.Forcing(.4)==.5);
  assert(a.Action(1)==0 && a.moves==1);
  a.Mark(2,40);assert(a.Action(2)==0 && a.Forcing(.1)==.1);
  a.Mark(3,30);assert(a.Action(3)==4 && a.moves==2);
  a.Mark(5,25);a.history[2]=.1;assert(a.Action(5)==0);
  a.Mark(6,20);a.history[2]=1;assert(a.Action(6)==4 && a.moves==3);
  a.Mark(8,15);assert(a.Action(8)==0);
  a.moves=0;a.last_move=-1000000;a.history[9]=1;
  a.Mark(10,12);assert(a.Action(10)==0&&a.repair_stop);
  a.history[9]=0;a.Mark(12,10);assert(a.Action(12)==0);
  assert(a.LambdaFactor(1)==.5 && a.LambdaFactor(2)==2);
  a.actor=false;assert(a.LambdaFactor(-1)==.1 && a.LambdaFactor(1)==10);
  std::cout<<"PASS: normalized policy, forcing bounds, action mapping, budget, cooldown, retry idempotence, repair stop\n";
}
