#include "cg_value.h"
#include <cassert>
int main(){
  PrismCGValue x;x.mode=2;x.Begin(0,0,0);
  assert(!x.Observe(100,1,.4,.01));assert(!x.Observe(10,2,.4,.01));
  assert(!x.Observe(1,3,.4,.01));assert(x.Observe(.1,4,.4,.01));
  x.Finish(false,0,0);x.Begin(0,0,0);
  for(int i=1;i<=8;++i)assert(!x.Observe(1./i,i,.4,.01));
  x.Finish(true,1,0);x.Begin(0,1,0);assert(!x.eligible);
  x.Begin(0,0,1);assert(x.disabled&&!x.eligible);
  x.Begin(0,0,0);assert(!x.eligible);
  PrismCGValue p;p.mode=1;p.Begin(0,0,0);
  for(int i=1;i<=8;++i)assert(!p.Observe(1./i,i,.4,.01));
  assert(p.proposals>0&&p.stops==0);
  PrismCGValue h;h.mode=2;h.Begin(1e9,0,0);
  for(int i=1;i<=8;++i)assert(!h.Observe(1./i,i,.4,.01));
  PrismCGValue r;r.mode=2;r.Begin(0,0,0);
  for(int i=1;i<=8;++i)assert(!r.Observe(1./i,i,.6,.01));
  PrismCGValue e;e.mode=2;e.Begin(0,0,0);
  for(int i=1;i<=8;++i)assert(!e.Observe(1./i,i,.001,.01));
}
