#include <cuda_runtime.h>
#include <math_constants.h>
#include <Eigen/Dense>
#include <Eigen/Geometry>
#include <vector>
#include <iostream>
#include <stdexcept>
#include <cmath>
#define CUDA_CHECK(x) do{auto e=(x);if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}while(0)
struct DeviceProblem{int *point_obs_offsets,*point_obs_list,*cam_idx;double* uv;int npt,ncam;};
struct DeviceState{double *R,*t,*X,*f,*k1,*k2;};
#define INTR_F(p,s) ((s).f)
#define INTR_K1(p,s) ((s).k1)
#define INTR_K2(p,s) ((s).k2)
#include "point_refinement_candidate.cuh"
template<class T>T* upload(const std::vector<T>& v){T* p;CUDA_CHECK(cudaMalloc(&p,v.size()*sizeof(T)));CUDA_CHECK(cudaMemcpy(p,v.data(),v.size()*sizeof(T),cudaMemcpyHostToDevice));return p;}
int main(){
  const int nc=3,np=4;std::vector<int> offsets={0,3,68,68,71},order(71),ci(71);
  std::vector<double> R(27),t(9),X={.5,.2,-4., -.8,.5,-6., 1.,2.,-3., 0.,0.,0.},f={700,750,680},k1={.02,-.01,.03},k2={.001,.002,-.001},uv(142),step(9*nc+3*np);
  for(int c=0;c<nc;++c){Eigen::Matrix3d r=Eigen::AngleAxisd(.05*c,Eigen::Vector3d::UnitY()).toRotationMatrix();for(int a=0;a<3;++a)for(int b=0;b<3;++b)R[9*c+3*a+b]=r(a,b);t[3*c]=.3*c;t[3*c+1]=-.1*c;}
  auto pixel=[&](int c,const Eigen::Vector3d& x){Eigen::Matrix<double,3,3,Eigen::RowMajor> r=Eigen::Map<Eigen::Matrix<double,3,3,Eigen::RowMajor>>(R.data()+9*c);Eigen::Vector3d q=r*x+Eigen::Map<Eigen::Vector3d>(t.data()+3*c);Eigen::Vector2d u=-q.head<2>()/q[2];double s=u.squaredNorm();return Eigen::Vector2d(f[c]*(1+k1[c]*s+k2[c]*s*s)*u);};
  for(int p=0;p<np;++p)for(int o=offsets[p];o<offsets[p+1];++o){order[o]=o;ci[o]=o%nc;auto u=pixel(ci[o],Eigen::Map<Eigen::Vector3d>(X.data()+3*p)+Eigen::Vector3d(.1,-.07,.2));uv[2*o]=u[0]+.01*(o%5);uv[2*o+1]=u[1];}
  // The last track has qz=0 in camera zero and must safely retain its input.
  for(int o=68;o<71;++o){ci[o]=0;uv[2*o]=uv[2*o+1]=0;}
  std::vector<double> expected(step.size());double max_error=0;
  for(int p=0;p<2;++p){Eigen::Vector3d x=Eigen::Map<Eigen::Vector3d>(X.data()+3*p),g=Eigen::Vector3d::Zero();Eigen::Matrix3d H=Eigen::Matrix3d::Zero();
    auto cost=[&](const Eigen::Vector3d& y){double s=0;for(int o=offsets[p];o<offsets[p+1];++o)s+=.5*(pixel(ci[o],y)-Eigen::Map<Eigen::Vector2d>(uv.data()+2*o)).squaredNorm();return s;};
    for(int o=offsets[p];o<offsets[p+1];++o){Eigen::Matrix<double,2,3> J;for(int a=0;a<3;++a){Eigen::Vector3d d=Eigen::Vector3d::Zero();d[a]=1e-6;J.col(a)=(pixel(ci[o],x+d)-pixel(ci[o],x-d))/(2e-6);}Eigen::Vector2d e=pixel(ci[o],x)-Eigen::Map<Eigen::Vector2d>(uv.data()+2*o);H+=J.transpose()*J;g+=J.transpose()*e;}
    double scale=H.trace()/3;for(int a=0;a<3;++a)H(a,a)+=1e-6*std::max(H(a,a),1e-3*scale);
    Eigen::Vector3d d=H.llt().solve(-g);double best=cost(x),alpha=0;for(int j=0;j<3;++j){double z=std::ldexp(1.,-j),v=cost(x+z*d);if(v<best){best=v;alpha=z;}}
    Eigen::Map<Eigen::Vector3d>(expected.data()+9*nc+3*p)=alpha*d;
  }
  DeviceProblem p{upload(offsets),upload(order),upload(ci),upload(uv),np,nc};DeviceState s{upload(R),upload(t),upload(X),upload(f),upload(k1),upload(k2)};double* ds=upload(step);PrismPointRefinement refine;auto changed=refine.Choose(p,s,ds);CUDA_CHECK(cudaMemcpy(step.data(),ds,step.size()*8,cudaMemcpyDeviceToHost));
  for(size_t i=0;i<step.size();++i){if(!std::isfinite(step[i]))throw std::runtime_error("nonfinite step");max_error=std::max(max_error,std::abs(step[i]-expected[i]));}
  std::cerr<<"max_error="<<max_error<<" changed="<<changed<<"\n";
  if(max_error>1e-6||changed!=2)throw std::runtime_error("finite-difference point refinement mismatch");
  std::cout<<"{\"maximum_step_error\":"<<max_error<<",\"changed_tracks\":"<<changed<<",\"tested_tracks\":4,\"long_track_observations\":65,\"unseen_and_nonfinite_retained\":true}\n";
}
