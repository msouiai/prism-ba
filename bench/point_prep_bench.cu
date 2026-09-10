#include <cuda_runtime.h>
#include <cstdio>
#include <vector>
#include <string>
#include <cmath>
#include <algorithm>
#include <stdexcept>
using Scalar=double;
#define CK(x) do{auto e=(x);if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}while(0)
#include "reference.cuh"
#include "point_prep_candidate.cuh"
template<class T>std::vector<T> read(std::string path,size_t n){std::vector<T>v(n);FILE*f=fopen(path.c_str(),"rb");if(!f||fread(v.data(),sizeof(T),n,f)!=n)throw std::runtime_error("read "+path);fclose(f);return v;}
template<class T>T* up(const std::vector<T>&v){T*p;CK(cudaMalloc(&p,v.size()*sizeof(T)));CK(cudaMemcpy(p,v.data(),v.size()*sizeof(T),cudaMemcpyHostToDevice));return p;}
template<class T>T* alloc(size_t n){T*p;CK(cudaMalloc(&p,n*sizeof(T)));return p;}
template<class T>std::vector<T> down(T*p,size_t n){std::vector<T>v(n);CK(cudaMemcpy(v.data(),p,n*sizeof(T),cudaMemcpyDeviceToHost));return v;}
template<class F>float timing(F f){std::vector<float>v;cudaEvent_t a,b;CK(cudaEventCreate(&a));CK(cudaEventCreate(&b));f();for(int i=0;i<7;++i){CK(cudaEventRecord(a));f();CK(cudaEventRecord(b));CK(cudaEventSynchronize(b));float ms;CK(cudaEventElapsedTime(&ms,a,b));v.push_back(ms);}std::sort(v.begin(),v.end());cudaEventDestroy(a);cudaEventDestroy(b);return v[3];}
void diff(const char*name,const std::vector<double>&a,const std::vector<double>&b,double tol){long double d=0,s=0;double mx=0;for(size_t i=0;i<a.size();++i){if(!std::isfinite(a[i])||!std::isfinite(b[i]))throw std::runtime_error("nonfinite");long double e=a[i]-b[i];d+=e*e;s+=(long double)a[i]*a[i];mx=std::max(mx,std::abs(a[i]-b[i])/std::max(1.,std::abs(a[i])));}double rel=sqrt(d/std::max(s,1e-300L));printf("CHECK %s relative=%.17g max_scaled=%.17g\n",name,rel,mx);if(!(rel<tol))throw std::runtime_error("accuracy");}
__global__ void solve(const double*R,const double*b,int n,double*x){int p=blockIdx.x*blockDim.x+threadIdx.x;if(p<n)MFVinv(R+6ul*p,b+3ul*p,x+3ul*p);}
int main(int argc,char**argv){bool fusion=argc>1&&std::string(argv[1])=="fusion";
 if(!fusion){std::string dir="/workspace/prism-tr-point-prep/capture-v2/";int nc,np,no;double tau;FILE*f=fopen((dir+"dims").c_str(),"r");if(!f||fscanf(f,"%d %d %d %lf",&nc,&np,&no,&tau)!=4)throw std::runtime_error("dims");fclose(f);
 auto bo=up(read<float>(dir+"Bo",6ul*no));auto po=up(read<int>(dir+"poff",np+1ul)),pl=up(read<int>(dir+"plist",no));auto cd=up(read<double>(dir+"Cdiag",3ul*np)),bp=up(read<double>(dir+"bp",3ul*np));auto ref=alloc<double>(6ul*np),cand=alloc<double>(6ul*np),rd=alloc<double>(6ul*np),cdamp=alloc<double>(6ul*np);auto flag=alloc<int>(np),ok=alloc<int>(np);int grid=(np+255)/256;
 float qr=timing([&](){MFPointFactorObs<float><<<grid,256>>>(bo,po,pl,np,ref);});float chol=timing([&](){MFPointFactorGuarded<<<grid,256>>>(bo,po,pl,np,cand,flag);});auto hf=down(flag,np);long long fallback=0;for(auto i:hf)fallback+=i;printf("TIME qr_ms=%.9g guarded_ms=%.9g fallback=%lld points=%d tau=%.17g\n",qr,chol,fallback,np,tau);
 diff("undamped_R",down(ref,6ul*np),down(cand,6ul*np),1e-8);
 auto x=alloc<double>(3ul*np),y=alloc<double>(3ul*np);
 for(double damping:{tau,.1,1e-4,1e-8}){
 printf("DAMPING %.17g\n",damping);
 MFPointFactorTau<<<grid,256>>>(cd,ref,damping,np,rd,ok);MFPointFactorTau<<<grid,256>>>(cd,cand,damping,np,cdamp,ok);diff("damped_R",down(rd,6ul*np),down(cdamp,6ul*np),1e-8);
 solve<<<grid,256>>>(rd,bp,np,x);solve<<<grid,256>>>(cdamp,bp,np,y);diff("damped_inverse_actual_rhs",down(x,3ul*np),down(y,3ul*np),1e-8);
 for(int axis=0;axis<3;++axis){std::vector<double> unit(3ul*np);for(int p=0;p<np;++p)unit[3ul*p+axis]=1;auto rhs=up(unit);solve<<<grid,256>>>(rd,rhs,np,x);solve<<<grid,256>>>(cdamp,rhs,np,y);diff("inverse_column",down(x,3ul*np),down(y,3ul*np),1e-8);cudaFree(rhs);}
 }

 }else{std::string dir="/workspace/prism-tr-cg-stop/capture/";int cd,nc,np,no;double sig,rad,eta;FILE*f=fopen((dir+"dimensions.txt").c_str(),"r");if(!f||fscanf(f,"%d %d %d %d %lf %lf %lf",&cd,&nc,&np,&no,&sig,&rad,&eta)!=7)throw std::runtime_error("dims");fclose(f);
 auto W=up(read<float>(dir+"W",27ul*no));auto cam=up(read<int>(dir+"cams",no)),pt=up(read<int>(dir+"points",no));auto R=up(read<double>(dir+"R",6ul*np));std::vector<double>h(3ul*np);for(size_t i=0;i<h.size();++i)h[i]=sin(i*.13);auto ub=up(h);auto rhs=alloc<double>(9ul*nc),diag=alloc<double>(9ul*nc);int grid=(no+255)/256;
 auto run=[&](bool fuse){CK(cudaMemset(rhs,0,9ul*nc*8));CK(cudaMemset(diag,0,9ul*nc*8));if(fuse)MFRhsDiagFused<<<grid,256>>>(W,cam,pt,R,ub,no,rhs,diag);else{MFRhsPrime<9,float><<<grid,256>>>(W,cam,pt,ub,no,rhs);MFDiagK<9,float,true><<<grid,256>>>(W,pt,cam,R,no,diag);}};
 run(false);auto hr=down(rhs,9ul*nc),hd=down(diag,9ul*nc);run(true);diff("fused_rhs",hr,down(rhs,9ul*nc),1e-10);diff("fused_diagonal",hd,down(diag,9ul*nc),1e-10);
 for(int rep=0;rep<3;++rep){float a,b;if(rep%2){b=timing([&](){run(true);});a=timing([&](){run(false);});}else{a=timing([&](){run(false);});b=timing([&](){run(true);});}printf("FUSION rep=%d separate_ms=%.9g fused_ms=%.9g\n",rep,a,b);}
 }return 0;}
