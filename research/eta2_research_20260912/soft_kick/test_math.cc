#include "mode_math.h"
#include <random>
#include <iostream>
#include <iomanip>
#include <cassert>
int main(){
 std::mt19937_64 gen(2026091211);std::normal_distribution<double> normal;
 const int nc=24,n=9*nc;std::vector<double> R(9*nc),t(3*nc),E(n),factors(81*nc);
 Eigen::MatrixXd M=Eigen::MatrixXd::Zero(n,n);Eigen::MatrixXd G=Eigen::MatrixXd::Zero(n,7);
 std::vector<Eigen::Vector3d> centers;Eigen::Vector3d center=Eigen::Vector3d::Zero();
 for(int i=0;i<nc;++i){Eigen::Vector3d c(normal(gen),normal(gen),normal(gen));centers.push_back(c);center+=c;}center/=nc;
 for(int i=0;i<nc;++i){
  Eigen::Vector3d a(normal(gen),normal(gen),normal(gen));Eigen::Matrix3d Ri=Eigen::AngleAxisd(a.norm(),a.normalized()).toRotationMatrix();
  Eigen::Map<prism_coarse::Mat3>(R.data()+9*i)=Ri;Eigen::Map<Eigen::Vector3d>(t.data()+3*i)=-Ri*centers[i];
  Eigen::Matrix<double,9,9> L=Eigen::Matrix<double,9,9>::Zero();for(int j=0;j<9;++j){E[9*i+j]=std::exp(.3*normal(gen));for(int k=0;k<=j;++k)L(j,k)=j==k?std::exp(.2*normal(gen)):.1*normal(gen);}
  M.block<9,9>(9*i,9*i)=L*L.transpose();for(int j=0;j<9;++j)for(int k=0;k<9;++k)factors[81*i+9*j+k]=k<=j?L(j,k):1000+normal(gen); // upper triangle must be ignored
  for(int j=0;j<3;++j){Eigen::Vector3d e=Eigen::Vector3d::Unit(j);G.block<3,1>(9*i,j)=-Ri*e;G.block<3,1>(9*i+3,j)=Ri*e.cross(center);G.block<3,1>(9*i+3,3+j)=-Ri*e;}
  G.block<3,1>(9*i+3,6)=-Ri*(centers[i]-center);for(int j=0;j<9;++j)G.row(9*i+j)/=E[9*i+j];
 }
 prism_coarse::Geometry geo(nc);geo.Build(R,t,E);int r=geo.rank;Eigen::MatrixXd Z=Eigen::MatrixXd::Zero(n,r);
 for(int i=0;i<nc;++i){int k=geo.label[i];for(int j=0;j<9;++j)for(int a=0;a<geo.local_rank[k];++a)Z(9*i+j,geo.offset[k]+a)=geo.Z[(9*i+j)*7+a];}
 Eigen::MatrixXd Q=Eigen::MatrixXd::NullaryExpr(n,n,[&](){return normal(gen);});Eigen::MatrixXd A=Q.transpose()*Q+.3*Eigen::MatrixXd::Identity(n,n),Ac=Z.transpose()*A*Z;
 std::cerr<<"independent global projector error "<<(G-Z*(Z.transpose()*G)).norm()/G.norm()<<" Zerr "<<(Z.transpose()*Z-Eigen::MatrixXd::Identity(r,r)).norm()<<"\n"; auto mode=prism_soft::SelectMode(geo,Ac,R,t,E,factors);if(!mode.usable)std::cerr<<"mode failure "<<mode.reason<<" rep="<<mode.gauge_representation<<" rank="<<mode.rank<<" gauge="<<mode.gauge_rank<<"\n";assert(mode.usable);
 Eigen::MatrixXd constraint=G.transpose()*M*Z;Eigen::JacobiSVD<Eigen::MatrixXd> svd(constraint,Eigen::ComputeFullV);Eigen::MatrixXd N=svd.matrixV().rightCols(r-7),Mc=Z.transpose()*M*Z;
 Eigen::GeneralizedSelfAdjointEigenSolver<Eigen::MatrixXd> ref(N.transpose()*Ac*N,N.transpose()*Mc*N);
 double eigerr=std::abs(mode.eigenvalue-ref.eigenvalues()[0])/std::abs(ref.eigenvalues()[0]);assert(eigerr<1e-10);
 Eigen::VectorXd z=Z*mode.coefficients;double gauge=(G.transpose()*M*z).norm()/(G.norm()*M.norm()*z.norm());assert(gauge<1e-10);
 double norm=std::sqrt(z.dot(M*z));assert(std::abs(norm-1)<1e-10);
 // Replacing actual M by identity gives a different Ritz result.
 Eigen::GeneralizedSelfAdjointEigenSolver<Eigen::MatrixXd> wrong(N.transpose()*Ac*N,N.transpose()*N);
 double metric_effect=std::abs(mode.eigenvalue-wrong.eigenvalues()[0])/mode.eigenvalue;assert(metric_effect>1e-3);
 auto negative=prism_soft::SelectMode(geo,-Ac,R,t,E,factors);assert(!negative.usable&&negative.reason=="no_positive_mode");
 auto badf=factors;badf[0]=-1;auto badmetric=prism_soft::SelectMode(geo,Ac,R,t,E,badf);assert(!badmetric.usable&&badmetric.reason=="metric_factor");
 double energy_error=0;
 for(int i=0;i<1000;++i){double a=i%7==0?0:std::exp(8*normal(gen)),b=std::exp(8*normal(gen)),budget=std::exp(8*normal(gen));double alpha=prism_soft::Amplitude(a,b,budget);double err=std::abs(a*alpha+.5*b*alpha*alpha-budget)/budget;energy_error=std::max(energy_error,err);assert(err<1e-12);}
 assert(!std::isfinite(prism_soft::Amplitude(0,0,1)));assert(!std::isfinite(prism_soft::Amplitude(-1,1,1)));
 Eigen::MatrixXd W=Eigen::MatrixXd::NullaryExpr(12,3,[&](){return normal(gen);}),V=Eigen::MatrixXd::Identity(3,3)+W.transpose()*W;
 Eigen::VectorXd dc=Eigen::VectorXd::NullaryExpr(12,[&](){return normal(gen);}),dp=-V.ldlt().solve(W.transpose()*dc);
 double pointres=(V*dp+W.transpose()*dc).norm()/std::max((W.transpose()*dc).norm(),1e-300);assert(pointres<1e-12);
 std::cout<<std::setprecision(17)<<"{\"passed\":true,\"negative_spectrum_skipped\":true,\"invalid_metric_skipped\":true,\"rank\":"<<r<<",\"gauge_rank\":"<<mode.gauge_rank<<",\"ritz_relative_error\":"<<eigerr<<",\"gauge_leakage\":"<<gauge<<",\"metric_norm\":"<<norm<<",\"wrong_metric_relative_difference\":"<<metric_effect<<",\"max_energy_error\":"<<energy_error<<",\"homogeneous_point_residual\":"<<pointres<<"}\n";
}
