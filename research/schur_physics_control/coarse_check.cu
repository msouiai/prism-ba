// Algebra check on the actual GPU implementation, including wrapped history.
#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <cstdio>
#include "coarse.cuh"
int main(){
  cublasHandle_t h;PrismCoarse::blas(cublasCreate(&h));
  constexpr int n=48;
  Eigen::MatrixXd T(n,n);
  for(int j=0;j<n;++j)for(int i=0;i<n;++i)T(i,j)=std::sin((i+1)*(j+1)*.129)+.2*std::cos((i+2)*(j+3)*.057);
  Eigen::MatrixXd A=T.transpose()*T+Eigen::MatrixXd::Identity(n,n);
  Eigen::MatrixXd M=A.diagonal().cwiseInverse().asDiagonal();
  double *ad,*md,*pd,*apd,*zd;
  for(auto p:{&ad,&md})PrismCoarse::check(cudaMalloc(p,n*n*8ul));
  for(auto p:{&pd,&apd,&zd})PrismCoarse::check(cudaMalloc(p,n*8ul));
  PrismCoarse::check(cudaMemcpy(ad,A.data(),n*n*8ul,cudaMemcpyHostToDevice));
  PrismCoarse::check(cudaMemcpy(md,M.data(),n*n*8ul,cudaMemcpyHostToDevice));
  double one=1,zero=0;
  auto apply=[&](const double*x,double*y){PrismCoarse::blas(cublasDgemv(h,CUBLAS_OP_N,n,n,&one,ad,n,x,1,&zero,y,1));};
  auto base=[&](const double*x,double*y){PrismCoarse::blas(cublasDgemv(h,CUBLAS_OP_N,n,n,&one,md,n,x,1,&zero,y,1));};
  for(int rank:{8,16}){
    PrismCoarse c(n,rank);c.Prepare(h,apply);if(c.active)return 2;
    for(int j=0;j<2*rank+3;++j){
      Eigen::VectorXd p(n);for(int i=0;i<n;++i)p[i]=std::sin((i+1)*(j+.25)*.231);
      PrismCoarse::check(cudaMemcpy(pd,p.data(),n*8ul,cudaMemcpyHostToDevice));apply(pd,apd);
      c.Observe(h,pd,apd,p.squaredNorm());
    }
    c.FinishCollection(2*rank+3);c.Prepare(h,apply);
    if(!c.active||c.used!=rank)return 3;
    Eigen::MatrixXd Z(n,c.used),P(n,n);
    PrismCoarse::check(cudaMemcpy(Z.data(),c.Z,n*c.used*8ul,cudaMemcpyDeviceToHost));
    const Eigen::MatrixXd K=Z.transpose()*A*Z;
    const Eigen::MatrixXd Q=Z*K.llt().solve(Z.transpose());
    const Eigen::MatrixXd I=Eigen::MatrixXd::Identity(n,n);
    const Eigen::MatrixXd expected=Q+(I-Q*A)*M*(I-A*Q);
    for(int j=0;j<n;++j){
      Eigen::VectorXd e=Eigen::VectorXd::Unit(n,j);
      PrismCoarse::check(cudaMemcpy(pd,e.data(),n*8ul,cudaMemcpyHostToDevice));c.Apply(pd,zd,base);
      PrismCoarse::check(cudaMemcpy(P.col(j).data(),zd,n*8ul,cudaMemcpyDeviceToHost));
    }
    const double error=(P-expected).norm()/expected.norm();
    const double symmetry=(P-P.transpose()).norm()/P.norm();
    const double exact=(P*A*Z-Z).norm()/Z.norm();
    Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> es(.5*(P+P.transpose()).eval());
    const double mineig=es.eigenvalues().minCoeff();
    std::printf("COARSE_ALGEBRA rank=%d relative=%.17g symmetry=%.17g coarse_exactness=%.17g minimum_eigenvalue=%.17g\n",rank,error,symmetry,exact,mineig);
    if(!(error<1e-10&&symmetry<1e-10&&exact<1e-10&&mineig>0))return 4;
  }
  for(auto p:{ad,md,pd,apd,zd})cudaFree(p);cublasDestroy(h);
}
