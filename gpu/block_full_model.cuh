#pragma once
// Diagnostic only: reconstruct the unregularized quadratic from stored blocks.
// W and Bo are rounded floats, so this does not replace direct acceptance.
__global__ void MFBlockModelCamera(const double*H,const double*d,int nc,double*out){
 int c=blockIdx.x*blockDim.x+threadIdx.x;double q=0;
 if(c<nc)for(int i=0;i<9;++i)for(int j=0;j<9;++j)q+=d[9*c+i]*H[81*c+9*i+j]*d[9*c+j];
 __shared__ double sh[256];sh[threadIdx.x]=q;__syncthreads();for(int k=128;k;k/=2){if(threadIdx.x<k)sh[threadIdx.x]+=sh[threadIdx.x+k];__syncthreads();}if(threadIdx.x==0)atomicAdd(out,sh[0]);
}
__global__ void MFBlockModelObs(const float*W,const float*B,const int*ci,const int*pi,const int*slots,const double*d,int no,int nc,double*out){
 int o=blockIdx.x*blockDim.x+threadIdx.x;double q=0,err=0;
 if(o<no){int c=ci[o],p=pi[o],k=slots[o];const double*dc=d+9*c,*dp=d+9*nc+3*p;double cross=0,abs_cross=0,jx=0,jy=0,ax=0,ay=0;
  for(int i=0;i<9;++i)for(int j=0;j<3;++j){double term=(double)W[(size_t)(3*i+j)*no+k]*dc[i]*dp[j];cross+=term;abs_cross+=fabs(term);}
  for(int j=0;j<3;++j){double x=(double)B[6*o+j]*dp[j],y=(double)B[6*o+3+j]*dp[j];jx+=x;jy+=y;ax+=fabs(x);ay+=fabs(y);}
  q=2*cross+jx*jx+jy*jy;const double u=5.9604648328104516e-8;double ex=u*ax,ey=u*ay;err=2*u*abs_cross+2*fabs(jx)*ex+ex*ex+2*fabs(jy)*ey+ey*ey;
 }
 __shared__ double sh[2][256];sh[0][threadIdx.x]=q;sh[1][threadIdx.x]=err;__syncthreads();for(int k=128;k;k/=2){if(threadIdx.x<k){sh[0][threadIdx.x]+=sh[0][threadIdx.x+k];sh[1][threadIdx.x]+=sh[1][threadIdx.x+k];}__syncthreads();}if(threadIdx.x<2)atomicAdd(out+1+threadIdx.x,sh[threadIdx.x][0]);
}
struct PrismBlockModel{
 double*out;PrismBlockModel(){CUDA_CHECK(cudaMalloc(&out,3*8));}~PrismBlockModel(){cudaFree(out);}
 struct Result{double slope,curvature,prediction,fragment_error_estimate;};
 Result Evaluate(const DeviceProblem&p,const double*step,const double*H,const float*W,const float*B,const double*bc,const double*bp,cublasHandle_t h){
  CUDA_CHECK(cudaMemset(out,0,24));MFBlockModelCamera<<<GridSize(p.ncam),256>>>(H,step,p.ncam,out);
  MFBlockModelObs<<<GridSize(p.nobs),256>>>(W,B,p.cam_idx,p.pt_idx,p.obs2cslot,step,p.nobs,p.ncam,out);
  double sums[3],dc,dp;CUDA_CHECK(cudaMemcpy(sums,out,24,cudaMemcpyDeviceToHost));cublasDdot(h,9*p.ncam,bc,1,step,1,&dc);cublasDdot(h,3*p.npt,bp,1,step+9*p.ncam,1,&dp);
  return {dc+dp,sums[0]+sums[1],-dc-dp-.5*(sums[0]+sums[1]),.5*sums[2]};
 }
};
