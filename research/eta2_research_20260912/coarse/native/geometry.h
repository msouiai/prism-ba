#pragma once
#include <Eigen/Dense>
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <vector>

namespace prism_coarse {
using Mat3 = Eigen::Matrix<double,3,3,Eigen::RowMajor>;
using Vec3 = Eigen::Vector3d;
struct Geometry {
  int nc, K, rank=0;
  std::vector<int> label, count, offset, local_rank, members, member_offsets;
  std::vector<double> Z;
  bool clustered=false;
  int lloyd_iterations=0, empty_repairs=0;
  explicit Geometry(int n):nc(n),K(std::min(8,n)),label(n,-1) {
    if(n<1)throw std::runtime_error("coarse: empty camera set");
  }
  std::vector<Vec3> Centers(const std::vector<double>& R,const std::vector<double>& t) const {
    std::vector<Vec3> C(nc);
    for(int i=0;i<nc;++i){
      Eigen::Map<const Mat3> r(R.data()+9*i);
      Eigen::Map<const Vec3> v(t.data()+3*i);
      C[i]=-r.transpose()*v;
      if(!C[i].allFinite())throw std::runtime_error("coarse: nonfinite camera center");
    }
    return C;
  }
  void Cluster(const std::vector<Vec3>& input){
    std::vector<Vec3> C=input;Vec3 origin=Vec3::Zero();for(const auto& c:C)origin+=c;origin/=nc;
    for(auto& c:C)c-=origin;
    if(K==nc){for(int i=0;i<nc;++i)label[i]=i;}
    else {
      std::vector<Vec3> seed;std::vector<double> distance(nc);
      int first=0;for(int i=0;i<nc;++i){distance[i]=C[i].squaredNorm();if(distance[i]>distance[first])first=i;}
      seed.push_back(C[first]);
      std::vector<bool> chosen(nc,false);chosen[first]=true;
      for(int i=0;i<nc;++i)distance[i]=(C[i]-C[first]).squaredNorm();
      while((int)seed.size()<K){
        int best=-1;for(int i=0;i<nc;++i)if(!chosen[i]&&(best<0||distance[i]>distance[best]))best=i;
        chosen[best]=true;seed.push_back(C[best]);
        for(int i=0;i<nc;++i)distance[i]=std::min(distance[i],(C[i]-C[best]).squaredNorm());
      }
      for(int it=0;it<100;++it){
        std::vector<int> next(nc),counts(K,0);
        for(int i=0;i<nc;++i){
          int best=0;double d=(C[i]-seed[0]).squaredNorm();
          for(int k=1;k<K;++k){double q=(C[i]-seed[k]).squaredNorm();if(q<d){d=q;best=k;}}
          next[i]=best;distance[i]=d;++counts[best];
        }
        for(int k=0;k<K;++k)if(!counts[k]){
          int best=-1;for(int i=0;i<nc;++i)if(counts[next[i]]>1&&(best<0||distance[i]>distance[best]))best=i;
          if(best<0)throw std::runtime_error("coarse: empty-cluster repair failed");
          --counts[next[best]];next[best]=k;++counts[k];distance[best]=0;++empty_repairs;
        }
        bool same=next==label;label=next;lloyd_iterations=it+1;
        std::fill(seed.begin(),seed.end(),Vec3::Zero());
        for(int i=0;i<nc;++i)seed[label[i]]+=C[i];
        for(int k=0;k<K;++k)seed[k]/=counts[k];
        if(same)break;
      }
    }
    count.assign(K,0);for(int k:label)++count[k];
    member_offsets.assign(K+1,0);for(int k=0;k<K;++k)member_offsets[k+1]=member_offsets[k]+count[k];
    members.resize(nc);auto cursor=member_offsets;
    for(int i=0;i<nc;++i)members[cursor[label[i]]++]=i;
    clustered=true;
  }
  void Build(const std::vector<double>& R,const std::vector<double>& t,const std::vector<double>& E){
    if(R.size()!=9ul*nc||t.size()!=3ul*nc||E.size()!=9ul*nc)throw std::runtime_error("coarse: geometry sizes");
    auto C=Centers(R,t);if(!clustered)Cluster(C);
    local_rank.assign(K,0);offset.assign(K+1,0);Z.assign(63ul*nc,0);
    for(int k=0;k<K;++k){
      Vec3 center=Vec3::Zero();for(int q=member_offsets[k];q<member_offsets[k+1];++q)center+=C[members[q]];center/=count[k];
      Eigen::MatrixXd raw=Eigen::MatrixXd::Zero(9*count[k],7);
      for(int q=0;q<count[k];++q){
        int i=members[member_offsets[k]+q];Eigen::Map<const Mat3> r(R.data()+9*i);
        for(int a=0;a<3;++a){
          Vec3 unit=Vec3::Unit(a);
          raw.block<3,1>(9*q,a)=-r*unit;
          raw.block<3,1>(9*q+3,a)=r*(unit.cross(center));
          raw.block<3,1>(9*q+3,3+a)=-r*unit;
        }
        raw.block<3,1>(9*q+3,6)=-r*(C[i]-center);
        for(int j=0;j<9;++j){if(!(E[9*i+j]>0&&std::isfinite(E[9*i+j])))throw std::runtime_error("coarse: scaling");raw.row(9*q+j)/=E[9*i+j];}
      }
      for(int a=0;a<7;++a){double norm=raw.col(a).norm();if(norm>0)raw.col(a)/=norm;}
      Eigen::JacobiSVD<Eigen::MatrixXd> svd(raw,Eigen::ComputeThinU);
      auto s=svd.singularValues();int r=0;while(r<(int)s.size()&&s[r]>1e-10*s[0])++r;
      if(!svd.matrixU().allFinite()||!s.allFinite())throw std::runtime_error("coarse: SVD nonfinite");
      local_rank[k]=r;offset[k+1]=offset[k]+r;
      for(int q=0;q<count[k];++q){int i=members[member_offsets[k]+q];for(int j=0;j<9;++j)for(int a=0;a<r;++a)Z[(9ul*i+j)*7+a]=svd.matrixU()(9*q+j,a);}
    }
    rank=offset[K];
    if(rank<1)throw std::runtime_error("coarse: zero rank");
  }
};
} // namespace prism_coarse
