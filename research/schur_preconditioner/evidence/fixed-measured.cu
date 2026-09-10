#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <vector>
#include <string>
#include <cstdio>
#include <cmath>
#include <algorithm>
#include <stdexcept>
#include <chrono>
using Scalar=double;
#define CK(x) do{if((x)!=cudaSuccess)throw std::runtime_error("CUDA");}while(0)
#include "reference.cuh"
#include "gram.cuh"
template<class T>T* alloc(size_t n){T*p;CK(cudaMalloc(&p,n*sizeof(T)));return p;}
template<class T>T* load(std::string s,size_t n){std::vector<T>v(n);FILE*f=fopen(s.c_str(),"rb");if(!f||fread(v.data(),sizeof(T),n,f)!=n)throw std::runtime_error("read");fclose(f);T*p=alloc<T>(n);CK(cudaMemcpy(p,v.data(),n*sizeof(T),cudaMemcpyHostToDevice));return p;}
__global__ void scaled(int n,const double*x,const double*E,double*y){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[i]=x[i]*E[i];}
__global__ void finish(int n,const double*x,const double*E,double sigma,double*y){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)y[i]=y[i]*E[i]+sigma*x[i];}
__global__ void normalize(int nc,const double*E,double sig,double*B){int c=blockIdx.x*blockDim.x+threadIdx.x;if(c<nc)for(int i=0;i<9;++i)for(int j=0;j<9;++j)B[81ul*c+9*i+j]=B[81ul*c+9*i+j]*E[9*c+i]*E[9*c+j]+(i==j?sig:0);}
int main(int argc,char**argv){if(argc!=2)return 2;std::string dir=std::string(argv[1])+"/";int cd,nc,np,no;double sig,rad,eta;FILE*f=fopen((dir+"dimensions.txt").c_str(),"r");if(!f||fscanf(f,"%d %d %d %d %lf %lf %lf",&cd,&nc,&np,&no,&sig,&rad,&eta)!=7)return 2;fclose(f);int n=9*nc,grid=(n+255)/256;
 auto W=load<float>(dir+"W",27ul*no);auto U=load<double>(dir+"U",81ul*nc),R=load<double>(dir+"R",6ul*np),E=load<double>(dir+"E",n),b=load<double>(dir+"b",n);auto cam=load<int>(dir+"cams",no),pt=load<int>(dir+"points",no),off=load<int>(dir+"offsets",nc+1);auto v=alloc<double>(n),t=alloc<double>(3ul*np),u=alloc<double>(3ul*np),x=alloc<double>(n),r=alloc<double>(n),z=alloc<double>(n),p=alloc<double>(n),ap=alloc<double>(n),temp=alloc<double>(n),B=alloc<double>(81ul*nc);auto fails=alloc<int>(1);cublasHandle_t h;cublasCreate(&h);auto dot=[&](double*a,double*c){double q;if(cublasDdot(h,n,a,1,c,1,&q)!=CUBLAS_STATUS_SUCCESS)throw std::runtime_error("dot");return q;};double nb=sqrt(dot(b,b));cudaEvent_t a,e;cudaEventCreate(&a);cudaEventCreate(&e);auto start=[&](){cudaEventRecord(a);};auto elapsed=[&](){cudaEventRecord(e);cudaEventSynchronize(e);float ms;cudaEventElapsedTime(&ms,a,e);return ms;};
 auto apply=[&](double*in,double*out){scaled<<<grid,256>>>(n,in,E,v);CK(cudaMemset(t,0,3ul*np*8));MFPass1<9,float><<<(no+255)/256,256>>>(W,cam,pt,v,no,t);MFVinvApply<<<(np+255)/256,256>>>(R,t,np,u);MFPass2<9,float><<<nc,256>>>(W,pt,off,u,U,v,no,out);finish<<<grid,256>>>(n,in,E,sig,out);};

 std::vector<double> old(81ul*nc),gram(81ul*nc);
 for(int arm=0;arm<2;++arm){CK(cudaMemset(B,0,81ul*nc*8));
 if(arm==0)MFBlockSchurCM<9,float><<<nc,32>>>(W,pt,off,R,no,B);else SchurGram<9,float><<<nc,32>>>(W,pt,off,R,no,B);
 MFBlockAddHcc<9><<<(nc+255)/256,256>>>(U,nc,B);normalize<<<(nc+255)/256,256>>>(nc,E,sig,B);
 CK(cudaMemcpy((arm?gram:old).data(),B,81ul*nc*8,cudaMemcpyDeviceToHost));}
 double diff=0,base=0,maximum=0;for(size_t i=0;i<old.size();++i){double d=gram[i]-old[i];diff+=d*d;base+=old[i]*old[i];maximum=std::max(maximum,std::abs(d));}
 double error=sqrt(diff/base);printf("BLOCK_PARITY relative_frobenius=%.17g max_abs=%.17g\n",error,maximum);
 if(!std::isfinite(error)||error>1e-10)throw std::runtime_error("Gram block parity failed");
 // Fixed operator and residual tolerance are unchanged across preconditioners.
 for(int rep=-1;rep<3;++rep)for(int arm=0;arm<3;++arm){int mode=1+(arm+std::max(rep,0))%3;start();int nf=0;if(mode){if(mode>=2){CK(cudaMemset(B,0,81ul*nc*8));if(mode==2)MFBlockSchurCM<9,float><<<nc,32>>>(W,pt,off,R,no,B);else SchurGram<9,float><<<nc,32>>>(W,pt,off,R,no,B);MFBlockAddHcc<9><<<(nc+255)/256,256>>>(U,nc,B);}else CK(cudaMemcpy(B,U,81ul*nc*8,cudaMemcpyDeviceToDevice));normalize<<<(nc+255)/256,256>>>(nc,E,sig,B);CK(cudaMemset(fails,0,4));MFBlockChol<9><<<(nc+255)/256,256>>>(B,nc,1e-10,fails);CK(cudaMemcpy(&nf,fails,4,cudaMemcpyDeviceToHost));}float setup=elapsed();
 auto pre=[&](){if(mode){MFBlockSolve<9><<<(nc+255)/256,256>>>(B,r,nc,0,temp);MFBlockSolve<9><<<(nc+255)/256,256>>>(B,temp,nc,1,z);}else CK(cudaMemcpy(z,r,n*8,cudaMemcpyDeviceToDevice));};
 for(double tol:{eta,.01}){CK(cudaMemset(x,0,n*8));CK(cudaMemcpy(r,b,n*8,cudaMemcpyDeviceToDevice));start();pre();CK(cudaMemcpy(p,z,n*8,cudaMemcpyDeviceToDevice));double rz=dot(r,z);int it=0,products=0;double rel=1;bool neg=false;
 for(;it<128;){apply(p,ap);++products;double pap=dot(p,ap);if(!(pap>0)){neg=true;break;}double alpha=rz/pap,minus=-alpha;cublasDaxpy(h,n,&alpha,p,1,x,1);cublasDaxpy(h,n,&minus,ap,1,r,1);++it;rel=sqrt(dot(r,r))/nb;
 if(rel<=tol||it==128){apply(x,ap);++products;double m=-1;cublasDscal(h,n,&m,ap,1);double one=1;cublasDaxpy(h,n,&one,b,1,ap,1);rel=sqrt(dot(ap,ap))/nb;if(rel<=tol||it==128)break;CK(cudaMemcpy(r,ap,n*8,cudaMemcpyDeviceToDevice));pre();CK(cudaMemcpy(p,z,n*8,cudaMemcpyDeviceToDevice));rz=dot(r,z);continue;}
 pre();double next=dot(r,z),beta=next/rz;cublasDscal(h,n,&beta,p,1);double one=1;cublasDaxpy(h,n,&one,z,1,p,1);rz=next;}
 float solve=elapsed();if(rep>=0)printf("FIXED rep=%d mode=%d tolerance=%.17g iterations=%d products=%d true_relative=%.17g hit=%d neg=%d setup_ms=%.9g solve_ms=%.9g total_ms=%.9g fallback_blocks=%d\n",rep,mode,tol,it,products,rel,rel<=tol,neg,setup,solve,setup+solve,nf);fflush(stdout);
 }
 }
}
