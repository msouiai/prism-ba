#define OCA_CORE_LIBRARY
#include "oca_cuda.cu"
#include <Eigen/Dense>
#include <Eigen/Geometry>
#include <random>
int main(){
 DeviceProblem p{};DeviceState s{};p.ncam=1;p.npt=17;p.nobs=513;
 std::mt19937 rng(123);std::normal_distribution<double> random;
 Eigen::Matrix3d R=Eigen::AngleAxisd(.3,Eigen::Vector3d(1,2,3).normalized()).toRotationMatrix();Eigen::Vector3d t(.1,-.2,.3);
 std::vector<int> ci(p.nobs,0),pi(p.nobs);std::vector<double> uv(2*p.nobs),rr(9),tt(3),xx(3*p.npt),base(9+3*p.npt),step;
 for(int i=0;i<3;++i){tt[i]=t[i];for(int j=0;j<3;++j)rr[3*i+j]=R(i,j);}
 for(int i=0;i<p.npt;++i){xx[3*i]=random(rng);xx[3*i+1]=random(rng);xx[3*i+2]=4+std::abs(random(rng));}
 for(int o=0;o<p.nobs;++o){pi[o]=o%p.npt;uv[2*o]=20*random(rng);uv[2*o+1]=20*random(rng);}
 for(auto& x:base)x=.03*random(rng);base[6]=2;base[7]=.0001;base[8]=.00001;
 std::vector<void*> allocations;auto upload=[&](auto a,auto** dest){CUDA_CHECK(cudaMalloc(dest,a.size()*sizeof(a[0])));allocations.push_back(*dest);CUDA_CHECK(cudaMemcpy(*dest,a.data(),a.size()*sizeof(a[0]),cudaMemcpyHostToDevice));};
 upload(ci,&p.cam_idx);upload(pi,&p.pt_idx);upload(uv,&p.uv);upload(rr,&s.R);upload(tt,&s.t);upload(xx,&s.X);upload(std::vector<double>{500},&p.f);upload(std::vector<double>{.002},&p.k1);upload(std::vector<double>{.00001},&p.k2);double* ds;upload(base,&ds);
 PrismFullModel model;double maxerr=0;int cases=0;
 for(double mask:{0.,1.})for(double cs:{0.,.7,1.})for(double ps:{0.,1.4}){
  step=base;for(int i=0;i<9;++i)step[i]*=cs;for(size_t i=9;i<step.size();++i)step[i]*=ps;
  CUDA_CHECK(cudaMemcpy(ds,step.data(),step.size()*sizeof(double),cudaMemcpyHostToDevice));auto gpu=model.Evaluate(p,s,ds,mask);
  auto residual=[&](int o,double eps){Eigen::Vector3d w(step[0],step[1],step[2]);Eigen::Matrix3d Rd=R;if(w.norm()>0)Rd=Eigen::AngleAxisd(eps*w.norm(),w.normalized()).toRotationMatrix()*R;int k=pi[o];Eigen::Vector3d X(xx[3*k],xx[3*k+1],xx[3*k+2]),dx(step[9+3*k],step[10+3*k],step[11+3*k]);Eigen::Vector3d q=Rd*(X+eps*dx)+t+eps*Eigen::Vector3d(step[3],step[4],step[5]);Eigen::Vector2d v=-q.head<2>()/q[2];double radius=v.squaredNorm();return Eigen::Vector2d((500+eps*step[6])*(1+(.002+eps*step[7])*radius+(.00001+eps*step[8]*mask)*radius*radius)*v-Eigen::Vector2d(uv[2*o],uv[2*o+1]));};
  double g=0,q=0;for(int o=0;o<p.nobs;++o){Eigen::Vector2d jd=(residual(o,1e-5)-residual(o,-1e-5))/(2e-5);g+=residual(o,0).dot(jd);q+=jd.squaredNorm();}
  for(auto pair:{std::make_pair(g,gpu.slope),std::make_pair(q,gpu.curvature),std::make_pair(-g-.5*q,gpu.prediction)}){double e=std::abs(pair.first-pair.second)/std::max(1.,std::abs(pair.first));maxerr=std::max(maxerr,e);if(e>1e-7)throw std::runtime_error("full model finite-difference mismatch");}++cases;
 }
 for(auto a:allocations)cudaFree(a);std::printf("PASS %d finite-difference mixed-block/mask cases; max error %.9g\n",cases,maxerr);
}
