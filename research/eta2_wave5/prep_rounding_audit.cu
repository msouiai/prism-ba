#include <cublas_v2.h>
#include <cuda_runtime.h>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>

using Scalar=double;
#define CK(x) do{auto e=(x);if(e!=cudaSuccess){std::fprintf(stderr,"CUDA %s:%d %s\n",__FILE__,__LINE__,cudaGetErrorString(e));std::exit(2);}}while(0)

__device__ __forceinline__ void MFGivens(Scalar* R,Scalar* v){
  const int ix[3][3]={{0,1,2},{-1,3,4},{-1,-1,5}};
  for(int j=0;j<3;++j){Scalar vj=v[j];if(vj==0.0)continue;Scalar rjj=R[ix[j][j]],rr=hypot(rjj,vj);if(rr==0.0)continue;Scalar cs=rjj/rr,sn=vj/rr;R[ix[j][j]]=rr;for(int k=j+1;k<3;++k){Scalar t1=R[ix[j][k]],t2=v[k];R[ix[j][k]]=cs*t1+sn*t2;v[k]=-sn*t1+cs*t2;}v[j]=0.0;}
}
__device__ __forceinline__ void MFVinv(const Scalar* R,const Scalar* t,Scalar* u){Scalar y0=t[0]/R[0],y1=(t[1]-R[1]*y0)/R[3],y2=(t[2]-R[2]*y0-R[4]*y1)/R[5];u[2]=y2/R[5];u[1]=(y1-R[4]*u[2])/R[3];u[0]=(y0-R[1]*u[1]-R[2]*u[2])/R[0];}
__global__ void SepFactor(const Scalar*C,const Scalar*R0,Scalar tau,int n,Scalar*R,int*ok){int p=blockIdx.x*blockDim.x+threadIdx.x;if(p>=n)return;Scalar cd[3]={C[3*p],C[3*p+1],C[3*p+2]},tr=cd[0]+cd[1]+cd[2],fl=tau*tr/3.;if(!(fl>0))fl=1e-32;Scalar qR[6];for(int i=0;i<6;++i)qR[i]=R0[6*p+i];for(int i=0;i<3;++i){Scalar q=tau*cd[i];if(!(q>1e-3*fl))q=1e-3*fl;Scalar v[3]={};v[i]=sqrt(q);MFGivens(qR,v);}ok[p]=qR[0]>0&&qR[3]>0&&qR[5]>0;for(int i=0;i<6;++i)R[6*p+i]=qR[i];}
__global__ void SepSolve(const Scalar*R,const Scalar*b,int n,Scalar*u){int p=blockIdx.x*blockDim.x+threadIdx.x;if(p>=n)return;const Scalar*q=R+6*p;if(!(q[0]>0&&q[3]>0&&q[5]>0)){u[3*p]=u[3*p+1]=u[3*p+2]=0;return;}Scalar t[3]={b[3*p],b[3*p+1],b[3*p+2]},x[3];MFVinv(q,t,x);u[3*p]=x[0];u[3*p+1]=x[1];u[3*p+2]=x[2];}
__global__ void FusedFactor(const Scalar*C,const Scalar*R0,const Scalar*b,Scalar tau,int n,Scalar*R,int*ok,Scalar*u){int p=blockIdx.x*blockDim.x+threadIdx.x;if(p>=n)return;Scalar cd[3]={C[3*p],C[3*p+1],C[3*p+2]},tr=cd[0]+cd[1]+cd[2],fl=tau*tr/3.;if(!(fl>0))fl=1e-32;Scalar qR[6];for(int i=0;i<6;++i)qR[i]=R0[6*p+i];for(int i=0;i<3;++i){Scalar q=tau*cd[i];if(!(q>1e-3*fl))q=1e-3*fl;Scalar v[3]={};v[i]=sqrt(q);MFGivens(qR,v);}bool valid=qR[0]>0&&qR[3]>0&&qR[5]>0;ok[p]=valid;for(int i=0;i<6;++i)R[6*p+i]=qR[i];if(!valid){u[3*p]=u[3*p+1]=u[3*p+2]=0;return;}Scalar t[3]={b[3*p],b[3*p+1],b[3*p+2]},x[3];MFVinv(qR,t,x);u[3*p]=x[0];u[3*p+1]=x[1];u[3*p+2]=x[2];}
__global__ void SepDiag(const Scalar*H,int n,Scalar*d){int c=blockIdx.x*blockDim.x+threadIdx.x;if(c>=n)return;for(int i=0;i<9;++i)d[9*c+i]+=H[81ul*c+9*i+i];}
__global__ void SepEquil(const Scalar*d,int n,Scalar*E){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n){Scalar x=d[i];E[i]=x>0?1./sqrt(x):1.;}}
__global__ void FusedEquil(const Scalar*H,int n,Scalar*E){int q=blockIdx.x*blockDim.x+threadIdx.x;if(q>=9*n)return;int c=q/9,i=q-9*c;Scalar x=H[81ul*c+9*i+i];E[q]=x>0?1./sqrt(x):1.;}
__global__ void Scale(Scalar*x,const Scalar*E,int n){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)x[i]*=E[i];}
__global__ void FusedRhs(const Scalar*b,const Scalar*c,const Scalar*E,int n,Scalar*x){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)x[i]=(b[i]-c[i])*E[i];}
template<class T> T* dev(size_t n){T*p=nullptr;CK(cudaMalloc(reinterpret_cast<void**>(&p),n*sizeof(T)));return p;}
template<class T> bool same(T*a,T*b,size_t n){std::vector<T>x(n),y(n);CK(cudaMemcpy(x.data(),a,n*sizeof(T),cudaMemcpyDeviceToHost));CK(cudaMemcpy(y.data(),b,n*sizeof(T),cudaMemcpyDeviceToHost));return std::memcmp(x.data(),y.data(),n*sizeof(T))==0;}
int main(){const int np=100003,nc=10007,n=9*nc;std::mt19937_64 g(12092026);std::uniform_real_distribution<double>u(-1,1),pos(.1,3);std::vector<double>C(3ul*np),R0(6ul*np),b(3ul*np),H(81ul*nc),bc(n),co(n);for(auto&x:C)x=pos(g);for(int p=0;p<np;++p){R0[6*p]=pos(g);R0[6*p+1]=u(g);R0[6*p+2]=u(g);R0[6*p+3]=pos(g);R0[6*p+4]=u(g);R0[6*p+5]=pos(g);}for(auto&x:b)x=u(g);for(auto&x:H)x=u(g);for(int c=0;c<nc;++c)for(int i=0;i<9;++i)H[81ul*c+9*i+i]=pos(g);for(auto&x:bc)x=u(g);for(auto&x:co)x=u(g);auto cp=dev<double>(C.size());auto r0=dev<double>(R0.size());auto bp=dev<double>(b.size());auto rs=dev<double>(R0.size());auto rf=dev<double>(R0.size());auto us=dev<double>(b.size());auto uf=dev<double>(b.size());auto os=dev<int>(np);auto of=dev<int>(np);CK(cudaMemcpy(cp,C.data(),C.size()*8,cudaMemcpyHostToDevice));CK(cudaMemcpy(r0,R0.data(),R0.size()*8,cudaMemcpyHostToDevice));CK(cudaMemcpy(bp,b.data(),b.size()*8,cudaMemcpyHostToDevice));SepFactor<<<(np+255)/256,256>>>(cp,r0,.037,np,rs,os);SepSolve<<<(np+255)/256,256>>>(rs,bp,np,us);FusedFactor<<<(np+255)/256,256>>>(cp,r0,bp,.037,np,rf,of,uf);CK(cudaDeviceSynchronize());bool factor=same(rs,rf,R0.size())&&same(us,uf,b.size())&&same(os,of,np);auto hd=dev<double>(H.size());auto ds=dev<double>(n);auto es=dev<double>(n);auto ef=dev<double>(n);CK(cudaMemcpy(hd,H.data(),H.size()*8,cudaMemcpyHostToDevice));CK(cudaMemset(ds,0,n*8));SepDiag<<<(nc+255)/256,256>>>(hd,nc,ds);SepEquil<<<(n+255)/256,256>>>(ds,n,es);FusedEquil<<<(n+255)/256,256>>>(hd,nc,ef);CK(cudaDeviceSynchronize());bool equil=same(es,ef,n);auto bd=dev<double>(n);auto cd=dev<double>(n);auto xs=dev<double>(n);auto xf=dev<double>(n);CK(cudaMemcpy(bd,bc.data(),n*8,cudaMemcpyHostToDevice));CK(cudaMemcpy(cd,co.data(),n*8,cudaMemcpyHostToDevice));CK(cudaMemcpy(xs,bd,n*8,cudaMemcpyDeviceToDevice));cublasHandle_t h;cublasCreate(&h);double m=-1;cublasDaxpy(h,n,&m,cd,1,xs,1);Scale<<<(n+255)/256,256>>>(xs,es,n);FusedRhs<<<(n+255)/256,256>>>(bd,cd,es,n,xf);CK(cudaDeviceSynchronize());bool rhs=same(xs,xf,n);std::printf("factor_solve_bitwise=%d equil_bitwise=%d rhs_axpy_scale_bitwise=%d\n",factor,equil,rhs);return factor&&equil&&rhs?0:1;}
