#pragma once
#include <chrono>
#include "retained_krylov.cuh"
namespace prism_recycle {
// Capture only reads live CG vectors. Orthogonalization is deferred until an
// expansion, and transforms P and AP together without applying the operator.
struct CgCapture {
 int n,cap,m=0; double shift=0; double *P=nullptr,*AP=nullptr;
 CgCapture(int size,int capacity):n(size),cap(capacity){
  Check(cudaMalloc((void**)&P,(size_t)n*cap*sizeof(double)));
  Check(cudaMalloc((void**)&AP,(size_t)n*cap*sizeof(double)));
 }
 ~CgCapture(){cudaFree(P);cudaFree(AP);}
 CgCapture(const CgCapture&)=delete;
 void Reset(double seed){m=0;shift=seed;}
 void Append(const double*p,const double*ap){
  if(m==cap)return;
  Check(cudaMemcpy(P+(size_t)m*n,p,(size_t)n*sizeof(double),cudaMemcpyDeviceToDevice));
  Check(cudaMemcpy(AP+(size_t)m*n,ap,(size_t)n*sizeof(double),cudaMemcpyDeviceToDevice));++m;
 }
 void Import(cublasHandle_t h,const double*b,Basis& basis){
  basis.Reset(h,b);
  const double one=1,zero=0,minus=-1,negative_shift=-shift;
  for(int i=0;i<m;++i){
   double *q=basis.q+(size_t)i*n,*aq=AP+(size_t)i*n;
   Check(cudaMemcpy(q,P+(size_t)i*n,(size_t)n*sizeof(double),cudaMemcpyDeviceToDevice));
   Check(cublasDaxpy(h,n,&negative_shift,P+(size_t)i*n,1,aq,1));
   double original;Check(cublasDnrm2(h,n,q,1,&original));
   for(int pass=0;pass<2 && i>0;++pass){
    Check(cublasDgemv(h,CUBLAS_OP_T,n,i,&one,basis.q,n,q,1,&zero,basis.coeff,1));
    Check(cublasDgemv(h,CUBLAS_OP_N,n,i,&minus,basis.q,n,basis.coeff,1,&one,q,1));
    Check(cublasDgemv(h,CUBLAS_OP_N,n,i,&minus,AP,n,basis.coeff,1,&one,aq,1));
   }
   double length;Check(cublasDnrm2(h,n,q,1,&length));
   if(!(length>1e-12*original) || !std::isfinite(length))break;
   double inv=1/length;Check(cublasDscal(h,n,&inv,q,1));Check(cublasDscal(h,n,&inv,aq,1));++basis.m;
  }
  const int count=basis.m;
  if(!count){basis.exhausted=true;return;}
  std::vector<double> column(count);
  for(int i=0;i<count;++i){
   Check(cublasDgemv(h,CUBLAS_OP_T,n,count,&one,basis.q,n,AP+(size_t)i*n,1,&zero,basis.coeff,1));
   Check(cudaMemcpy(column.data(),basis.coeff,count*sizeof(double),cudaMemcpyDeviceToHost));
   for(int j=0;j<count;++j)basis.H[j*basis.cap+i]=column[j];
  }
  for(int i=0;i<count;++i)for(int j=0;j<i;++j){
   double v=.5*(basis.H[i*basis.cap+j]+basis.H[j*basis.cap+i]);
   basis.H[i*basis.cap+j]=basis.H[j*basis.cap+i]=v;
  }
  // The last orthogonalized CG direction completes K_m. Its operator
  // residual supplies the next Krylov vector if the expansion needs more.
  double* next=basis.q+(size_t)count*n;
  Check(cudaMemcpy(next,AP+(size_t)(count-1)*n,(size_t)n*sizeof(double),cudaMemcpyDeviceToDevice));
  double original;Check(cublasDnrm2(h,n,next,1,&original));
  for(int pass=0;pass<2;++pass){
   Check(cublasDgemv(h,CUBLAS_OP_T,n,count,&one,basis.q,n,next,1,&zero,basis.coeff,1));
   Check(cublasDgemv(h,CUBLAS_OP_N,n,count,&minus,basis.q,n,basis.coeff,1,&one,next,1));
  }
  double length;Check(cublasDnrm2(h,n,next,1,&length));
  basis.exhausted=!(length>1e-12*std::max(original,1e-300)) || !std::isfinite(length);
  if(!basis.exhausted){double inv=1/length;Check(cublasDscal(h,n,&inv,next,1));}
 }
};
} // namespace prism_recycle

namespace prism_recycle {
// Diagnostic fixed-operator ablation. Never used by normal solver calls.
template<class Apply>
void AuditCapture(cublasHandle_t h,const double*b,const std::vector<double>& shifts,
                  CgCapture& source,Apply apply,double tolerance){
 for(int rep=1;rep<=3;++rep)for(int order=0;order<2;++order){
  const bool reuse=(order==(rep%2));
  CgCapture copy(source.n,source.cap);copy.m=source.m;copy.shift=source.shift;
  Check(cudaMemcpy(copy.P,source.P,(size_t)source.n*source.m*sizeof(double),cudaMemcpyDeviceToDevice));
  Check(cudaMemcpy(copy.AP,source.AP,(size_t)source.n*source.m*sizeof(double),cudaMemcpyDeviceToDevice));
  Basis basis(source.n,source.cap);double* x;Check(cudaMalloc((void**)&x,(size_t)source.n*sizeof(double)));
  int calls=0;auto op=[&](const double*v,double*w){apply(v,w);++calls;};
  Check(cudaDeviceSynchronize());auto begin=std::chrono::steady_clock::now();
  if(reuse)copy.Import(h,b,basis);else basis.Reset(h,b);
  std::vector<int> depths={source.m};for(int d:{8,16,32,64})if(d>source.m)depths.push_back(d);
  bool valid=false;double worst=0;
  for(int depth:depths){
   basis.Grow(h,op,depth);valid=basis.m>0;worst=0;
   for(double shift:shifts){double residual,prediction;
    bool finite=basis.Solve(h,op,b,shift,x,residual,prediction);
    worst=std::max(worst,residual);valid=valid&&finite&&residual<=tolerance;}
   if(valid||basis.exhausted)break;
  }
  Check(cudaDeviceSynchronize());double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
  std::printf("CAPTURE_AUDIT rep=%d reuse=%d captured=%d depth=%d matvecs=%d seconds=%.9f residual=%.17g tolerance=%.17g valid=%d\n",
   rep,(int)reuse,source.m,basis.m,calls,seconds,worst,tolerance,(int)valid);
  cudaFree(x);
 }
 std::fflush(stdout);
}
} // namespace prism_recycle
