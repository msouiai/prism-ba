#pragma once
#include "projection.h"
// This research CLI is serialized. State belongs to one active solve, with RAII
// cleanup. Off and s=1 call the original analytic functions exactly.
__constant__ double o2_stage_device=1.;
__constant__ const double* o2_depth_device=nullptr;
static double o2_stage_host=1.;
static bool o2_context_active=false;
__device__ __forceinline__ double O2Depth(int observation,double z){
  return o2_stage_device==1.?z:o2::Denominator(z,o2_depth_device[observation],o2_stage_device);
}
__device__ __forceinline__ void O2BalResidualGrad12(int o,
 Scalar R00,Scalar R01,Scalar R02,Scalar R10,Scalar R11,Scalar R12,Scalar R20,Scalar R21,Scalar R22,
 Scalar tx,Scalar ty,Scalar tz,Scalar X,Scalar Y,Scalar Z,Scalar f,Scalar k1,Scalar k2,Scalar ox,Scalar oy,
 Scalar* gx,Scalar* gy,Scalar* rx,Scalar* ry){
  if(o2_stage_device==1.){
    BalResidualGrad12(R00,R01,R02,R10,R11,R12,R20,R21,R22,tx,ty,tz,X,Y,Z,f,k1,k2,ox,oy,gx,gy,rx,ry);return;
  }
  const double r[9]={R00,R01,R02,R10,R11,R12,R20,R21,R22},t[3]={tx,ty,tz},x[3]={X,Y,Z};
  o2::ResidualGrad12(r,t,x,f,k1,k2,ox,oy,o2_depth_device[o],o2_stage_device,gx,gy,rx,ry);
}
__device__ __forceinline__ void O2BalDirectional12(int o,const double* R,const double* t,
 const double* X,double f,double k1,double k2,double ox,double oy,const double* dc,const double* dp,
 double mask,double& rx,double& ry,double& jx,double& jy){
  if(o2_stage_device==1.){BalDirectional12(R,t,X,f,k1,k2,ox,oy,dc,dp,mask,rx,ry,jx,jy);return;}
  o2::Directional12(R,t,X,f,k1,k2,ox,oy,dc,dp,mask,o2_depth_device[o],o2_stage_device,rx,ry,jx,jy);
}
