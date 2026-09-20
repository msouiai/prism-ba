#include "rl_curvature.h"
#include <cassert>
#include <iostream>

int main(){
  unsetenv("OCA_RLD_EPISODE");unsetenv("OCA_RLD_POLICY");unsetenv("OCA_RLC_POLICY");
  // PCG's recurrence must recover the spectrum of M^-1/2 A M^-1/2,
  // rather than A. The complete eight-dimensional solve excites every mode.
  constexpr int n=8;Eigen::MatrixXd X(n,n);
  for(int i=0;i<n;++i)for(int j=0;j<n;++j)X(i,j)=std::sin(1.+i*3.+j*7.+i*j*.7);
  Eigen::MatrixXd A=X.transpose()*X+Eigen::MatrixXd::Identity(n,n)*2;
  Eigen::VectorXd metric(n),r(n);
  for(int i=0;i<n;++i){metric[i]=1.+i*.7;r[i]=1.+std::cos(i*2.);}
  Eigen::VectorXd z=r.cwiseQuotient(metric),p=z;double rz=r.dot(z);
  PrismCurvatureDamping c;c.ResetCG();
  for(int k=0;k<n;++k){
    Eigen::VectorXd Ap=A*p;double alpha=rz/p.dot(Ap),rayleigh=p.dot(Ap)/p.squaredNorm();
    r-=alpha*Ap;z=r.cwiseQuotient(metric);double next=r.dot(z),beta=next/rz;
    c.ObserveCG(alpha,beta,rayleigh);p=z+beta*p;rz=next;
  }
  c.ObserveModel(-6,2);c.Summarize();assert(c.model_valid&&c.quad_alpha==3&&c.spectrum_valid);
  Eigen::MatrixXd inv=metric.cwiseSqrt().cwiseInverse().asDiagonal();
  Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> exact(inv*A*inv);
  assert(std::abs(c.theta_min-exact.eigenvalues()[0])<1e-7);
  assert(std::abs(c.theta_max-exact.eigenvalues()[n-1])<1e-7);
  // One step is not a trustworthy spectral summary, and retry reset discards
  // all previous recurrence entries. Invalid recurrences must abstain.
  c.ResetCG();c.ObserveCG(1,.2,1);c.Summarize();assert(c.depth==1&&!c.spectrum_valid);
  c.ResetCG();c.ObserveCG(-1,1,1);c.Summarize();assert(!c.spectrum_valid);
  c.ObserveModel(1,2);c.Summarize();assert(!c.model_valid);
  c.controller=true;c.use_curvature=true;c.mode=3;c.history_count=2;c.history[0]=-3;
  c.history[2]=1;c.history[3]=-2;c.history[7]=.1;
  c.model_valid=true;c.quad_alpha=3;c.previous_quad_alpha=2;
  assert(c.Action(1)==-1);assert(c.Action(2)==0);assert(c.Action(3)==-1);assert(c.Action(5)==0);
  PrismCurvatureDamping failed;failed.controller=true;failed.mode=3;failed.Begin(0,0,0,100);
  failed.End(1,false,.1,.1,1e-16,1,1,0,1,1,.5,1,128,2,1,0,100,1,1,1);
  assert(failed.fallback&&!failed.previous_accepted);
  // Curvature may veto a blind CG-cap increase when the current step is
  // already short relative to its directional quadratic minimizer.
  c.actions=0;c.last_action=-1000000;c.history[7]=1;c.history[2]=.5;
  c.spectrum_valid=true;c.condition=200;c.quad_alpha=3;
  assert(c.Action(7)==0);c.quad_alpha=1;assert(c.Action(7)==1);
  std::cout<<"PASS: PCG Ritz spectrum, directional model, reset, masks, controller safeguards\n";
}
