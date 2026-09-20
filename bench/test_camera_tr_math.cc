#include "camera_tr_math.h"
#include <Eigen/Dense>
#include <random>
#include <iostream>
#include <stdexcept>
int main(){
 std::mt19937 rng(1701);std::normal_distribution<double> normal;double maxerr=0;
 for(int c=0;c<100;++c){
  Eigen::MatrixXd A(9,9);Eigen::VectorXd b(9);
  for(int i=0;i<9;++i){b[i]=normal(rng);for(int j=0;j<9;++j)A(i,j)=normal(rng);}
  Eigen::MatrixXd S=A.transpose()*A+.01*Eigen::MatrixXd::Identity(9,9);
  double previous=1e100,delta=.1+c*.013;
  for(double shift:{.001,.01,.1,1.,10.}){
   Eigen::VectorXd x=(S+shift*Eigen::MatrixXd::Identity(9,9)).ldlt().solve(b);
   if(x.norm()>previous*(1+1e-10))throw std::runtime_error("shift norm monotonicity");previous=x.norm();
   double a=prism_camera_tr::scale(x.norm(),delta);Eigen::VectorXd z=a*x;
   if(z.norm()>delta*(1+1e-12))throw std::runtime_error("radius violated");
   double actual=b.dot(z)-.5*z.dot(S*z);
   double pred=prism_camera_tr::prediction(b.dot(x),x.dot(S*x),a);
   double err=std::abs(pred-actual)/std::max(1.,std::abs(actual));maxerr=std::max(maxerr,err);
   if(err>1e-11)throw std::runtime_error("scaled prediction mismatch");
  }
 }
 if(prism_camera_tr::accept(1,-1,.5,1)||prism_camera_tr::accept(1,1,2,1)||
    prism_camera_tr::accept(.01,1,.5,1)||!prism_camera_tr::accept(.5,1,.5,1))throw std::runtime_error("acceptance rule");
 if(prism_camera_tr::radius_after(1,.9,.9)!=2||prism_camera_tr::radius_after(1,.5,.9)!=1||
    prism_camera_tr::radius_after(1,.5,.1)!=.25)throw std::runtime_error("radius update");
 std::cout<<"PASS 500 SPD shifted/clipped candidates, prediction maxerr="<<maxerr<<"; acceptance and radius guards\n";
}
