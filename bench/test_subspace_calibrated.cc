#include "../gpu/subspace_box.h"
#include <cstdio>
int main(){double g,h,a,b,c,e;while(std::scanf("%lf %lf %lf %lf %lf %lf",&g,&h,&a,&b,&c,&e)==6){for(bool scalar:{false,true}){auto r=PrismSubspaceBox::Calibrated(g,h,a,b,c,e,scalar);std::printf("%.17g %.17g %.17g %d ",r.a,r.b,r.prediction,int(r.valid));}std::puts("");}}
