#include "reference_forcing.h"
#include <cassert>
int main(){
 PrismReferenceForcing x;assert(x.Forcing(0,.2,0)==.2);
 x.mode=1;assert(x.Forcing(0,.2,0)==.4);
 assert(!x.Accept(false,10,.1));assert(!x.have);
 x.mode=2;assert(x.Forcing(0,.2,0)==.5);
 assert(x.Accept(true,10,.1));assert(x.NeedQuery(1,0));
 x.Reference(1,2);assert(!x.NeedQuery(1,0));
 double e=x.Forcing(1,.4,0);assert(std::abs(e-.072)<1e-15);
 assert(x.Forcing(1,.01,0)==e);assert(x.previous_tau==.1);
 assert(!x.Accept(false,99,10));assert(x.previous_norm==10);
 assert(!x.NeedQuery(2,1));assert(x.Forcing(2,.1,1)==.2);
 assert(!x.Accept(true,1,1));
 PrismReferenceForcing y;y.mode=3;y.Accept(true,10,.1);y.Reference(0,.01);
 assert(std::abs(y.Forcing(0,.01,0)-.225)<1e-15);
 std::puts("PASS: accepted anchors, retry idempotence, safeguard and repair fallback");
}
