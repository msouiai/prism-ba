#pragma once
#include <Eigen/Dense>
#include <iomanip>

struct WaveStepRecord {
  int outer=0,retry=0,accepts=0,iterations=0;
  double lambda=0,tau=0,radius=0,raw=0,eta=0,rho=NAN;
  double gauge=NAN,top5=NAN,gauge_seconds=0;
  bool observed=false,accepted=false,repair=false;
};
struct WaveTrace {
  std::string path;
  std::vector<WaveStepRecord> rows;
  explicit WaveTrace(const char* name):path(name) {rows.reserve(2048);}
  void Observe(WaveStepRecord& row,const DeviceState& s,const double* E,
               const double* z,int nc){
    auto begin=std::chrono::steady_clock::now();
    std::vector<double> rv(9ul*nc),tv(3ul*nc),ev(9ul*nc),zv(9ul*nc);
    CUDA_CHECK(cudaMemcpy(rv.data(),s.R,8ul*rv.size(),cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(tv.data(),s.t,8ul*tv.size(),cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(ev.data(),E,8ul*ev.size(),cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(zv.data(),z,8ul*zv.size(),cudaMemcpyDeviceToHost));
    using RowMat=Eigen::Matrix<double,3,3,Eigen::RowMajor>;
    Eigen::MatrixXd C(nc,3);Eigen::Vector3d center=Eigen::Vector3d::Zero();
    for(int i=0;i<nc;++i){Eigen::Map<const RowMat> R(rv.data()+9*i);
      Eigen::Map<const Eigen::Vector3d> t(tv.data()+3*i);
      C.row(i)=(-R.transpose()*t).transpose();center+=C.row(i).transpose();}
    center/=std::max(1,nc);
    Eigen::MatrixXd Z=Eigen::MatrixXd::Zero(9*nc,7);
    std::vector<double> cnorm(nc,0);
    Eigen::Map<const Eigen::VectorXd> x(zv.data(),9*nc);
    row.raw=x.norm();row.observed=std::isfinite(row.raw);
    for(int i=0;i<nc;++i){
      Eigen::Map<const RowMat> R(rv.data()+9*i);
      for(int j=0;j<3;++j){Eigen::Vector3d u=Eigen::Vector3d::Unit(j);
        Z.block<3,1>(9*i,j)=-R*u;
        Z.block<3,1>(9*i+3,j)=R*u.cross(center);
        Z.block<3,1>(9*i+3,3+j)=-R*u;}
      Z.block<3,1>(9*i+3,6)=-R*(C.row(i).transpose()-center);
      for(int j=0;j<9;++j){Z.row(9*i+j)/=ev[9*i+j];cnorm[i]+=zv[9*i+j]*zv[9*i+j];}
    }
    for(int j=0;j<7;++j){double n=Z.col(j).norm();if(n>0)Z.col(j)/=n;}
    if(row.observed && Z.allFinite()){
      Eigen::ColPivHouseholderQR<Eigen::MatrixXd> qr(Z);qr.setThreshold(1e-10);
      Eigen::VectorXd q=qr.householderQ().adjoint()*x;
      row.gauge=q.head(qr.rank()).squaredNorm()/std::max(1e-300,x.squaredNorm());
      std::sort(cnorm.begin(),cnorm.end(),std::greater<double>());
      double sum=0;for(int i=0;i<std::min(5,nc);++i)sum+=cnorm[i];
      row.top5=sum/std::max(1e-300,x.squaredNorm());
    }
    row.gauge_seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
  }
  ~WaveTrace(){
    std::ofstream f(path);f<<std::setprecision(17)<<"[";
    auto num=[&](double d){if(std::isfinite(d))f<<d;else f<<"null";};
    for(size_t i=0;i<rows.size();++i){auto& r=rows[i];if(i)f<<",";
      f<<"{\"outer\":"<<r.outer<<",\"retry\":"<<r.retry<<",\"accepts_before\":"<<r.accepts;
      f<<",\"lambda\":";num(r.lambda);f<<",\"tau\":";num(r.tau);
      f<<",\"radius_before\":";num(r.radius);f<<",\"raw_norm\":";num(r.raw);
      f<<",\"raw_radius_ratio\":";num(r.radius>0?r.raw/r.radius:NAN);
      f<<",\"eta\":";num(r.eta);f<<",\"rho\":";num(r.rho);
      f<<",\"gauge_fraction\":";num(r.gauge);f<<",\"top5_fraction\":";num(r.top5);
      f<<",\"gauge_seconds\":";num(r.gauge_seconds);
      f<<",\"pcg_iterations\":"<<r.iterations<<",\"accepted\":"<<(r.accepted?"true":"false")
       <<",\"numeric_repair\":"<<(r.repair?"true":"false")
       <<",\"observed\":"<<(r.observed?"true":"false")<<"}";
    }f<<"]\n";f.close();if(!f)std::fprintf(stderr,"WAVE_TRACE write failed\n");
  }
};
struct WaveAttempt {
  WaveTrace* owner;StcgAttemptClock& clock;WaveStepRecord row;
  WaveAttempt(WaveTrace* o,StcgAttemptClock& c,int k,int r,int a):owner(o),clock(c){row.outer=k;row.retry=r;row.accepts=a;}
  ~WaveAttempt(){if(owner){row.iterations=clock.row.pcg_iterations;row.accepted=clock.row.accepted;
    row.repair=clock.row.numeric_repair;owner->rows.push_back(row);}}
};
