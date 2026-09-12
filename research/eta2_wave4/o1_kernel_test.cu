// Standalone native O1 kernels and exact-QP audit (no Eta2 performance timing).
#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <Eigen/Dense>
#include <vector>
#include <map>
#include <string>
#include <functional>
#include <stdexcept>
#include <chrono>
#include <cstdio>
#include <algorithm>
#include <cmath>
#include <fstream>
#define CUDA_CHECK(x) do{cudaError_t e=(x);if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}while(0)
using Scalar=double;
struct DeviceProblem {int ncam,npt,nobs;int* cam_idx;int* pt_idx;double* uv;};
struct DeviceState {double* R;double* t;double* X;double* intr;};
double ComputeCost(const DeviceProblem&,const DeviceState&,int,int){return 0;}
#include "o1.cuh"
void vec(std::ofstream& f,const std::string& key,const std::vector<double>& a){f<<'"'<<key<<"\":[";for(size_t i=0;i<a.size();++i){if(i)f<<',';f<<a[i];}f<<"],\n";}
int main(int argc,char** argv){try{
 const int nc=4,np=12,no=nc*np;DeviceProblem p{nc,np,no};DeviceState s;
 O1::Buf R(nc*9),t(nc*3),X(np*3),intr(nc*3),uv(no*2);s={R.p,t.p,X.p,intr.p};p.uv=uv.p;
 CUDA_CHECK(cudaMalloc(&p.cam_idx,no*4));CUDA_CHECK(cudaMalloc(&p.pt_idx,no*4));std::vector<int> ci(no),pi(no);
 std::vector<double> hr(9*nc),ht(3*nc),hx(3*np),hi(3*nc),hu(2*no);
 int mode=argc>2?atoi(argv[2]):0;double sg=mode>=3?1.:-1.;
 for(int i=0;i<nc;++i){Eigen::Matrix3d q=Eigen::AngleAxisd(.13*i,Eigen::Vector3d(1,.4,.2).normalized()).toRotationMatrix();for(int k=0;k<3;++k)for(int l=0;l<3;++l)hr[9*i+3*k+l]=q(k,l);ht[3*i]=.9*i;ht[3*i+1]=.2*i*i;hi[i]=400+20*i;}
 for(int j=0;j<np;++j){hx[3*j]=.4*sin(j);hx[3*j+1]=.5*cos(j*.7);hx[3*j+2]=sg*(4+.13*j);}
 if(mode==5)for(int i=0;i<nc;++i)hi[nc+i]=.01*(i-1);
 for(int j=0;j<np;++j)for(int i=0;i<nc;++i){int o=j*nc+i;ci[o]=i;pi[o]=j;Eigen::Vector3d y;for(int k=0;k<3;++k){y[k]=ht[3*i+k];for(int l=0;l<3;++l)y[k]+=hr[9*i+3*k+l]*hx[3*j+l];}double f=hi[i]*(1+hi[nc+i]*(y[0]*y[0]+y[1]*y[1])/(y[2]*y[2]));hu[2*o]=-f*y[0]/y[2]+.4*sin(o+1);hu[2*o+1]=-f*y[1]/y[2]+.3*cos(o);}
 R.from(hr);t.from(ht);X.from(hx);intr.from(hi);uv.from(hu);CUDA_CHECK(cudaMemcpy(p.cam_idx,ci.data(),no*4,cudaMemcpyHostToDevice));CUDA_CHECK(cudaMemcpy(p.pt_idx,pi.data(),no*4,cudaMemcpyHostToDevice));
 O1::Solver a(p,s);a.initializeRays();a.assembleBlocks();
 if(mode==1||mode==4){
  // Prescribe a quadratic minimizer that pushes point zero 90% toward the pole.
  auto U=a.U.host(),V=a.V.host(),W=a.W.host();std::vector<double> dc(3*nc),dp(3*np),bc(3*nc),bp(3*np);dp[2]=-.9*hx[2];
  for(int k=0;k<3;++k)for(int l=0;l<3;++l)bp[k]+=V[3*k+l]*dp[l];
  for(int o=0;o<nc;++o)for(int k=0;k<3;++k)for(int l=0;l<3;++l)bc[3*o+k]+=W[9*o+3*k+l]*dp[l];a.bc.from(bc);a.bp.from(bp);
 }
 if(mode==2){a.act={0,1};a.buildGroups();a.solve();a.backsolve();a.copy(a.tc.p,a.tn.p,3*nc);a.copy(a.xc.p,a.xn.p,3*np);}
 else if(mode==4){bool guarded=false;std::string reason;try{a.qp([](){return false;});}catch(const std::runtime_error& e){reason=e.what();guarded=reason=="more_than_three_active_point_constraints";}std::ofstream out(argv[1]);out<<"{\"mode\":4,\"expected_guard\":"<<(guarded?"true":"false")<<",\"reason\":\""<<reason<<"\"}\n";cudaFree(p.cam_idx);cudaFree(p.pt_idx);return guarded?0:4;}
 else a.qp([](){return false;});
 std::ofstream out(argv[1]);out.precision(17);out<<"{\n";vec(out,"R",hr);vec(out,"t",ht);vec(out,"X",hx);vec(out,"intr",hi);vec(out,"uv",hu);vec(out,"ray",a.v.host());vec(out,"weight",a.w.host());vec(out,"U",a.U.host());vec(out,"V",a.V.host());vec(out,"Vinv",a.vi.host());vec(out,"W",a.W.host());vec(out,"bc",a.bc.host());vec(out,"bp",a.bp.host());vec(out,"dt",a.tc.host());vec(out,"dX",a.xc.host());vec(out,"axis",a.axis.host());vec(out,"nu",a.nu.host());
 if(mode==5){a.rotation();a.intrinsics();vec(out,"rotation_updated",R.host());vec(out,"intrinsics_updated",intr.host());}
 out<<"\"nc\":"<<nc<<",\"np\":"<<np<<",\"far\":"<<a.far<<",\"mode\":"<<mode<<",\"schur_residual\":"<<a.linearResidual<<",\"point_residual\":"<<a.pointResidualNorm<<",\"act\":[";for(size_t i=0;i<a.act.size();++i){if(i)out<<',';out<<a.act[i];}out<<"],\"rank_failure_checked\":";
 bool fail=false;a.act={0,1,2,3};try{a.buildGroups();}catch(const std::runtime_error&){fail=true;}out<<(fail?"true":"false")<<"}\n";cudaFree(p.cam_idx);cudaFree(p.pt_idx);return fail?0:3;
}catch(const std::exception& e){fprintf(stderr,"O1 TEST FAILED: %s\n",e.what());return 2;}}
