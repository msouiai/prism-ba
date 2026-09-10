#pragma once
// Diagnostic only: fixed-operator CG comparison. Called only by OCA_KRYLOV_AUDIT.
namespace prism_audit {
struct Buffer {
  double* p=nullptr;
  explicit Buffer(size_t n){if(cudaMalloc((void**)&p,n*sizeof(double))!=cudaSuccess)throw std::runtime_error("audit allocation failed");}
  ~Buffer(){cudaFree(p);}
  Buffer(const Buffer&)=delete;
};
struct Result {double seconds;int matvecs;std::vector<double> residuals,solution;bool curvature_ok;};
template<class Apply>
Result Solve(cublasHandle_t h,int n,const double* b,const std::vector<double>& shifts,
             Apply apply,bool shared,double tolerance,int limit){
 const int L=(int)shifts.size();Buffer X((size_t)L*n),P((size_t)L*n),R(n),A(n);
 auto copy=[&](double* out,const double* in){cudaMemcpy(out,in,n*sizeof(double),cudaMemcpyDeviceToDevice);};
 auto dot=[&](const double* a,const double* b){double v;cublasDdot(h,n,a,1,b,1,&v);return v;};
 auto axpy=[&](double* y,double a,const double*x){cublasDaxpy(h,n,&a,x,1,y,1);};
 auto scale=[&](double* y,double a){cublasDscal(h,n,&a,y,1);};
 auto op=[&](const double* x,double* y,double shift){apply(x,y);axpy(y,shift,x);};
 const double norm=std::sqrt(dot(b,b));int calls=0;bool curvature_ok=true;
 cudaMemset(X.p,0,(size_t)L*n*sizeof(double));
 cudaDeviceSynchronize();auto begin=std::chrono::steady_clock::now();
 if(shared){
  copy(R.p,b);for(int l=0;l<L;++l)copy(P.p+(size_t)l*n,b);
  double rr=dot(R.p,R.p),aprev=1,bprev=0;
  std::vector<double> z(L,1),zp(L,1),zn(L,1),alphas(L),betas(L);
  for(int k=0;k<limit && std::sqrt(rr)>tolerance*norm;++k){
   op(P.p,A.p,shifts[0]);++calls;double pap=dot(P.p,A.p);
   if(!(pap>0)){curvature_ok=false;break;}
   double alpha=rr/pap;axpy(X.p,alpha,P.p);axpy(R.p,-alpha,A.p);
   double rn=dot(R.p,R.p),beta=rn/rr;
   for(int l=1;l<L;++l){
    double den=alpha*bprev*(zp[l]-z[l])+zp[l]*aprev*(1+(shifts[l]-shifts[0])*alpha);
    zn[l]=z[l]*zp[l]*aprev/den;
    alphas[l]=alpha*zn[l]/z[l];betas[l]=beta*(zn[l]/z[l])*(zn[l]/z[l]);
    axpy(X.p+(size_t)l*n,alphas[l],P.p+(size_t)l*n);
    scale(P.p+(size_t)l*n,betas[l]);axpy(P.p+(size_t)l*n,zn[l],R.p);
    zp[l]=z[l];z[l]=zn[l];
   }
   scale(P.p,beta);axpy(P.p,1.,R.p);aprev=alpha;bprev=beta;rr=rn;
  }
 }else{
  for(int l=0;l<L;++l){
   double* x=X.p+(size_t)l*n;copy(R.p,b);copy(P.p,b);double rr=dot(R.p,R.p);
   for(int k=0;k<limit && std::sqrt(rr)>tolerance*norm;++k){
    op(P.p,A.p,shifts[l]);++calls;double pap=dot(P.p,A.p);
    if(!(pap>0)){curvature_ok=false;break;}
    double alpha=rr/pap;axpy(x,alpha,P.p);axpy(R.p,-alpha,A.p);
    double rn=dot(R.p,R.p),beta=rn/rr;scale(P.p,beta);axpy(P.p,1.,R.p);rr=rn;
   }
  }
 }
 cudaDeviceSynchronize();double elapsed=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
 Result result{elapsed,calls,{},std::vector<double>((size_t)L*n),curvature_ok};
 // True residual checks deliberately outside solver timing and matvec count.
 for(int l=0;l<L;++l){op(X.p+(size_t)l*n,A.p,shifts[l]);axpy(A.p,-1.,b);result.residuals.push_back(std::sqrt(dot(A.p,A.p))/std::max(norm,1e-300));}
 cudaMemcpy(result.solution.data(),X.p,(size_t)L*n*sizeof(double),cudaMemcpyDeviceToHost);
 return result;
}
template<class Apply>
void Run(cublasHandle_t h,int n,const double* b,const std::vector<double>& shifts,Apply apply){
 Buffer scratch(n);apply(b,scratch.p);cudaDeviceSynchronize();
 for(double tol: {1e-4,1e-6})for(int rep=1;rep<=3;++rep){
  Result multi,independent;
  if(rep%2){multi=Solve(h,n,b,shifts,apply,true,tol,2048);independent=Solve(h,n,b,shifts,apply,false,tol,2048);}
  else{independent=Solve(h,n,b,shifts,apply,false,tol,2048);multi=Solve(h,n,b,shifts,apply,true,tol,2048);}
  for(int mode=0;mode<2;++mode){const auto& r=mode?independent:multi;
   std::printf("KRYLOV_AUDIT method=%s rep=%d tol=%.9g seconds=%.9f matvecs=%d curvature_ok=%d residuals=",mode?"independent":"shared",rep,tol,r.seconds,r.matvecs,(int)r.curvature_ok);
   for(size_t l=0;l<shifts.size();++l)std::printf("%s%.17g",l?",":"",r.residuals[l]);
   std::printf("\n");
  }
  std::printf("KRYLOV_DIFFERENCE rep=%d tol=%.9g relative_solution=",rep,tol);
  for(size_t l=0;l<shifts.size();++l){long double error=0,ref=0;
   for(int j=0;j<n;++j){size_t i=l*n+j;double d=multi.solution[i]-independent.solution[i];error+=(long double)d*d;ref+=(long double)independent.solution[i]*independent.solution[i];}
   std::printf("%s%.17g",l?",":"",std::sqrt((double)(error/std::max(ref,1e-300L))));
  }std::printf("\n");
 }
}
} // namespace prism_audit
