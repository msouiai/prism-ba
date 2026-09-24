#include "../gpu/adaptive_menu.h"
#include <cassert>
int main(){
 PrismAdaptiveMenu m;
 assert(m.Wide(0,0));
 m.Observe(10,0,1,1,true,false,false);
 assert(!m.Wide(2,0));assert(m.Wide(8,0));assert(m.Wide(3,1));
 m.Observe(0,1,1,1,true,false,false);assert(m.Wide(3,0));
 for(int k=0;k<5;++k)m.Observe(10,0,1,1,true,false,false);
 assert(!m.Wide(3,0));
 m.Observe(0,0,0,0,false,true,false);assert(m.Wide(3,0));
 m.Observe(0,0,0,0,false,false,true);assert(m.Wide(3,0));
 double v=m.value;m.Observe(0,0,0,0,false,false,false);assert(m.value==v);
 PrismAdaptiveMenu a,b;
 a.Observe(2,3,4,5,true,false,false);b.Observe(20,30,40,50,true,false,false);
 assert(std::abs(a.value-b.value)<1e-12);
}
