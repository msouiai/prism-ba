#pragma once
// CLI-only diagnostic: same fixed operator/RHS, narrow+expansion comparison.
namespace prism_fixed {
using prism_recycle::Check;
struct Buffer {
 double* p=nullptr;
 explicit Buffer(size_t n){Check(cudaMalloc((void**)&p,n*sizeof(double)));}
 ~Buffer(){cudaFree(p);} Buffer(const Buffer&)=delete;
};
struct Outcome {int steps=0;bool curvature=true;double worst=0,verify=0;};
template<class Apply>
Outcome CG(cublasHandle_t h,int n,const double*b,const std::vector<double>& shifts,
 Apply apply,double tolerance,int limit,prism_recycle::CgCapture* capture,
 double& capture_seconds,bool certify){
 const int L=shifts.size();Buffer X((size_t)L*n),P((size_t)L*n),R(n),A(n);
 auto copy=[&](double*out,const double*in){Check(cudaMemcpy(out,in,n*sizeof(double),cudaMemcpyDeviceToDevice));};
 auto dot=[&](const double*a,const double*b){double d;Check(cublasDdot(h,n,a,1,b,1,&d));return d;};
 auto axpy=[&](double*y,double v,const double*x){Check(cublasDaxpy(h,n,&v,x,1,y,1));};
 auto scale=[&](double*y,double v){Check(cublasDscal(h,n,&v,y,1));};
 const double norm=std::sqrt(dot(b,b));Outcome out;
 Check(cudaMemset(X.p,0,(size_t)L*n*sizeof(double)));copy(R.p,b);
 for(int l=0;l<L;++l)copy(P.p+(size_t)l*n,b);
 double rr=dot(R.p,R.p),aprev=1,bprev=0;
 std::vector<double> z(L,1),zp(L,1),zn(L,1);
 if(capture)capture->Reset(shifts[0]);
 for(int k=0;k<limit && std::sqrt(rr)>tolerance*norm;++k){
  apply(P.p,A.p);axpy(A.p,shifts[0],P.p);
  double pap=dot(P.p,A.p),pp=dot(P.p,P.p);
  if(!(pap>1e-14*pp)){out.curvature=false;break;}
  if(capture){auto t=std::chrono::steady_clock::now();capture->Append(P.p,A.p);capture_seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-t).count();}
  double alpha=rr/pap;axpy(X.p,alpha,P.p);axpy(R.p,-alpha,A.p);
  double rn=dot(R.p,R.p),beta=rn/rr;
  for(int l=1;l<L;++l){
   double den=alpha*bprev*(zp[l]-z[l])+zp[l]*aprev*(1+(shifts[l]-shifts[0])*alpha);
   zn[l]=den!=0?z[l]*zp[l]*aprev/den:0;
   if(!std::isfinite(zn[l]))zn[l]=0;
   double al=alpha*zn[l]/z[l],be=beta*(zn[l]/z[l])*(zn[l]/z[l]);
   axpy(X.p+(size_t)l*n,al,P.p+(size_t)l*n);
   scale(P.p+(size_t)l*n,be);axpy(P.p+(size_t)l*n,zn[l],R.p);
   zp[l]=z[l];z[l]=zn[l];
  }
  scale(P.p,beta);axpy(P.p,1.,R.p);rr=rn;aprev=alpha;bprev=beta;out.steps=k+1;
  if(!std::isfinite(rr)){out.curvature=false;break;}
 }
 if(certify){
  Check(cudaDeviceSynchronize());auto begin=std::chrono::steady_clock::now();
  for(int l=0;l<L;++l){apply(X.p+(size_t)l*n,A.p);axpy(A.p,shifts[l],X.p+(size_t)l*n);axpy(A.p,-1.,b);
   double relative=std::sqrt(dot(A.p,A.p))/std::max(norm,1e-300);
   out.worst=std::isfinite(relative)?std::max(out.worst,relative):std::numeric_limits<double>::infinity();}
  Check(cudaDeviceSynchronize());out.verify=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
 }
 return out;
}
inline void Save(const std::string& path,const void* device,size_t bytes){
 FILE* f=std::fopen(path.c_str(),"wb");if(!f)throw std::runtime_error("cannot open fixed-system capture");
 std::vector<unsigned char> block(std::min(bytes,(size_t)8*1024*1024));
 for(size_t offset=0;offset<bytes;offset+=block.size()){
  size_t count=std::min(block.size(),bytes-offset);
  Check(cudaMemcpy(block.data(),static_cast<const unsigned char*>(device)+offset,count,cudaMemcpyDeviceToHost));
  if(std::fwrite(block.data(),1,count,f)!=count)throw std::runtime_error("fixed-system capture write failed");
 }
 if(std::fclose(f))throw std::runtime_error("fixed-system capture close failed");
}
struct Collector {
 int counts[3]={0,0,0};
 int desired[3]={1,2,1};
 bool on=getenv("OCA_REUSE_FIXED_STUDY")!=nullptr;
 static int Bucket(int depth){return depth<=10?0:depth<=32?1:2;}
 bool Want(int depth){return on && counts[Bucket(depth)]<desired[Bucket(depth)];}
 bool Done()const{return counts[0]>=desired[0]&&counts[1]>=desired[1]&&counts[2]>=desired[2];}
};
template<class Apply>
void Run(cublasHandle_t h,int n,const double*b,const std::vector<double>& shifts,
 double center,double tolerance,int limit,int outer,int source_depth,int snapshot,
 const std::vector<int>& checkpoints,Apply apply){
 // Rotate methods and reverse the middle repeat. One untimed warmup for the
 // code paths prevents the first reported method paying lazy library setup.
 for(int rep=0;rep<=3;++rep){
  for(int order=0;order<3;++order){
   int method=(order+rep)%3;if(rep==2)method=(2-order+rep)%3;
   int calls=0;auto op=[&](const double*v,double*w){apply(v,w);++calls;};
   std::unique_ptr<prism_recycle::CgCapture> capture;
   std::unique_ptr<prism_recycle::Basis> basis;
   Check(cudaDeviceSynchronize());auto begin=std::chrono::steady_clock::now();
   // Charge capture allocations in full for every fixed-system trial; the
   // production solver amortizes them across nonlinear iterations.
   if(method){capture.reset(new prism_recycle::CgCapture(n,64));basis.reset(new prism_recycle::Basis(n,64));}
   double capture_seconds=0;
   auto narrow=CG(h,n,b,{center},op,tolerance,limit,capture.get(),capture_seconds,false);
   int decision=-1;if(method==2){PrismSelectiveReuse policy;decision=policy.Decide(capture->m,shifts.size(),64);}
   const bool reuse=method==1 || (method==2 && decision==PrismSelectiveReuse::Use);
   bool valid=false,fallback=false;int depth=0,wide_steps=0;double worst=0,diagnostic_verify=0;
   if(reuse && capture->m>0){
    capture->Import(h,b,*basis);Buffer x(n);
    std::vector<int> depths={capture->m};for(int d:{8,16,32,64})if(d>capture->m && d<=limit)depths.push_back(d);
    for(int target:depths){
     basis->Grow(h,op,target);valid=basis->m>0;worst=0;
     for(double shift:shifts){double residual,prediction;
      bool finite=basis->Solve(h,op,b,shift,x.p,residual,prediction);
      worst=std::isfinite(residual)?std::max(worst,residual):std::numeric_limits<double>::infinity();
      valid=valid&&finite&&residual<=tolerance;}
     if(valid||basis->exhausted)break;
    }
    depth=basis->m;
    if(valid){
     std::vector<int> scoring;for(int ck:checkpoints)if(ck<=depth)scoring.push_back(ck);
     if(scoring.empty()||scoring.back()!=depth)scoring.push_back(depth);
     for(int ck:scoring){basis->m=ck;for(double shift:shifts){double residual,prediction;
      if(!basis->Solve(h,op,b,shift,x.p,residual,prediction,false))throw std::runtime_error("fixed-study invalid prefix");}}
     basis->m=depth;
    }
   }
   if(!valid){
    fallback=reuse;
    auto wide=CG(h,n,b,shifts,op,tolerance,limit,nullptr,capture_seconds,true);
    wide_steps=wide.steps;worst=wide.worst;valid=wide.curvature&&worst<=tolerance*(1+1e-8);
    // Ordinary production CG has no true-residual certification cost. Also
    // remove this diagnostic-only cost on the fallback/skip paths.
    diagnostic_verify=wide.verify;
   }
   basis.reset();capture.reset();Check(cudaDeviceSynchronize());
   double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
   if(rep)std::printf("FIXED_REUSE snapshot=%d outer=%d source_depth=%d bucket=%d rep=%d method=%d narrow=%d projection=%d wide=%d decision=%d fallback=%d calls=%d seconds=%.9f diagnostic_verify=%.9f charged=%.9f capture=%.9f residual=%.17g tolerance=%.17g valid=%d\n",
    snapshot,outer,source_depth,Collector::Bucket(source_depth),rep,method,narrow.steps,depth,wide_steps,decision,(int)fallback,calls,seconds,diagnostic_verify,seconds-diagnostic_verify,capture_seconds,worst,tolerance,(int)valid);
  }
 }
 std::fflush(stdout);
}
} // namespace prism_fixed
