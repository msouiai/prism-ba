#pragma once
#include <Eigen/Eigenvalues>
#include <stdexcept>
// min .5 y'H y - b'y subject to ||y||<=radius, including the hard case.
struct PrismProjectedRadius {
 Eigen::MatrixXd H,U; Eigen::VectorXd d,b,a;
 struct Result { Eigen::VectorXd y; double lambda; };
 PrismProjectedRadius(const Eigen::MatrixXd& h,const Eigen::VectorXd& rhs):H(h),b(rhs){
  Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> es(H);
  if(es.info()!=Eigen::Success)throw std::runtime_error("TR eigensolve failed");
  U=es.eigenvectors();d=es.eigenvalues();a=U.transpose()*b;
 }
 Result Solve(double radius) const {
  if(!(radius>0))throw std::runtime_error("Invalid TR radius");
  const double floor=std::max(0.,-d[0]);
  const double tol=1e-13*std::max(1.,d.cwiseAbs().maxCoeff());
  Eigen::VectorXd z=Eigen::VectorXd::Zero(d.size()); bool singular_rhs=false;
  for(int i=0;i<d.size();++i){
   if(d[i]+floor<=tol){if(std::abs(a[i])>1e-13*std::max(1.,b.norm()))singular_rhs=true;}
   else z[i]=a[i]/(d[i]+floor);
  }
  if(!singular_rhs && z.norm()<=radius){
   if(floor>0)z[0]+=std::sqrt(std::max(0.,radius*radius-z.squaredNorm()));
   return {U*z,floor};
  }
  auto vector_at=[&](double l){return (a.array()/(d.array()+l)).matrix().eval();};
  double lo=floor,hi=floor+std::max(1.,b.norm()/radius);
  while(vector_at(hi).norm()>radius)hi=floor+2*(hi-floor);
  for(int j=0;j<100;++j){double mid=lo+.5*(hi-lo);if(mid==lo||mid==hi)break;
   if(vector_at(mid).norm()>radius)lo=mid;else hi=mid;}
  return {U*vector_at(hi),hi};
 }
};
