#include "projected_radius.h"
#include <iostream>
int main(){
 double worst=0;
 for(int i=0;i<1000;++i){
  Eigen::VectorXd jc=Eigen::VectorXd::Random(12),jp=Eigen::VectorXd::Random(12),r=Eigen::VectorXd::Random(12);
  if(i%10==0)jp=-jc; // singular cancellation direction
  double sc=jc.norm(),sp=jp.norm();Eigen::MatrixXd H(2,2);H<<1,jc.dot(jp)/(sc*sp),jc.dot(jp)/(sc*sp),1;
  Eigen::VectorXd rhs(2);rhs<<-jc.dot(r)/sc,-jp.dot(r)/sp;
  PrismProjectedRadius model(H,rhs);
  for(double f:{.5,1.,2.}){
   double R=f*std::hypot(sc,sp);auto solution=model.Solve(R);auto y=solution.y;
   auto jd=(jc*(y[0]/sc)+jp*(y[1]/sp)).eval();double pred=-r.dot(jd)-.5*jd.squaredNorm();
   double error=std::abs(pred-(rhs.dot(y)-.5*y.dot(H*y)));worst=std::max(worst,error);
   if(error>1e-9||y.norm()>R*(1+1e-10)||(H*y+solution.lambda*y-rhs).norm()>1e-9)
    throw std::runtime_error("joint TR projection validation failed");
  }
 }
 std::cout<<"3000 joint TR projection/metric/KKT checks passed; max prediction error "<<worst<<"\n";
}
