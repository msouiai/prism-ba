#pragma once
#include "projected_radius.h"
// Capture r_j and S r_j from CG's already-computed A p_j, where A=S+sigma I.
// A r_j = A p_j - beta_{j-1} A p_{j-1}. No extra Schur product per column.
__global__ void MFStoreCgProjection(int n,int m,double inv,double beta,double sigma,
 const double*r,const double*ap,double*prev,double*Q,double*SQ){
 int i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=n)return;
 double q=r[i]*inv;Q[(size_t)m*n+i]=q;
 SQ[(size_t)m*n+i]=(ap[i]-(m?beta*prev[i]:0.))*inv-sigma*q;prev[i]=ap[i];
}
struct PrismCgProjection{
 int n,m=0;static constexpr int cap=128;
 double *Q=nullptr,*SQ=nullptr,*prev=nullptr,*G=nullptr,*H=nullptr,*rhs=nullptr,*coef=nullptr,*x=nullptr;
 int rank=0;double multiplier=0,model_prediction=0,gram_min=0;
 explicit PrismCgProjection(int size):n(size){
  for(double**p:{&Q,&SQ})CUDA_CHECK(cudaMalloc(p,(size_t)n*cap*8));
  for(double**p:{&prev,&x})CUDA_CHECK(cudaMalloc(p,(size_t)n*8));
  for(double**p:{&G,&H})CUDA_CHECK(cudaMalloc(p,(size_t)cap*cap*8));
  for(double**p:{&rhs,&coef})CUDA_CHECK(cudaMalloc(p,(size_t)cap*8));
 }
 ~PrismCgProjection(){for(double*p:{Q,SQ,prev,G,H,rhs,coef,x})cudaFree(p);}
 void Reset(){m=0;}
 void Append(const double*r,const double*ap,double rr,double beta,double sigma){
  if(m>=cap || !(rr>0))throw std::runtime_error("CG projection capacity or residual");
  MFStoreCgProjection<<<(n+255)/256,256>>>(n,m,1./std::sqrt(rr),beta,sigma,r,ap,prev,Q,SQ);++m;
 }
 bool Solve(cublasHandle_t h,const double*b,double radius){
  const double one=1,zero=0;
  cublasDgemm(h,CUBLAS_OP_T,CUBLAS_OP_N,m,m,n,&one,Q,n,Q,n,&zero,G,m);
  cublasDgemm(h,CUBLAS_OP_T,CUBLAS_OP_N,m,m,n,&one,Q,n,SQ,n,&zero,H,m);
  cublasDgemv(h,CUBLAS_OP_T,n,m,&one,Q,n,b,1,&zero,rhs,1);
  Eigen::MatrixXd g(m,m),a(m,m);Eigen::VectorXd f(m);
  CUDA_CHECK(cudaMemcpy(g.data(),G,m*m*8,cudaMemcpyDeviceToHost));CUDA_CHECK(cudaMemcpy(a.data(),H,m*m*8,cudaMemcpyDeviceToHost));CUDA_CHECK(cudaMemcpy(f.data(),rhs,m*8,cudaMemcpyDeviceToHost));
  if(!g.allFinite()||!a.allFinite()||!f.allFinite())return false;
  g=(.5*(g+g.transpose())).eval();a=(.5*(a+a.transpose())).eval();
  Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> es(g);if(es.info()!=Eigen::Success)return false;
  gram_min=es.eigenvalues()[0];const double threshold=1e-10*es.eigenvalues().maxCoeff();rank=0;
  for(int j=0;j<m;++j)rank+=es.eigenvalues()[j]>threshold;
  if(!rank)return false;Eigen::MatrixXd W(m,rank);int col=0;
  for(int j=0;j<m;++j)if(es.eigenvalues()[j]>threshold)W.col(col++)=es.eigenvectors().col(j)/std::sqrt(es.eigenvalues()[j]);
  Eigen::MatrixXd projected=(W.transpose()*a*W).eval();Eigen::VectorXd pb=W.transpose()*f;
  PrismProjectedRadius model(projected,pb);auto result=model.Solve(radius);
  Eigen::VectorXd c=W*result.y;multiplier=result.lambda;model_prediction=f.dot(c)-.5*c.dot(a*c);
  if(!c.allFinite() || !(model_prediction>0))return false;
  CUDA_CHECK(cudaMemcpy(coef,c.data(),m*8,cudaMemcpyHostToDevice));
  cublasDgemv(h,CUBLAS_OP_N,n,m,&one,Q,n,coef,1,&zero,x,1);
  double norm=0;cublasDnrm2(h,n,x,1,&norm);if(!std::isfinite(norm))return false;
  if(norm>radius){double scale=radius/norm;cublasDscal(h,n,&scale,x,1);}
  return true;
 }
};
