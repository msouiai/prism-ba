#pragma once
// Pure analytic primitive, usable in CPU and CUDA derivative checks.
// d0 is signed and fixed per ORIGINAL observation. No denominator clamping.
#if defined(__CUDACC__)
#define O2_HD __host__ __device__ __forceinline__
#else
#define O2_HD inline
#endif
namespace o2 {
O2_HD double Denominator(double z,double d0,double stage){
  if(stage==1.)return z;
  if(stage==0.)return d0;
  return stage*z+(1.-stage)*d0;
}
O2_HD void Projection(const double* Y,double f,double k1,double k2,
    double d0,double stage,double* pixel,double* JY=nullptr,double* JI=nullptr){
  const double iz=1./Denominator(Y[2],d0,stage);
  const double u=-Y[0]*iz,v=-Y[1]*iz,r2=u*u+v*v;
  const double h=1.+k1*r2+k2*r2*r2,hp=k1+2.*k2*r2;
  pixel[0]=f*h*u;pixel[1]=f*h*v;
  if(JY){
    const double a=f*(h+2.*u*u*hp),b=2.*f*u*v*hp,c=f*(h+2.*v*v*hp);
    JY[0]=-a*iz;JY[1]=-b*iz;JY[2]=-stage*(a*u+b*v)*iz;
    JY[3]=-b*iz;JY[4]=-c*iz;JY[5]=-stage*(b*u+c*v)*iz;
  }
  if(JI){
    JI[0]=h*u;JI[1]=f*u*r2;JI[2]=f*u*r2*r2;
    JI[3]=h*v;JI[4]=f*v*r2;JI[5]=f*v*r2*r2;
  }
}
O2_HD void ResidualGrad12(const double* R,const double* t,const double* X,
    double f,double k1,double k2,double ox,double oy,double d0,double stage,
    double* gx,double* gy,double* rx,double* ry){
  double q[3],Y[3];for(int i=0;i<3;++i){q[i]=R[3*i]*X[0]+R[3*i+1]*X[1]+R[3*i+2]*X[2];Y[i]=q[i]+t[i];}
  double pix[2],jp[6],ji[6];Projection(Y,f,k1,k2,d0,stage,pix,jp,ji);
  *rx=pix[0]-ox;*ry=pix[1]-oy;
  for(int row=0;row<2;++row){double* g=row?gy:gx;const double* a=jp+3*row;
    g[0]=q[1]*a[2]-q[2]*a[1];g[1]=q[2]*a[0]-q[0]*a[2];g[2]=q[0]*a[1]-q[1]*a[0];
    for(int j=0;j<3;++j){g[3+j]=a[j];g[6+j]=ji[3*row+j];g[9+j]=R[j]*a[0]+R[3+j]*a[1]+R[6+j]*a[2];}
  }
}
O2_HD void Directional12(const double* R,const double* t,const double* X,
    double f,double k1,double k2,double ox,double oy,const double* dc,
    const double* dp,double mask,double d0,double stage,double& rx,double& ry,double& jx,double& jy){
  double gx[12],gy[12];ResidualGrad12(R,t,X,f,k1,k2,ox,oy,d0,stage,gx,gy,&rx,&ry);
  jx=0;jy=0;for(int j=0;j<9;++j){double d=dc[j]*(j==8?mask:1.);jx+=gx[j]*d;jy+=gy[j]*d;}
  for(int j=0;j<3;++j){jx+=gx[9+j]*dp[j];jy+=gy[9+j]*dp[j];}
}
} // namespace o2
#undef O2_HD
