#include "../gpu/repair_damping.h"
#include <iostream>
#include <stdexcept>
int main(){
 using P=PrismRepairDamping;int checks=0;
 auto require=[&](bool b){++checks;if(!b)throw std::runtime_error("repair damping gate failed at check "+std::to_string(checks));};
 for(int mode=1;mode<=3;++mode)for(double rho:{.1,.25,.5,.75,.9,2.}){
  auto d=P::Decide(100,100-8*rho,-10,4,mode);
  require(d.valid);require(std::abs(d.rho-rho)<1e-14);
  double expected=mode>=2&&rho>.75?.5:(mode==3&&rho<.25?2:1);require(d.factor==expected);
  for(double scale:{.001,1.,1000.}){auto q=P::Decide(100*scale,(100-8*rho)*scale,-10*scale,4*scale,mode);require(q.valid&&q.factor==expected);}
 }
 double inf=std::numeric_limits<double>::infinity(),nan=std::numeric_limits<double>::quiet_NaN();
 for(auto d:{P::Decide(100,101,-10,4,3),P::Decide(100,99,1,0,3),P::Decide(100,99,-1,3,3),P::Decide(100,99,-1,-1,3),P::Decide(inf,99,-1,0,3),P::Decide(100,99,nan,0,3),P::Decide(100,99,-1e-20,0,3)})require(!d.valid && d.factor==1);
 // A high local rho cannot establish safety of a longer step.
 double h=1e-6,M=1000,r=1-h+M*h*h,actual=.5-.5*r*r,pred=h-.5*h*h;
 require(actual/pred>.99);require(.5*std::pow(1-1+M,2)>.5);
 std::cout<<"PASS "<<checks<<" host checks; tiny-step rho="<<actual/pred<<", full-step cost="<<.5*M*M<<"\n";
}
