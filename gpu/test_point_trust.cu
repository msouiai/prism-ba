#define OCA_CORE_LIBRARY
#include "oca_cuda.cu"
#include <Eigen/Dense>
#include <random>
int main(){
 const int n=259;std::vector<double> r(6*n),cd(3*n),x(3*n);std::mt19937 rng(77);std::normal_distribution<double> rand;
 std::vector<Eigen::Matrix3d> v(n);std::vector<Eigen::Vector3d> d(n),xx(n);
 for(int p=0;p<n;++p){Eigen::Matrix3d R=Eigen::Matrix3d::Zero();
  for(int i=0;i<3;++i)for(int j=i;j<3;++j)R(i,j)=(i==j?std::abs(rand(rng))+.1:rand(rng))*std::pow(10.,j-1);
  if(p%7==0)R.row(2).setZero();if(p%11==0)R.row(1).setZero();if(p%31==0)R.setZero();
  v[p]=R.transpose()*R;r[6*p]=R(0,0);r[6*p+1]=R(0,1);r[6*p+2]=R(0,2);r[6*p+3]=R(1,1);r[6*p+4]=R(1,2);r[6*p+5]=R(2,2);
  for(int i=0;i<3;++i){cd[3*p+i]=v[p](i,i);d[p][i]=std::max(v[p](i,i),1e-3*v[p].trace()/3);x[3*p+i]=xx[p][i]=rand(rng);}
 }
 double *dr,*dd,*dx;
 auto up=[](auto& a,double** p){CUDA_CHECK(cudaMalloc(p,a.size()*sizeof(double)));CUDA_CHECK(cudaMemcpy(*p,a.data(),a.size()*sizeof(double),cudaMemcpyHostToDevice));};up(r,&dr);up(cd,&dd);up(x,&dx);
 auto require=[](bool ok){if(!ok)throw std::runtime_error("point trust test failed");};
 double norm=0,curv=0;for(int p=0;p<n;++p){norm+=xx[p].dot(d[p].asDiagonal()*xx[p]);curv+=xx[p].dot(v[p]*xx[p]);}
 auto cpu_ratio=[&](double old,double trial){double sum=0;
  for(int p=0;p<n;++p){if(d[p].sum()==0)continue;Eigen::Vector3d inv=d[p].array().sqrt().inverse();Eigen::Matrix3d W=inv.asDiagonal()*v[p]*inv.asDiagonal();Eigen::Vector3d z=d[p].array().sqrt().matrix().asDiagonal()*xx[p];Eigen::Vector3d y=(W+trial*Eigen::Matrix3d::Identity()).ldlt().solve((W+old*Eigen::Matrix3d::Identity())*z);sum+=y.squaredNorm();}
  return std::sqrt(sum/norm);};
 PrismPointTrust work;double sums[3];work.Sums(dr,dd,dx,n,1,1,sums,false);require(std::abs(sums[0]/norm-1)<1e-12&&std::abs(sums[1]/curv-1)<1e-12);
 double maxerr=0;int cases=0;
 for(double old:{1e-7,1e-3,1.,100.})for(double alpha:{.5,.125,1./128}){
  auto q=work.Choose(dr,dd,dx,n,old,alpha,2);require(q.valid&&q.ratio<=alpha*(1+1e-8));double check=cpu_ratio(old,q.tau);maxerr=std::max(maxerr,std::abs(check-q.ratio)/alpha);require(check<=alpha*(1+1e-7)&&std::abs(check-q.ratio)<1e-7*alpha);
  double lo=old/alpha,hi=(old+3)/alpha-3;for(int i=0;i<60;++i){double mid=std::sqrt(lo*hi);if(cpu_ratio(old,mid)>alpha)lo=mid;else hi=mid;}require(q.tau>=hi*(1-1e-7)&&q.tau/hi<1.01);
  auto a=work.Choose(dr,dd,dx,n,old,alpha,1);require(a.valid&&std::abs(a.ratio-cpu_ratio(old,a.tau))<1e-7);++cases;
 }
 require(!work.Choose(dr,dd,dx,n,1e8,.5,2).valid);require(!work.Choose(dr,dd,dx,n,0,.5,2).valid);
 CUDA_CHECK(cudaMemset(dx,0,3*n*sizeof(double)));require(!work.Choose(dr,dd,dx,n,1,.5,2).valid);
 cudaFree(dr);cudaFree(dd);cudaFree(dx);std::printf("PASS %d root/Rayleigh cases, rank-deficient/zero blocks, cap/invalid/zero-step guards; max normalized ratio error %.9g\n",cases,maxerr);
}
