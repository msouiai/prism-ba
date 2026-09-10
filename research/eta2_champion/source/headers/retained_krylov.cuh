#pragma once
// Fixed-operator, fixed-RHS camera-space projection. Full two-pass
// orthogonalization deliberately favors robustness over a short recurrence.
namespace prism_recycle {
inline void Check(cudaError_t e){if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}
inline void Check(cublasStatus_t e){if(e!=CUBLAS_STATUS_SUCCESS)throw std::runtime_error("retained Krylov cuBLAS failure");}
struct Basis {
 int n,cap,m=0; double norm=0; bool exhausted=false;
 double *q=nullptr,*v=nullptr,*coeff=nullptr;
 std::vector<double> H;
 Basis(int size,int capacity):n(size),cap(capacity),H(capacity*capacity,0){
  Check(cudaMalloc((void**)&q,(size_t)n*(cap+1)*sizeof(double)));
  Check(cudaMalloc((void**)&v,(size_t)n*sizeof(double)));
  Check(cudaMalloc((void**)&coeff,(size_t)(cap+1)*sizeof(double)));
 }
 ~Basis(){cudaFree(q);cudaFree(v);cudaFree(coeff);}
 Basis(const Basis&)=delete;
 void Reset(cublasHandle_t h,const double* b){
  m=0;exhausted=false;std::fill(H.begin(),H.end(),0.);
  Check(cublasDnrm2(h,n,b,1,&norm));
  Check(cudaMemcpy(q,b,(size_t)n*sizeof(double),cudaMemcpyDeviceToDevice));
  if(!(norm>0) || !std::isfinite(norm)){exhausted=true;return;}
  double inv=1/norm;Check(cublasDscal(h,n,&inv,q,1));
 }
 template<class Apply> void Grow(cublasHandle_t h,Apply apply,int target){
  const double one=1,zero=0,minus=-1;
  while(m<std::min(target,cap) && !exhausted){
   apply(q+(size_t)m*n,v);
   std::vector<double> sums(m+1,0.),part(m+1);
   double original=0;Check(cublasDnrm2(h,n,v,1,&original));
   for(int pass=0;pass<2;++pass){
    Check(cublasDgemv(h,CUBLAS_OP_T,n,m+1,&one,q,n,v,1,&zero,coeff,1));
    Check(cudaMemcpy(part.data(),coeff,(m+1)*sizeof(double),cudaMemcpyDeviceToHost));
    for(int j=0;j<=m;++j)sums[j]+=part[j];
    Check(cublasDgemv(h,CUBLAS_OP_N,n,m+1,&minus,q,n,coeff,1,&one,v,1));
   }
   for(int j=0;j<=m;++j)H[j*cap+m]=H[m*cap+j]=sums[j];
   double beta=0;Check(cublasDnrm2(h,n,v,1,&beta));
   ++m;
   exhausted=!(beta>1e-13*std::max(original,1e-300)) || !std::isfinite(beta);
   if(!exhausted){
    Check(cudaMemcpy(q+(size_t)m*n,v,(size_t)n*sizeof(double),cudaMemcpyDeviceToDevice));
    double inv=1/beta;Check(cublasDscal(h,n,&inv,q+(size_t)m*n,1));
   }
  }
 }
 // Solve the projected SPD system, then independently apply the full
 // operator to check its true residual. These matvecs count in run timing.
 template<class Apply> bool Solve(cublasHandle_t h,Apply apply,const double* b,
   double shift,double* x,double& relative,double& prediction,bool verify=true){
  relative=std::numeric_limits<double>::infinity();prediction=0;
  if(!m)return false;
  std::vector<double> C(m*m,0),y(m,0.);y[0]=norm;
  for(int i=0;i<m;++i)for(int j=0;j<=i;++j){
   double a=H[i*cap+j]+(i==j?shift:0.);
   for(int k=0;k<j;++k)a-=C[i*m+k]*C[j*m+k];
   if(i==j){if(!(a>0)||!std::isfinite(a))return false;C[i*m+j]=std::sqrt(a);}
   else C[i*m+j]=a/C[j*m+j];
  }
  for(int i=0;i<m;++i){for(int j=0;j<i;++j)y[i]-=C[i*m+j]*y[j];y[i]/=C[i*m+i];}
  for(int i=m-1;i>=0;--i){for(int j=i+1;j<m;++j)y[i]-=C[j*m+i]*y[j];y[i]/=C[i*m+i];}
  Check(cudaMemcpy(coeff,y.data(),m*sizeof(double),cudaMemcpyHostToDevice));
  const double one=1,zero=0,minus=-1;
  Check(cublasDgemv(h,CUBLAS_OP_N,n,m,&one,q,n,coeff,1,&zero,x,1));
  if(!verify){
   // Galerkin optimality gives the reduced model decrease b_Q^T y / 2.
   // Used only to reconstruct checkpoints after a true terminal check.
   prediction=.5*norm*y[0];
   return std::isfinite(prediction);
  }
  apply(x,v);Check(cublasDaxpy(h,n,&shift,x,1,v,1));
  double bx=0,xax=0;Check(cublasDdot(h,n,b,1,x,1,&bx));Check(cublasDdot(h,n,x,1,v,1,&xax));
  prediction=bx-.5*xax;
  Check(cublasDaxpy(h,n,&minus,b,1,v,1));
  double residual=0;Check(cublasDnrm2(h,n,v,1,&residual));
  relative=residual/std::max(norm,1e-300);
  return std::isfinite(relative) && std::isfinite(prediction);
 }
};
} // namespace prism_recycle
