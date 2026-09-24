#include "../gpu/subspace_box.h"
#include <cstdio>
int main(){double g,h,a,b,c;while(std::scanf("%lf %lf %lf %lf %lf",&g,&h,&a,&b,&c)==5){for(bool scalar:{false,true}){auto r=PrismSubspaceBox::Solve(g,h,a,b,c,scalar);std::printf("%.17g %.17g %.17g %d ",r.a,r.b,r.prediction,int(r.valid));}std::puts("");}}
