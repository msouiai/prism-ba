#include "../gpu/demand_menu.h"
#include <cassert>
#include <iostream>
int main(){
 assert(PrismDemandMenu::Expand(false,0,.1,1e-5));
 assert(PrismDemandMenu::Expand(true,.01,.1,1e-5));
 assert(!PrismDemandMenu::Expand(true,.03,.1,1e-5));
 assert(PrismDemandMenu::Expand(true,1e-6,1e-6,1e-5));
 PrismDemandMenu p;
 p.Accept(.02,.004,false,1e-7);assert(!p.wide&&p.pair_known&&p.lambda==.02&&p.tau==.004);
 p.Accept(.02,.004,true,1e-7);assert(p.lambda==.01&&p.tau==.002);
 p.Reject(.01,.002,1e-7);assert(p.wide&&p.lambda==.1&&p.tau==.02);
 p.Reject(1e8,1e8,1e-7);assert(p.lambda==1e8&&p.tau==1e8);
 p.Accept(1e-7,1e-7,true,1e-7);assert(p.lambda==1e-7&&p.tau==1e-7);
 std::cout<<"demand policy transitions passed\n";
}
