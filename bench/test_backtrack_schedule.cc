#include "../gpu/backtrack_schedule.h"
#include <stdexcept>
#include <limits>
#include <cstdio>
static void check(bool b){if(!b)throw std::runtime_error("backtrack schedule test failed");}
int main(){
 // Exhaustive finite-menu coverage, including nonmonotone acceptance sets.
 for(int n=1;n<=12;++n)for(int first=0;first<n;++first)for(int mode=0;mode<=5;++mode){
  PrismBacktrackSchedule p(n,first,mode);unsigned mask=0;
  for(int k=0;k<n;++k){int i=p.Next();check(i>=0&&i<n&&!(mask&(1u<<i)));mask|=1u<<i;p.Failed(i,1e8,1,-10);}
  check(mask==(1u<<n)-1 && p.Next()==-1);
 }
 PrismBacktrackSchedule guarded(8,0,3);
 check(guarded.Next()==0);guarded.Failed(0,1e8,1,-10);
 check(guarded.Next()>1);
 PrismBacktrackSchedule up(8,0,4);
 check(up.Next()==0);up.next=4;check(up.Next()==4);
 check(up.Upward(4)&&up.Next()==3);
 check(up.Upward(3)&&up.Next()==2);
 check(up.Upward(2)&&up.Next()==1);
 check(!up.Upward(1)&&!up.Upward(0));
 // Prediction cannot discard a larger successful step after smaller failures.
 PrismBacktrackSchedule recover(8,5,1);int calls=0,idx;
 do{idx=recover.Next();check(idx>=0);++calls;}while(idx!=0);
 check(calls==4&&recover.recovery);
 // A dyadic near-minimum predicted from a known quadratic, plus invalid fits.
 check(PrismBacktrackSchedule::Quadratic(1,91,1,-10,8)==3);
 check(PrismBacktrackSchedule::Quadratic(.5,std::numeric_limits<double>::infinity(),1,-1,8)==1);
 check(PrismBacktrackSchedule::Quadratic(.5,1,1,1,8)==1);
 PrismBacktrackHistory h;bool predicted=true;
 check(h.Start(0,0,1,2,predicted)==0&&!predicted);
 h.Observe(0,0,1,2,6);
 for(int o=1;o<=8;++o){int i=h.Start(0,o,1,2,predicted);check(i==(o==8?0:5));h.Observe(0,o,1,2,6);}
 check(h.Start(1,9,1,2,predicted)==0); // lane separation
 check(h.Start(0,10,1,2,predicted)==0); // stale nonlinear history
 h.Observe(0,10,1,2,6);check(h.Start(0,11,2,2,predicted)==0); // camera damping
 h.Observe(0,11,1,2,6);check(h.Start(0,12,1,3,predicted)==0); // point damping
 h.Observe(0,12,1,2,-1);check(h.Start(0,13,1,2,predicted)==0); // failed search
 check(PrismBacktrackSchedule(0,0,0).Next()==-1);
 std::puts("PASS exhaustive coverage/uniqueness, larger-step recovery, interpolation, stale/damping resets and periodic full search");
}
