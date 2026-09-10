// C_tau=R^T R; W C_tau^-1 W^T=(R^-T W^T)^T(R^-T W^T).
// One forward solve per row instead of a forward and backward solve.
// Same layout, fixed warp reduction tree, and lower triangle as legacy.
template <int CD, typename HT>
__global__ void SchurGram(const HT* __restrict__ W,const int* __restrict__ pt,
 const int* __restrict__ off,const double* __restrict__ R,int no,double* __restrict__ B){
 int c=blockIdx.x;constexpr int NT=CD*(CD+1)/2;double acc[NT];
 #pragma unroll
 for(int t=0;t<NT;++t)acc[t]=0;
 for(int k=off[c]+threadIdx.x;k<off[c+1];k+=32){
  const double* rp=R+6ul*pt[k];if(!(rp[0]>0&&rp[3]>0&&rp[5]>0))continue;
  double Y[3*CD];
  #pragma unroll
  for(int i=0;i<CD;++i){
   double y0=W[(3ul*i)*no+k]/rp[0];
   double y1=(W[(3ul*i+1)*no+k]-rp[1]*y0)/rp[3];
   double y2=(W[(3ul*i+2)*no+k]-rp[2]*y0-rp[4]*y1)/rp[5];
   Y[3*i]=y0;Y[3*i+1]=y1;Y[3*i+2]=y2;
  }
  int t=0;
  #pragma unroll
  for(int i=0;i<CD;++i){
   #pragma unroll
   for(int j=0;j<=i;++j,++t)acc[t]-=Y[3*i]*Y[3*j]+Y[3*i+1]*Y[3*j+1]+Y[3*i+2]*Y[3*j+2];
  }
 }
 int t=0;
 #pragma unroll
 for(int i=0;i<CD;++i){
  #pragma unroll
  for(int j=0;j<=i;++j,++t){double v=acc[t];
   for(int d=16;d;d>>=1)v+=__shfl_down_sync(0xffffffffu,v,d);
   if(threadIdx.x==0){B[81ul*c+CD*i+j]+=v;if(i!=j)B[81ul*c+CD*j+i]+=v;}
  }
 }
}
