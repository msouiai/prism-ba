#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <vector>
#include <stdexcept>
#include <cstdio>
#include <Eigen/Dense>
#define CUDA_CHECK(x) do{if((x)!=cudaSuccess)throw std::runtime_error("CUDA error");}while(0)
#include "camera_tr_diagnostic.cuh"
int main(){
 const int n=9;Eigen::MatrixXd A(n,n);Eigen::VectorXd b(n),E(n);
 for(int i=0;i<n;++i){b[i]=.2+i;E[i]=.1+.03*i;for(int j=0;j<n;++j)A(i,j)=std::sin(1.+i*9+j);}
 Eigen::MatrixXd S=A.transpose()*A+.1*Eigen::MatrixXd::Identity(n,n);
 double *dS,*db,*dx,*de;CUDA_CHECK(cudaMalloc(&dS,n*n*8));CUDA_CHECK(cudaMalloc(&db,n*8));CUDA_CHECK(cudaMalloc(&dx,n*8));CUDA_CHECK(cudaMalloc(&de,n*8));
 CUDA_CHECK(cudaMemcpy(dS,S.data(),n*n*8,cudaMemcpyHostToDevice));CUDA_CHECK(cudaMemcpy(db,b.data(),n*8,cudaMemcpyHostToDevice));CUDA_CHECK(cudaMemcpy(de,E.data(),n*8,cudaMemcpyHostToDevice));
 cublasHandle_t blas;cublasCreate(&blas);int operations=0;std::vector<Eigen::VectorXd> candidates;
 {
 PrismCameraTR tr(n);tr.radius=2;
 auto op=[&](const double* x,double* y){double one=1,zero=0;cublasDgemv(blas,CUBLAS_OP_N,n,n,&one,dS,n,x,1,&zero,y,1);++operations;};
 for(int i=0;i<5;++i){double shift=std::pow(10.,i-2);Eigen::VectorXd x=(S+shift*Eigen::MatrixXd::Identity(n,n)).ldlt().solve(b);candidates.push_back(x);
  CUDA_CHECK(cudaMemcpy(dx,x.data(),n*8,cudaMemcpyHostToDevice));tr.Add(dx,i,8,db,blas,op);}
 double maxerr=0;
 for(double radius:{2.,.5,.125,.03125}){
  tr.radius=radius;tr.Reset();tr.Reconsider(blas);
  double best=-1;Eigen::VectorXd expected(n);
  for(auto x:candidates){if(x.norm()>radius)x*=radius/x.norm();double pred=b.dot(x)-.5*x.dot(S*x);if(pred>best){best=pred;expected=x;}}
  Eigen::VectorXd got(n);CUDA_CHECK(cudaMemcpy(got.data(),tr.best,n*8,cudaMemcpyDeviceToHost));
  maxerr=std::max(maxerr,(got-expected).norm());
  if((got-expected).norm()>1e-10||std::abs(tr.best_prediction-best)>1e-10||got.norm()>radius*(1+1e-10)||operations!=5)throw std::runtime_error("candidate reuse/selection mismatch");
  Eigen::VectorXd physical=E.array()*got.array();CUDA_CHECK(cudaMemcpy(dx,physical.data(),n*8,cudaMemcpyHostToDevice));
  MFTRUnscale<<<1,32>>>(dx,de,tr.work,n);double norm=0;cublasDnrm2(blas,n,tr.work,1,&norm);
  if(std::abs(norm-got.norm())>1e-12)throw std::runtime_error("actual camera radius mismatch");
 }
 std::printf("PASS four radii; cached candidate re-selection uses zero extra operator calls; max vector error %.3g; physical-to-scaled norm verified\n",maxerr);
 }
 cublasDestroy(blas);cudaFree(dS);cudaFree(db);cudaFree(dx);cudaFree(de);
}
