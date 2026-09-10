#pragma once
// Same left-rotation/additive translation/intrinsics/point parameterization as
// BalResidualGrad12. Factor through the 2x3 projection derivative.
__device__ __forceinline__ void BalResidualGrad12(
 Scalar R00,Scalar R01,Scalar R02,Scalar R10,Scalar R11,Scalar R12,Scalar R20,Scalar R21,Scalar R22,
 Scalar tx,Scalar ty,Scalar tz,Scalar X,Scalar Y,Scalar Z,Scalar f,Scalar k1,Scalar k2,Scalar ox,Scalar oy,
 Scalar*gx,Scalar*gy,Scalar*rx,Scalar*ry){
 const double qx=R00*X+R01*Y+R02*Z,qy=R10*X+R11*Y+R12*Z,qz=R20*X+R21*Y+R22*Z;
 const double iz=1/(qz+tz),u=-(qx+tx)*iz,v=-(qy+ty)*iz,s=u*u+v*v,D=1+k1*s+k2*s*s,h=k1+2*k2*s;
 const double a=f*(D+2*u*u*h),b=2*f*u*v*h,c=f*(D+2*v*v*h);
 const double px=-a*iz,py=-b*iz,pz=-(a*u+b*v)*iz;
 const double yx=-b*iz,yy=-c*iz,yz=-(b*u+c*v)*iz;
 gx[0]=qy*pz-qz*py;gx[1]=qz*px-qx*pz;gx[2]=qx*py-qy*px;
 gy[0]=qy*yz-qz*yy;gy[1]=qz*yx-qx*yz;gy[2]=qx*yy-qy*yx;
 gx[3]=px;gx[4]=py;gx[5]=pz;gy[3]=yx;gy[4]=yy;gy[5]=yz;
 gx[6]=D*u;gx[7]=f*u*s;gx[8]=f*u*s*s;gy[6]=D*v;gy[7]=f*v*s;gy[8]=f*v*s*s;
 gx[9]=R00*px+R10*py+R20*pz;gx[10]=R01*px+R11*py+R21*pz;gx[11]=R02*px+R12*py+R22*pz;
 gy[9]=R00*yx+R10*yy+R20*yz;gy[10]=R01*yx+R11*yy+R21*yz;gy[11]=R02*yx+R12*yy+R22*yz;
 *rx=f*D*u-ox;*ry=f*D*v-oy;
}
__device__ __forceinline__ void BalDirectional12(const double*R,const double*t,const double*X,double f,double k1,double k2,double ox,double oy,const double*dc,const double*dp,double mask,double&rx,double&ry,double&jx,double&jy){
 double qx=R[0]*X[0]+R[1]*X[1]+R[2]*X[2],qy=R[3]*X[0]+R[4]*X[1]+R[5]*X[2],qz=R[6]*X[0]+R[7]*X[1]+R[8]*X[2];
 double dx=dc[1]*qz-dc[2]*qy+dc[3]+R[0]*dp[0]+R[1]*dp[1]+R[2]*dp[2];
 double dy=dc[2]*qx-dc[0]*qz+dc[4]+R[3]*dp[0]+R[4]*dp[1]+R[5]*dp[2];
 double dz=dc[0]*qy-dc[1]*qx+dc[5]+R[6]*dp[0]+R[7]*dp[1]+R[8]*dp[2];
 double iz=1/(qz+t[2]),u=-(qx+t[0])*iz,v=-(qy+t[1])*iz,du=-(dx+u*dz)*iz,dv=-(dy+v*dz)*iz;
 double s=u*u+v*v,ds=2*(u*du+v*dv),D=1+k1*s+k2*s*s,dD=dc[7]*s+mask*dc[8]*s*s+(k1+2*k2*s)*ds;
 rx=f*D*u-ox;ry=f*D*v-oy;jx=dc[6]*D*u+f*(dD*u+D*du);jy=dc[6]*D*v+f*(dD*v+D*dv);
}
