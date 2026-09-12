#pragma once
#include "../coarse/native/geometry.h"
#include <limits>
#include <string>

namespace prism_soft {
struct Mode {
 bool usable=false;std::string reason="uninitialized";int rank=0,gauge_rank=0,negative=0;
 double eigenvalue=0,gauge_representation=0,gauge_leakage=0,ritz_residual=0,metric_norm=0;
 Eigen::VectorXd coefficients,eigenvalues;
};
inline Mode SelectMode(const prism_coarse::Geometry& geo,const Eigen::MatrixXd& Ac,
 const std::vector<double>& R,const std::vector<double>& t,const std::vector<double>& E,
 const std::vector<double>& factors){
 Mode out;out.rank=geo.rank;const int r=geo.rank,nc=geo.nc;
 if(r<=7||Ac.rows()!=r||Ac.cols()!=r||!Ac.allFinite()){out.reason="matrix_or_rank";return out;}
 const double sym=(Ac-Ac.transpose()).norm()/std::max(Ac.norm(),1e-300);
 if(!std::isfinite(sym)||sym>1e-7){out.reason="asymmetry";return out;}
 Eigen::MatrixXd Mc=Eigen::MatrixXd::Zero(r,r),Cg=Eigen::MatrixXd::Zero(r,7);
 Eigen::MatrixXd Gfull=Eigen::MatrixXd::Zero(9*nc,7);
 Eigen::Matrix<double,1,7> gnorm=Eigen::Matrix<double,1,7>::Zero(),err=gnorm;
 auto C=geo.Centers(R,t);Eigen::Vector3d center=Eigen::Vector3d::Zero();for(auto c:C)center+=c;center/=nc;
 for(int i=0;i<nc;++i){
  int k=geo.label[i],rk=geo.local_rank[k],o=geo.offset[k];Eigen::MatrixXd Zi(9,rk);
  for(int j=0;j<9;++j)for(int a=0;a<rk;++a)Zi(j,a)=geo.Z[(9ul*i+j)*7+a];
  Eigen::Matrix<double,9,9> L=Eigen::Matrix<double,9,9>::Zero();
  for(int j=0;j<9;++j)for(int a=0;a<=j;++a)L(j,a)=factors[81ul*i+9*j+a];
  if(!L.allFinite()||(L.diagonal().array()<=0).any()){out.reason="metric_factor";return out;}
  Eigen::MatrixXd LiZ=L.transpose()*Zi;Mc.block(o,o,rk,rk)+=LiZ.transpose()*LiZ;
  Eigen::Map<const prism_coarse::Mat3> Ri(R.data()+9*i);
  Eigen::Matrix<double,9,7> G=Eigen::Matrix<double,9,7>::Zero();
  for(int a=0;a<3;++a){Eigen::Vector3d e=Eigen::Vector3d::Unit(a);
   G.block<3,1>(0,a)=-Ri*e;G.block<3,1>(3,a)=Ri*(e.cross(center));G.block<3,1>(3,3+a)=-Ri*e;}
  G.block<3,1>(3,6)=-Ri*(C[i]-center);
  for(int j=0;j<9;++j)G.row(j)/=E[9*i+j];
  auto local=Zi.transpose()*G;Cg.block(o,0,rk,7)+=local;
  gnorm+=G.array().square().colwise().sum().matrix();
  Gfull.block<9,7>(9*i,0)=G;
 }
 // Z is orthonormal across a whole cluster, not within each camera block.
 for(int i=0;i<nc;++i){int k=geo.label[i],rk=geo.local_rank[k],o=geo.offset[k];Eigen::MatrixXd Zi(9,rk);
  for(int j=0;j<9;++j)for(int a=0;a<rk;++a)Zi(j,a)=geo.Z[(9ul*i+j)*7+a];
  Eigen::MatrixXd missing=Gfull.block<9,7>(9*i,0)-Zi*Cg.block(o,0,rk,7);err+=missing.array().square().colwise().sum().matrix();}
 for(int j=0;j<7;++j)out.gauge_representation=std::max(out.gauge_representation,std::sqrt(err[j]/std::max(gnorm[j],1e-300)));
 if(!Mc.allFinite()||out.gauge_representation>1e-8){out.reason="gauge_representation";return out;}
 Eigen::LLT<Eigen::MatrixXd> chol(Mc);if(chol.info()!=Eigen::Success){out.reason="metric_not_spd";return out;}
 Eigen::MatrixXd L=chol.matrixL(),inv=L.triangularView<Eigen::Lower>().solve(Eigen::MatrixXd::Identity(r,r));
 Eigen::MatrixXd G=L.transpose()*Cg;for(int j=0;j<7;++j){double n=G.col(j).norm();if(!(n>0&&std::isfinite(n))){out.reason="zero_gauge";return out;}G.col(j)/=n;}
 Eigen::JacobiSVD<Eigen::MatrixXd> svd(G,Eigen::ComputeFullU);auto singular=svd.singularValues();
 for(int j=0;j<singular.size();++j)if(singular[j]>1e-10*singular[0])++out.gauge_rank;
 if(out.gauge_rank!=7){out.reason="gauge_rank";return out;}
 Eigen::MatrixXd N=svd.matrixU().rightCols(r-7),S=inv*(.5*(Ac+Ac.transpose()))*inv.transpose();
 Eigen::MatrixXd T=N.transpose()*S*N;T=.5*(T+T.transpose()).eval();
 Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> eig(T);
 if(eig.info()!=Eigen::Success||!eig.eigenvalues().allFinite()){out.reason="eigen_failure";return out;}
 out.eigenvalues=eig.eigenvalues();int chosen=-1;
 for(int j=0;j<out.eigenvalues.size();++j){double v=out.eigenvalues[j];if(v<0)++out.negative;if(chosen<0&&v>0)chosen=j;}
 if(chosen<0){out.reason="no_positive_mode";return out;}
 out.eigenvalue=out.eigenvalues[chosen];Eigen::VectorXd v=eig.eigenvectors().col(chosen),y=N*v;
 out.ritz_residual=(T*v-out.eigenvalue*v).norm()/std::max(T.norm(),1e-300);
 out.gauge_leakage=(G.transpose()*y).norm()/std::max(G.norm()*y.norm(),1e-300);
 out.coefficients=inv.transpose()*y;out.metric_norm=std::sqrt(out.coefficients.dot(Mc*out.coefficients));
 if(!out.coefficients.allFinite()||out.ritz_residual>1e-8||out.gauge_leakage>1e-8){out.reason="eigen_certificate";return out;}
 out.usable=true;out.reason="ok";return out;
}
inline double Amplitude(double slope,double curvature,double budget){
 if(!(slope>=0&&curvature>0&&budget>0&&std::isfinite(slope)&&std::isfinite(curvature)&&std::isfinite(budget)))return std::numeric_limits<double>::quiet_NaN();
 return 2*budget/(slope+std::hypot(slope,std::sqrt(2*curvature*budget)));
}
} // namespace prism_soft
