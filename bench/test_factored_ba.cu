#include <cuda_runtime.h>
#include <cmath>
#include <cstdio>
#include <vector>
#include <random>
#include <algorithm>
using Scalar=double;
#define BalResidualGrad12 ReferenceGrad
#include "bal_grad12_generated.cuh"
#undef BalResidualGrad12
#include "bal_factored_grad.cuh"
struct Sample{double R[9],t[3],X[3],f,k1,k2,ox,oy,d[12],mask;};
__global__ void check(int n,const Sample*s,double*out){int k=blockIdx.x*blockDim.x+threadIdx.x;if(k>=n)return;const auto&a=s[k];double gx[12],gy[12],fx[12],fy[12],rx,ry,rrx,rry;
#define ARGS a.R[0],a.R[1],a.R[2],a.R[3],a.R[4],a.R[5],a.R[6],a.R[7],a.R[8],a.t[0],a.t[1],a.t[2],a.X[0],a.X[1],a.X[2],a.f,a.k1,a.k2,a.ox,a.oy
 ReferenceGrad(ARGS,gx,gy,&rx,&ry);BalResidualGrad12(ARGS,fx,fy,&rrx,&rry);double norm=0,err=0,jx=0,jy=0,scale=0;
 for(int i=0;i<12;++i){norm+=gx[i]*gx[i]+gy[i]*gy[i];err+=(gx[i]-fx[i])*(gx[i]-fx[i])+(gy[i]-fy[i])*(gy[i]-fy[i]);double d=a.d[i]*(i==8?a.mask:1);jx+=gx[i]*d;jy+=gy[i]*d;scale+=fabs(gx[i]*d)+fabs(gy[i]*d);}
 double dx,dy,jrx,jry;BalDirectional12(a.R,a.t,a.X,a.f,a.k1,a.k2,a.ox,a.oy,a.d,a.d+9,a.mask,jrx,jry,dx,dy);
 out[5*k]=sqrt(err/fmax(norm,1e-300));out[5*k+1]=(fabs(dx-jx)+fabs(dy-jy))/fmax(scale,1e-300);out[5*k+2]=fmax(fabs(rrx-rx),fabs(rry-ry))/fmax(1.,fmax(fabs(rx),fabs(ry)));out[5*k+3]=dx;out[5*k+4]=dy;
}
void value(const Sample&a,double eps,double&x,double&y){
 double w[3]={eps*a.d[0],eps*a.d[1],eps*a.d[2]},theta=sqrt(w[0]*w[0]+w[1]*w[1]+w[2]*w[2]);double A=theta?sin(theta)/theta:1,B=theta?(1-cos(theta))/(theta*theta):.5;
 double X[3],q[3]={};for(int j=0;j<3;++j)X[j]=a.X[j]+eps*a.d[9+j];for(int i=0;i<3;++i)for(int j=0;j<3;++j)q[i]+=a.R[3*i+j]*X[j];
 double cross[3]={w[1]*q[2]-w[2]*q[1],w[2]*q[0]-w[0]*q[2],w[0]*q[1]-w[1]*q[0]},cross2[3]={w[1]*cross[2]-w[2]*cross[1],w[2]*cross[0]-w[0]*cross[2],w[0]*cross[1]-w[1]*cross[0]};
 for(int i=0;i<3;++i)q[i]+=A*cross[i]+B*cross2[i]+a.t[i]+eps*a.d[3+i];double u=-q[0]/q[2],v=-q[1]/q[2],s=u*u+v*v,D=1+(a.k1+eps*a.d[7])*s+(a.k2+eps*a.mask*a.d[8])*s*s;x=(a.f+eps*a.d[6])*D*u-a.ox;y=(a.f+eps*a.d[6])*D*v-a.oy;
}
int main(){const int n=100000;std::mt19937_64 rng(9092026);std::uniform_real_distribution<double>u(-1,1);std::vector<Sample>s(n);
 for(auto&a:s){double q[4],norm=0;for(auto&v:q){v=u(rng);norm+=v*v;}for(auto&v:q)v/=sqrt(norm);double w=q[0],x=q[1],y=q[2],z=q[3];double R[9]={1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)};std::copy(R,R+9,a.R);for(int i=0;i<3;++i){a.X[i]=5*u(rng);a.t[i]=u(rng);}a.t[2]=(rng()%2?1:-1)*(.1+10*(1+u(rng)))-(R[6]*a.X[0]+R[7]*a.X[1]+R[8]*a.X[2]);a.f=1200+800*u(rng);a.k1=.1*u(rng);a.k2=.001*u(rng);a.ox=100*u(rng);a.oy=100*u(rng);for(int i=0;i<12;++i)a.d[i]=u(rng)*(i<3?.01:i==6?10:i==7||i==8?.001:.1);a.mask=(rng()%2)?1:0;}
 Sample*d;double*o;cudaMalloc(&d,n*sizeof(Sample));cudaMalloc(&o,n*5*8);cudaMemcpy(d,s.data(),n*sizeof(Sample),cudaMemcpyHostToDevice);check<<<(n+255)/256,256>>>(n,d,o);if(cudaDeviceSynchronize()!=cudaSuccess)return 2;std::vector<double>r(n*5);cudaMemcpy(r.data(),o,n*5*8,cudaMemcpyDeviceToHost);double g=0,j=0,res=0,fd=0;
 for(int i=0;i<n;++i){for(int k=0;k<5;++k)if(!std::isfinite(r[5*i+k]))return 3;g=std::max(g,r[5*i]);j=std::max(j,r[5*i+1]);res=std::max(res,r[5*i+2]);if(i<500){double xp,yp,xm,ym;value(s[i],1e-5,xp,yp);value(s[i],-1e-5,xm,ym);fd=std::max(fd,(fabs((xp-xm)/2e-5-r[5*i+3])+fabs((yp-ym)/2e-5-r[5*i+4]))/std::max(1.,fabs(r[5*i+3])+fabs(r[5*i+4])));}}
 printf("{\"samples\":%d,\"finite_differences\":500,\"max_gradient_relative\":%.17g,\"max_directional_scaled\":%.17g,\"max_residual_relative\":%.17g,\"max_finite_difference_relative\":%.17g}\n",n,g,j,res,fd);return g<1e-12&&j<1e-12&&res<1e-9&&fd<5e-5?0:1;
}
