#include "../gpu/lambda_hysteresis.h"
#include <cassert>
#include <limits>
int main(){
 double s[]={.01,.1,1,10,100},c[]={90,90.4,91,99,100};
 assert(PrismHysteresisChoice(100,c,s,5,.1,.95)==1);
 assert(PrismHysteresisChoice(100,c,s,5,1,.95)==1); // closer 1 loses too much
 assert(PrismHysteresisChoice(100,c,s,5,.1,1)==0); // zero regret
 assert(PrismHysteresisChoice(100,c,s,5,NAN,.95)==-1);
 assert(PrismHysteresisChoice(89,c,s,5,1,.95)==-1);
 c[0]=NAN;c[1]=INFINITY;
 assert(PrismHysteresisChoice(100,c,s,5,1,.95)==2);
 // Units/scale of the objective and common rescaling of lambdas must not
 // change which candidate qualifies or is closest.
 double a[]={10,10.4,11,19,20},b[]={90,90.4,91,99,100},t[]={1,10,100,1000,10000};
 assert(PrismHysteresisChoice(20,a,s,5,.1,.95)==PrismHysteresisChoice(100,b,t,5,10,.95));
}
