#pragma once
#include "clusters.h"
#include <limits>
namespace prism_passenger {
using Mat3=prism_coarse::Mat3;
using Vec3=Eigen::Vector3d;
struct Geometry {
  int nc,np,no,K,rank=0;
  prism_coarse::Geometry cluster;
  std::vector<int> point_label,offset,local_rank;
  std::vector<double> mu,T,singular;
  double whitening_error=0;
  Geometry(int c,int p,int o):nc(c),np(p),no(o),K(std::min(8,c)),cluster(c){}
  void Build(const std::vector<double>& R,const std::vector<double>& t,const std::vector<double>& X,
      const std::vector<double>& E,const std::vector<double>& Cdiag,const std::vector<int>& ci,
      const std::vector<int>& pi,double lambda,double tau){
    auto C=cluster.Centers(R,t);cluster.Cluster(C);
    point_label.assign(np,-1);for(int o=0;o<no;++o)if(point_label[pi[o]]<0)point_label[pi[o]]=cluster.label[ci[o]];
    std::vector<std::vector<int>> points(K);for(int j=0;j<np;++j)if(point_label[j]>=0)points[point_label[j]].push_back(j);
    offset.assign(K+1,0);local_rank.assign(K,0);mu.assign(3*K,0);T.assign(49*K,0);singular.assign(7*K,0);
    if(!(lambda>0&&tau>0))throw std::runtime_error("passenger: nonpositive damping");
    for(int k=0;k<K;++k){
      Vec3 center=Vec3::Zero();for(int a=cluster.member_offsets[k];a<cluster.member_offsets[k+1];++a)center+=C[cluster.members[a]];
      center/=cluster.count[k];Eigen::Map<Vec3>(mu.data()+3*k)=center;
      const int nr=9*cluster.count[k]+3*points[k].size();Eigen::MatrixXd raw=Eigen::MatrixXd::Zero(nr,7);
      for(int a=0;a<cluster.count[k];++a){int i=cluster.members[cluster.member_offsets[k]+a];Eigen::Map<const Mat3> r(R.data()+9*i);
        for(int m=0;m<3;++m){Vec3 u=Vec3::Unit(m);raw.block<3,1>(9*a,m)=-r*u;raw.block<3,1>(9*a+3,m)=r*u.cross(center);raw.block<3,1>(9*a+3,m+3)=-r*u;}
        raw.block<3,1>(9*a+3,6)=-r*(C[i]-center);
        for(int d=0;d<9;++d){if(!(E[9*i+d]>0&&std::isfinite(E[9*i+d])))throw std::runtime_error("passenger: invalid E");raw.row(9*a+d)/=E[9*i+d];}
      }
      for(size_t a=0;a<points[k].size();++a){int j=points[k][a];int row=9*cluster.count[k]+3*a;Vec3 v=Eigen::Map<const Vec3>(X.data()+3*j)-center;
        for(int m=0;m<3;++m){raw.block<3,1>(row,m)=Vec3::Unit(m).cross(v);raw(row+m,m+3)=1;}raw.block<3,1>(row,6)=v;
        double floor=tau*(Cdiag[3*j]+Cdiag[3*j+1]+Cdiag[3*j+2])/3.;if(!(floor>0))floor=1e-32;
        for(int d=0;d<3;++d){double D=std::max(tau*Cdiag[3*j+d],.001*floor)/lambda;if(!(D>0&&std::isfinite(D)))throw std::runtime_error("passenger: invalid point metric");raw.row(row+d)*=std::sqrt(D);}
      }
      Eigen::Matrix<double,7,1> norm;for(int m=0;m<7;++m){norm[m]=raw.col(m).norm();if(norm[m]>0)raw.col(m)/=norm[m];}
      Eigen::HouseholderQR<Eigen::MatrixXd> qr(raw);Eigen::Matrix<double,7,7> r=qr.matrixQR().topLeftCorner(7,7).template triangularView<Eigen::Upper>();
      Eigen::JacobiSVD<Eigen::Matrix<double,7,7>> svd(r,Eigen::ComputeFullV);auto s=svd.singularValues();int n=0;while(n<7&&s[n]>1e-10*s[0])++n;
      if(!s.allFinite()||n<1)throw std::runtime_error("passenger: metric rank failure");local_rank[k]=n;offset[k+1]=offset[k]+n;
      Eigen::MatrixXd normalized=svd.matrixV().leftCols(n);for(int m=0;m<n;++m)normalized.col(m)/=s[m];
      Eigen::MatrixXd white=raw*normalized;whitening_error=std::max(whitening_error,(white.transpose()*white-Eigen::MatrixXd::Identity(n,n)).norm());
      for(int m=0;m<7;++m){singular[7*k+m]=s[m];for(int a=0;a<n;++a)T[49*k+7*m+a]=norm[m]>0?normalized(m,a)/norm[m]:0;}
    }
    rank=offset[K];if(!(whitening_error<=1e-6))throw std::runtime_error("passenger: metric whitening tolerance");
  }
  std::vector<double> Parameters(const Eigen::VectorXd& y,double alpha)const{
    std::vector<double> q(7*K,0);for(int k=0;k<K;++k)for(int m=0;m<7;++m)for(int a=0;a<local_rank[k];++a)q[7*k+m]+=alpha*T[49*k+7*m+a]*y[offset[k]+a];return q;
  }
  std::vector<double> Action(const std::vector<double>& q)const{
    std::vector<double> a(13*K,0);for(int k=0;k<K;++k){Vec3 w=Eigen::Map<const Vec3>(q.data()+7*k);double angle=w.norm();
      Mat3 Q=Mat3::Identity();if(angle>0)Q=Eigen::AngleAxisd(angle,w/angle).toRotationMatrix();
      for(int m=0;m<9;++m)a[13*k+m]=Q.data()[m];for(int m=0;m<3;++m)a[13*k+9+m]=q[7*k+3+m];a[13*k+12]=std::expm1(q[7*k+6]);}
    return a;
  }
};
} // namespace prism_passenger
