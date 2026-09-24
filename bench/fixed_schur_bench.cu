#include <cuda_runtime.h>
#include <cublas_v2.h>
#include <vector>
#include <cstdio>
#include <string>
#include <cmath>
#include <algorithm>
#include <stdexcept>
using Scalar=double;
#define CK(a) do{cudaError_t e=(a);if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}while(0)
#include "reference_kernels.cuh"
#include "point_owned_schur.cuh"
template<class T>std::vector<T> read(const std::string&name,size_t n){std::vector<T>a(n);FILE*f=fopen(name.c_str(),"rb");if(!f||fread(a.data(),sizeof(T),n,f)!=n)throw std::runtime_error("capture read");fclose(f);return a;}
template<class T>T* upload(const std::vector<T>&a){T*p;CK(cudaMalloc(&p,a.size()*sizeof(T)));CK(cudaMemcpy(p,a.data(),a.size()*sizeof(T),cudaMemcpyHostToDevice));return p;}
template<class T>T* load(const std::string&name,size_t n){return upload(read<T>(name,n));}
__global__ void scale(int n,double*x,const double*E){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)x[i]*=E[i];}
int main(int argc,char**argv){
 const bool profile=argc>1&&std::string(argv[1])=="--profile"; const bool staged=argc>1&&std::string(argv[1])=="--staged"; const bool tune=argc>1&&std::string(argv[1])=="--tune";std::string dir="/workspace/prism-tr-cg-stop/capture/";
 FILE*f=fopen((dir+"dimensions.txt").c_str(),"r");int cd,nc,np,no;double sig,rad,eta;if(!f||fscanf(f,"%d %d %d %d %lf %lf %lf",&cd,&nc,&np,&no,&sig,&rad,&eta)!=7)throw std::runtime_error("dimensions read");fclose(f);const int n=9*nc;
 float*W=load<float>(dir+"W",27ul*no);double*U=load<double>(dir+"U",81ul*nc),*R=load<double>(dir+"R",6ul*np),*E=load<double>(dir+"E",n),*rhs=load<double>(dir+"b",n);
 auto hpt=read<int>(dir+"points",no);int*pt=upload(hpt),*cam=load<int>(dir+"cams",no),*off=load<int>(dir+"offsets",nc+1);
 std::vector<int>poff(np+1,0),slots(no);for(int p:hpt)++poff[p+1];for(int i=0;i<np;++i)poff[i+1]+=poff[i];auto cursor=poff;for(int k=0;k<no;++k)slots[cursor[hpt[k]]++]=k;int*dpoff=upload(poff),*dslots=upload(slots);
 double*products;CK(cudaMalloc(&products,3ul*no*8));double*v,*t,*u,*y,*ref;CK(cudaMalloc(&v,n*8));CK(cudaMalloc(&t,3ul*np*8));CK(cudaMalloc(&u,3ul*np*8));CK(cudaMalloc(&y,n*8));CK(cudaMalloc(&ref,n*8));cublasHandle_t h;cublasCreate(&h);double nb;cublasDnrm2(h,n,rhs,1,&nb);
 auto pass1=[&](int mode){
  if(mode>=100){
   MFPass1Local<9><<<(no+255)/256,256>>>(W,cam,v,no,products);
   if(mode==101)MFPass1Reduce<1><<<(np+255)/256,256>>>(products,dpoff,dslots,no,np,t);
   if(mode==102)MFPass1Reduce<2><<<((size_t)np*2+255)/256,256>>>(products,dpoff,dslots,no,np,t);
   if(mode==104)MFPass1Reduce<4><<<((size_t)np*4+255)/256,256>>>(products,dpoff,dslots,no,np,t);
   if(mode==116)MFPass1Reduce<16><<<((size_t)np*16+255)/256,256>>>(products,dpoff,dslots,no,np,t);
   if(mode==108)MFPass1Reduce<8><<<((size_t)np*8+255)/256,256>>>(products,dpoff,dslots,no,np,t);
   if(mode==132)MFPass1Reduce<32><<<((size_t)np*32+255)/256,256>>>(products,dpoff,dslots,no,np,t);
  }
  if(mode==0){CK(cudaMemset(t,0,3ul*np*8));MFPass1<9,float><<<(no+255)/256,256>>>(W,cam,pt,v,no,t);}
  if(mode==1)MFPass1PointOwned<9,1><<<(np+255)/256,256>>>(W,cam,dpoff,dslots,v,no,np,t);
  if(mode==8)MFPass1PointOwned<9,8><<<((size_t)np*8+255)/256,256>>>(W,cam,dpoff,dslots,v,no,np,t);
  if(mode==32)MFPass1PointOwned<9,32><<<((size_t)np*32+255)/256,256>>>(W,cam,dpoff,dslots,v,no,np,t);
 };
 auto finish=[&](){MFVinvApply<<<(np+255)/256,256>>>(R,t,np,u);MFPass2<9,float><<<nc,256>>>(W,pt,off,u,U,v,no,y);scale<<<(n+255)/256,256>>>(n,y,E);};
 for(int depth:{16,32,64,128}){
  double*x=load<double>(dir+"projected-"+std::to_string(depth)+".x",n);CK(cudaMemcpy(v,x,n*8,cudaMemcpyDeviceToDevice));scale<<<(n+255)/256,256>>>(n,v,E);pass1(0);finish();CK(cudaMemcpy(ref,y,n*8,cudaMemcpyDeviceToDevice));
  if(profile){CK(cudaDeviceSynchronize());return 0;}
  if(tune&&depth==16){
   for(int part:{0,1}){std::vector<float>times;cudaEvent_t a,b;cudaEventCreate(&a);cudaEventCreate(&b);
    for(int rep=0;rep<5;++rep){cudaEventRecord(a);
     if(part==0)MFPass1Local<9><<<(no+255)/256,256>>>(W,cam,v,no,products);
     else MFPass1Reduce<8><<<((size_t)np*8+255)/256,256>>>(products,dpoff,dslots,no,np,t);
     cudaEventRecord(b);cudaEventSynchronize(b);float ms;cudaEventElapsedTime(&ms,a,b);times.push_back(ms);
    }std::sort(times.begin(),times.end());printf("STAGE part=%d ms=%.9g\n",part,times[2]);cudaEventDestroy(a);cudaEventDestroy(b);
   }
  }
  double normref;cublasDnrm2(h,n,ref,1,&normref);
  for(int mode:(tune?std::vector<int>{0,102,104,116}:staged?std::vector<int>{0,101,108,132}:std::vector<int>{0,1,8,32})){
   pass1(mode);finish();double minus=-1;cublasDaxpy(h,n,&minus,ref,1,y,1);double err;cublasDnrm2(h,n,y,1,&err);if(!(err/nb<1e-7))throw std::runtime_error("reference operator disagreement");
   std::vector<float> times;cudaEvent_t a,b;cudaEventCreate(&a);cudaEventCreate(&b);
   for(int rep=0;rep<5;++rep){cudaEventRecord(a);pass1(mode);cudaEventRecord(b);cudaEventSynchronize(b);float ms;cudaEventElapsedTime(&ms,a,b);times.push_back(ms);}std::sort(times.begin(),times.end());cudaEventDestroy(a);cudaEventDestroy(b);
   printf("FIXED depth=%d mode=%d pass1_ms=%.9g error_over_b=%.17g error_over_Sx=%.17g\n",depth,mode,times[2],err/nb,err/std::max(normref,1e-300));fflush(stdout);
  }
  cudaFree(x);
 }
 return 0;
}
