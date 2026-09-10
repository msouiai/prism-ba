#include "projected_radius.h"
#include <iostream>
void check(Eigen::MatrixXd h,Eigen::VectorXd b,double r){
 PrismProjectedRadius p(h,b);auto s=p.Solve(r);
 double scale=std::max(1.,b.norm()+h.norm()*s.y.norm());
 if(s.y.norm()>r*(1+1e-10)||(h*s.y+s.lambda*s.y-b).norm()>1e-9*scale||
    s.lambda<0||p.d[0]+s.lambda < -1e-10||
    std::abs(s.lambda*(s.y.norm()-r))>1e-9*scale*std::max(1.,r))
  throw std::runtime_error("KKT failure");
}
int main(){
 Eigen::MatrixXd h=Eigen::MatrixXd::Zero(3,3);h.diagonal()<<-2,1,3;
 Eigen::VectorXd b(3);b<<0,1,0;check(h,b,2); // indefinite hard case
 b<<1,1,1;check(h,b,.1);check(h,b,100);
 h.diagonal()<<0,1,3;b.setZero();check(h,b,1);
 for(int i=0;i<100;++i){Eigen::MatrixXd a=Eigen::MatrixXd::Random(8,8);h=a.transpose()*a; b=Eigen::VectorXd::Random(8);for(double r:{.01,1.,100.})check(h,b,r);}
 std::cout<<"304 projected TR KKT checks passed\n";
}
