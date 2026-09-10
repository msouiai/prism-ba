#pragma once
#include <Eigen/Dense>
#include <vector>
#include <algorithm>
#include <cmath>
#include <stdexcept>

// Balanced two-level inverse. History belongs to the PREVIOUS linear solve.
// All changes to Z/K happen before a PCG solve, never inside its recurrence.
struct PrismCoarse {
  int n, rank, cap, count=0, seen=0, previous_depth=0, used=0, rejects=0;
  bool active=false;
  double *V,*AV,*Z,*AZ,*ki,*coeff,*work,*dotbuf,*dense;
  cublasHandle_t handle=nullptr;
  explicit PrismCoarse(int size,int r):n(size),rank(r),cap(2*r) {
    if(r!=8 && r!=16)throw std::runtime_error("coarse rank must be 8 or 16");
    for(auto p:{&V,&AV})check(cudaMalloc(p,size_t(n)*cap*8));
    for(auto p:{&Z,&AZ})check(cudaMalloc(p,size_t(n)*rank*8));
    check(cudaMalloc(&ki,rank*rank*8ul));
    check(cudaMalloc(&coeff,rank*8ul));check(cudaMalloc(&dotbuf,rank*8ul));
    check(cudaMalloc(&work,n*8ul));check(cudaMalloc(&dense,cap*cap*8ul));
  }
  ~PrismCoarse(){for(auto p:{V,AV,Z,AZ,ki,coeff,work,dotbuf,dense})cudaFree(p);}
  static void check(cudaError_t e){if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}
  static void blas(cublasStatus_t e){if(e!=CUBLAS_STATUS_SUCCESS)throw std::runtime_error("coarse cuBLAS failure");}
  void Observe(cublasHandle_t h,const double*p,const double*ap,double norm2){
    if(!(norm2>0)||!std::isfinite(norm2))return;
    int j=seen%cap;++seen;count=std::min(cap,seen);
    check(cudaMemcpy(V+size_t(j)*n,p,n*8ul,cudaMemcpyDeviceToDevice));
    check(cudaMemcpy(AV+size_t(j)*n,ap,n*8ul,cudaMemcpyDeviceToDevice));
    double scale=1/std::sqrt(norm2);
    blas(cublasDscal(h,n,&scale,V+size_t(j)*n,1));
    blas(cublasDscal(h,n,&scale,AV+size_t(j)*n,1));
  }
  Eigen::MatrixXd Gram(cublasHandle_t h,const double*a,const double*b,int cols){
    double one=1,zero=0;
    blas(cublasDgemm(h,CUBLAS_OP_T,CUBLAS_OP_N,cols,cols,n,&one,a,n,b,n,&zero,dense,cols));
    Eigen::MatrixXd x(cols,cols);
    check(cudaMemcpy(x.data(),dense,size_t(cols)*cols*8,cudaMemcpyDeviceToHost));
    return .5*(x+x.transpose()).eval();
  }
  template<class Operator> void Prepare(cublasHandle_t h,Operator apply,int gate=16){
    handle=h;active=false;used=0;
    if(previous_depth<gate||count<2)return;
    Eigen::MatrixXd gram=Gram(h,V,V,count),stiff=Gram(h,V,AV,count);
    Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> ge(gram);
    if(ge.info()!=Eigen::Success||!ge.eigenvalues().allFinite()){++rejects;return;}
    double largest=ge.eigenvalues().maxCoeff();
    int first=0;while(first<count&&ge.eigenvalues()[first]<=1e-10*largest)++first;
    int good=count-first;if(good==0){++rejects;return;}
    Eigen::MatrixXd wh=ge.eigenvectors().rightCols(good);
    for(int j=0;j<good;++j)wh.col(j)/=std::sqrt(ge.eigenvalues()[j+first]);
    Eigen::MatrixXd projected=wh.transpose()*stiff*wh;
    Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> se(.5*(projected+projected.transpose()).eval());
    if(se.info()!=Eigen::Success||!se.eigenvalues().allFinite()){++rejects;return;}
    used=std::min(rank,good);
    Eigen::MatrixXd lift=wh*se.eigenvectors().leftCols(used);
    check(cudaMemcpy(dense,lift.data(),size_t(count)*used*8,cudaMemcpyHostToDevice));
    double one=1,zero=0;
    blas(cublasDgemm(h,CUBLAS_OP_N,CUBLAS_OP_N,n,used,count,&one,V,n,dense,count,&zero,Z,n));
    for(int j=0;j<used;++j)apply(Z+size_t(j)*n,AZ+size_t(j)*n);
    Eigen::MatrixXd K=Gram(h,Z,AZ,used);
    Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> ke(K);
    if(ke.info()!=Eigen::Success||!ke.eigenvalues().allFinite()||
       !(ke.eigenvalues().minCoeff()>1e-12*ke.eigenvalues().maxCoeff())){
      ++rejects;used=0;return;
    }
    Eigen::LLT<Eigen::MatrixXd> llt(K);
    if(llt.info()!=Eigen::Success){++rejects;used=0;return;}
    Eigen::MatrixXd inverse=llt.solve(Eigen::MatrixXd::Identity(used,used));
    if(!inverse.allFinite()){++rejects;used=0;return;}
    check(cudaMemcpy(ki,inverse.data(),size_t(used)*used*8,cudaMemcpyHostToDevice));
    active=true;
  }
  void StartCollection(){count=0;seen=0;}
  void FinishCollection(int depth){previous_depth=depth;}
  template<class Base> void Apply(const double*r,double*z,Base base){
    if(!active){base(r,z);return;}
    double one=1,zero=0,minus=-1;
    // q = K^-1 Z^T r; work = (I - S Q) r.
    blas(cublasDgemv(handle,CUBLAS_OP_T,n,used,&one,Z,n,r,1,&zero,dotbuf,1));
    blas(cublasDgemv(handle,CUBLAS_OP_N,used,used,&one,ki,used,dotbuf,1,&zero,coeff,1));
    check(cudaMemcpy(work,r,n*8ul,cudaMemcpyDeviceToDevice));
    blas(cublasDgemv(handle,CUBLAS_OP_N,n,used,&minus,AZ,n,coeff,1,&one,work,1));
    base(work,z);
    // z <- z + Z (q - K^-1 (SZ)^T z).
    blas(cublasDgemv(handle,CUBLAS_OP_T,n,used,&one,AZ,n,z,1,&zero,dotbuf,1));
    blas(cublasDgemv(handle,CUBLAS_OP_N,used,used,&minus,ki,used,dotbuf,1,&one,coeff,1));
    blas(cublasDgemv(handle,CUBLAS_OP_N,n,used,&one,Z,n,coeff,1,&one,z,1));
  }
};
