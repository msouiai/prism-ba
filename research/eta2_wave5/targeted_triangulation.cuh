#pragma once

// Wave 5 A1: targeted, in-attempt repair for two-observation tracks whose
// first-order pixel model disagrees with the corresponding linear-fractional
// projection.  The scored objective is unchanged.  The repaired point is a
// deterministic Lindstrom niter2 epipolar correction followed by a 3x3
// inhomogeneous DLT solve at the already-proposed cameras.

namespace eta2_w5_a1 {

__device__ __forceinline__ bool finite3(const double* x) {
  return isfinite(x[0]) && isfinite(x[1]) && isfinite(x[2]);
}

__device__ __forceinline__ void camera_y(const double* R, const double* t,
                                          const double* X, double* y) {
#pragma unroll
  for (int i = 0; i < 3; ++i)
    y[i] = R[3*i]*X[0] + R[3*i+1]*X[1] + R[3*i+2]*X[2] + t[i];
}

__device__ __forceinline__ double pixel_cost(
    int o, int point, const int* ci, const double* uv, const double* R,
    const double* t, const double* X, const double* f, const double* k1,
    const double* k2) {
  const int c = ci[o];
  double y[3]; camera_y(R + 9*c, t + 3*c, X + 3*point, y);
  if (!finite3(y) || y[2] == 0.0) return CUDART_INF;
  const double u = -y[0]/y[2], v = -y[1]/y[2], s = u*u + v*v;
  const double scale = f[c]*(1.0 + k1[c]*s + k2[c]*s*s);
  const double rx = scale*u - uv[2*o], ry = scale*v - uv[2*o+1];
  const double value = .5*(rx*rx + ry*ry);
  return isfinite(value) ? value : CUDART_INF;
}

// Invert rd=r(1+k r^2) on its origin-connected monotone branch.  This is the
// branch selected by the registered CPU replay and is the only one continuous
// with zero distortion.  Returns a conventional pinhole pixel q=f*Yxy/Yz;
// BAL's normalized projection has the opposite sign.
__device__ __forceinline__ bool undistort_standard_pixel(
    double ox, double oy, double f, double k, double& qx, double& qy) {
  if (!(isfinite(ox) && isfinite(oy) && isfinite(f) && isfinite(k)) ||
      fabs(f) < 1e-300) return false;
  const double dx = ox/f, dy = oy/f, rd = sqrt(dx*dx + dy*dy);
  if (!isfinite(rd)) return false;
  if (rd == 0.0) { qx = qy = 0.0; return true; }
  double lo = 0.0, hi;
  if (k < 0.0) {
    hi = sqrt(-1.0/(3.0*k))*(1.0-8.0*2.2204460492503131e-16);
    const double max_rd = hi*(1.0+k*hi*hi);
    if (!(isfinite(max_rd) && rd <= max_rd*(1.0+1e-12))) return false;
  } else {
    hi = fmax(1.0, rd);
    for (int i = 0; i < 32 && hi*(1.0+k*hi*hi) < rd; ++i) hi *= 2.0;
    if (!(isfinite(hi) && hi*(1.0+k*hi*hi) >= rd)) return false;
  }
  for (int i = 0; i < 64; ++i) {
    const double mid = .5*(lo+hi);
    if (mid*(1.0+k*mid*mid) < rd) lo = mid; else hi = mid;
  }
  const double r = .5*(lo+hi), ratio = r/rd;
  // observed BAL pixel = f * distorted * (-Yxy/Yz)
  qx = -ox*ratio; qy = -oy*ratio;
  const double forward = r*(1.0+k*r*r);
  return isfinite(qx) && isfinite(qy) &&
         fabs(forward-rd) <= 1e-10*fmax(1.0,rd);
}

__device__ __forceinline__ void relative_fundamental(
    const double* R1, const double* t1, double f1,
    const double* R2, const double* t2, double f2, double* F) {
  double R21[9], tr[3];
#pragma unroll
  for (int i=0;i<3;++i) for (int j=0;j<3;++j) {
    double v=0; for (int k=0;k<3;++k) v += R2[3*i+k]*R1[3*j+k];
    R21[3*i+j]=v;
  }
#pragma unroll
  for (int i=0;i<3;++i) {
    double v=t2[i]; for (int k=0;k<3;++k) v-=R21[3*i+k]*t1[k];
    tr[i]=v;
  }
  double E[9];
  // E = [tr]_x R21.
#pragma unroll
  for (int j=0;j<3;++j) {
    E[j]   = -tr[2]*R21[3+j] + tr[1]*R21[6+j];
    E[3+j] =  tr[2]*R21[j]   - tr[0]*R21[6+j];
    E[6+j] = -tr[1]*R21[j]   + tr[0]*R21[3+j];
  }
#pragma unroll
  for (int i=0;i<3;++i) for (int j=0;j<3;++j) {
    const double rs = i<2 ? f2 : 1.0, cs = j<2 ? f1 : 1.0;
    F[3*i+j] = E[3*i+j]/(rs*cs);
  }
}

__device__ __forceinline__ bool lindstrom_niter2(
    const double* F, double x0, double y0, double x1, double y1,
    double& q0, double& r0, double& q1, double& r1) {
  // Lindstrom writes x^T E x'=0.  F here obeys x'^T F x=0, so E=F^T.
  const double x[3]={x0,y0,1.0}, xp[3]={x1,y1,1.0};
  double n[2], np[2];
  n[0]=F[0]*xp[0]+F[3]*xp[1]+F[6];
  n[1]=F[1]*xp[0]+F[4]*xp[1]+F[7];
  np[0]=F[0]*x[0]+F[1]*x[1]+F[2];
  np[1]=F[3]*x[0]+F[4]*x[1]+F[5];
  // Top-left 2x2 of E=F^T.
  const double a=n[0]*(F[0]*np[0]+F[3]*np[1])+
                 n[1]*(F[1]*np[0]+F[4]*np[1]);
  const double b=.5*(n[0]*n[0]+n[1]*n[1]+np[0]*np[0]+np[1]*np[1]);
  const double c=x[0]*(F[0]*xp[0]+F[3]*xp[1]+F[6])+
                 x[1]*(F[1]*xp[0]+F[4]*xp[1]+F[7])+
                       F[2]*xp[0]+F[5]*xp[1]+F[8];
  const double disc=b*b-a*c;
  if (!(isfinite(a)&&isfinite(b)&&isfinite(c)&&isfinite(disc)) ||
      disc < -1e-12*fmax(1.0,fmax(b*b,fabs(a*c)))) return false;
  const double root=sqrt(fmax(0.0,disc)), den=b+copysign(root,b);
  if (!(isfinite(den)) || fabs(den)<1e-300) return false;
  const double lam=c/den, dx0=lam*n[0], dx1=lam*n[1];
  const double dp0=lam*np[0], dp1=lam*np[1];
  const double nn0=n[0]-F[0]*dp0-F[3]*dp1;
  const double nn1=n[1]-F[1]*dp0-F[4]*dp1;
  const double nnp0=np[0]-F[0]*dx0-F[1]*dx1;
  const double nnp1=np[1]-F[3]*dx0-F[4]*dx1;
  const double den2=nn0*nn0+nn1*nn1+nnp0*nnp0+nnp1*nnp1;
  if (!(isfinite(den2)) || den2<1e-300) return false;
  const double lam2=lam*2.0*root/den2;
  q0=x0-lam2*nn0; r0=y0-lam2*nn1;
  q1=x1-lam2*nnp0; r1=y1-lam2*nnp1;
  return isfinite(q0)&&isfinite(r0)&&isfinite(q1)&&isfinite(r1);
}

__device__ __forceinline__ bool solve3(double* A, double* b, double* x) {
  double m[3][4];
#pragma unroll
  for(int i=0;i<3;++i){for(int j=0;j<3;++j)m[i][j]=A[3*i+j];m[i][3]=b[i];}
  double scale=0;for(int i=0;i<3;++i)for(int j=0;j<3;++j)scale=fmax(scale,fabs(m[i][j]));
  if (!(isfinite(scale)) || scale<1e-300) return false;
  for(int k=0;k<3;++k){
    int pivot=k;for(int i=k+1;i<3;++i)if(fabs(m[i][k])>fabs(m[pivot][k]))pivot=i;
    if (!(isfinite(m[pivot][k])) || fabs(m[pivot][k])<1e-14*scale) return false;
    if(pivot!=k)for(int j=k;j<4;++j){double z=m[k][j];m[k][j]=m[pivot][j];m[pivot][j]=z;}
    for(int i=k+1;i<3;++i){double z=m[i][k]/m[k][k];for(int j=k;j<4;++j)m[i][j]-=z*m[k][j];}
  }
  for(int i=2;i>=0;--i){double z=m[i][3];for(int j=i+1;j<3;++j)z-=m[i][j]*x[j];x[i]=z/m[i][i];}
  return finite3(x);
}

__global__ void detector(
    const int* ci,const int* pi,const double* uv,const double* R,const double* t,
    const double* X,const double* f,const double* k1,const double* k2,
    const double* step,int no,int nc,double k2mask,double mean_r2,
    unsigned char* flags,unsigned long long* counts) {
  const int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=no)return;
  const int c=ci[o],p=pi[o];const double* r=R+9*c;const double* x=X+3*p;
  const double* dc=step+9*c;const double* dp=step+9*nc+3*p;
  double rx,ry,jx,jy;
  BalDirectional12(r,t+3*c,x,f[c],k1[c],k2[c],uv[2*o],uv[2*o+1],
                   dc,dp,k2mask,rx,ry,jx,jy);
  double q[3]={r[0]*x[0]+r[1]*x[1]+r[2]*x[2],
               r[3]*x[0]+r[4]*x[1]+r[5]*x[2],
               r[6]*x[0]+r[7]*x[1]+r[8]*x[2]};
  double dy[3]={dc[1]*q[2]-dc[2]*q[1]+dc[3]+r[0]*dp[0]+r[1]*dp[1]+r[2]*dp[2],
                dc[2]*q[0]-dc[0]*q[2]+dc[4]+r[3]*dp[0]+r[4]*dp[1]+r[5]*dp[2],
                dc[0]*q[1]-dc[1]*q[0]+dc[5]+r[6]*dp[0]+r[7]*dp[1]+r[8]*dp[2]};
  const double z=q[2]+t[3*c+2]+dy[2];bool hit=false;
  if(isfinite(z)&&z!=0){
    const double u=-(q[0]+t[3*c]+dy[0])/z,v=-(q[1]+t[3*c+1]+dy[1])/z,s=u*u+v*v;
    const double ff=f[c]+dc[6],kk=k1[c]+dc[7],kk2=k2[c]+k2mask*dc[8];
    const double sc=ff*(1.0+kk*s+kk2*s*s);
    const double rrx=sc*u-uv[2*o],rry=sc*v-uv[2*o+1];
    const double ex=rrx-(rx+jx),ey=rry-(ry+jy);
    const double den=fmax(rx*rx+ry*ry,mean_r2), ratio=(ex*ex+ey*ey)/den;
    hit=isfinite(ratio)&&ratio>.5;
  }
  flags[o]=(unsigned char)hit;if(hit)atomicAdd(counts,1ULL);
}

__global__ void repair(
    const int* offsets,const int* order,const int* ci,const double* uv,
    const double* oldR,const double* oldt,const double* oldX,
    const double* newR,const double* newt,double* newX,const double* f,
    const double* k1,const double* k2,const unsigned char* flags,int np,int nc,
    double* step,unsigned long long* counts,double* improvement) {
  const int p=blockIdx.x*blockDim.x+threadIdx.x;if(p>=np)return;
  const int begin=offsets[p],end=offsets[p+1];if(end-begin!=2)return;
  const int o0=order[begin],o1=order[begin+1];if(!(flags[o0]||flags[o1]))return;
  atomicAdd(counts+1,1ULL);
  const int c0=ci[o0],c1=ci[o1];
  if(c0==c1 || fabs(f[c0])<1e-300 || fabs(f[c1])<1e-300){atomicAdd(counts+3,1ULL);return;}
  double x0,y0,x1,y1;
  if(!undistort_standard_pixel(uv[2*o0],uv[2*o0+1],f[c0],k1[c0],x0,y0) ||
     !undistort_standard_pixel(uv[2*o1],uv[2*o1+1],f[c1],k1[c1],x1,y1)){
    atomicAdd(counts+3,1ULL);return;
  }
  double F[9];relative_fundamental(newR+9*c0,newt+3*c0,f[c0],
                                   newR+9*c1,newt+3*c1,f[c1],F);
  double q0,r0,q1,r1;
  if(!lindstrom_niter2(F,x0,y0,x1,y1,q0,r0,q1,r1)){
    atomicAdd(counts+3,1ULL);return;
  }
  double normal[9]={},rhs[3]={};
  const int cams[2]={c0,c1};const double qx[2]={q0,q1},qy[2]={r0,r1};
  for(int h=0;h<2;++h){const int c=cams[h];const double* r=newR+9*c;const double* tt=newt+3*c;
    double rows[2][3],bb[2];
    for(int a=0;a<3;++a){rows[0][a]=qx[h]*r[6+a]-f[c]*r[a];rows[1][a]=qy[h]*r[6+a]-f[c]*r[3+a];}
    bb[0]=-(qx[h]*tt[2]-f[c]*tt[0]);bb[1]=-(qy[h]*tt[2]-f[c]*tt[1]);
    for(int row=0;row<2;++row)for(int a=0;a<3;++a){rhs[a]+=rows[row][a]*bb[row];
      for(int b=0;b<3;++b)normal[3*a+b]+=rows[row][a]*rows[row][b];}
  }
  double candidate[3]={};if(!solve3(normal,rhs,candidate)){atomicAdd(counts+3,1ULL);return;}
  const double* old=oldX+3*p;const double* gn=newX+3*p;
  bool depth_ok=true;
  for(int h=0;h<2;++h){const int c=cams[h];double zo[3],zg[3],zc[3];
    camera_y(oldR+9*c,oldt+3*c,old,zo);camera_y(newR+9*c,newt+3*c,gn,zg);
    camera_y(newR+9*c,newt+3*c,candidate,zc);
    depth_ok=depth_ok&&isfinite(zo[2])&&isfinite(zg[2])&&isfinite(zc[2])&&
      zo[2]*zc[2]>0.0&&fabs(zc[2])>=fabs(zg[2]);
  }
  if(!depth_ok){atomicAdd(counts+2,1ULL);return;}
  const double gn_cost=pixel_cost(o0,p,ci,uv,newR,newt,newX,f,k1,k2)+
                       pixel_cost(o1,p,ci,uv,newR,newt,newX,f,k1,k2);
  double local[3]={candidate[0],candidate[1],candidate[2]};
  // pixel_cost indexes by point, so temporarily evaluate the two observations directly.
  double cand_cost=0;
  for(int h=0;h<2;++h){const int o=h?o1:o0,c=cams[h];double yy[3];camera_y(newR+9*c,newt+3*c,local,yy);
    if(!finite3(yy)||yy[2]==0){cand_cost=CUDART_INF;break;}
    const double u=-yy[0]/yy[2],v=-yy[1]/yy[2],ss=u*u+v*v;
    const double sc=f[c]*(1.0+k1[c]*ss+k2[c]*ss*ss);
    const double ex=sc*u-uv[2*o],ey=sc*v-uv[2*o+1];cand_cost+=.5*(ex*ex+ey*ey);
  }
  if(isfinite(cand_cost)&&cand_cost<gn_cost){
    for(int a=0;a<3;++a){newX[3*p+a]=candidate[a];step[9*nc+3*p+a]=candidate[a]-old[a];}
    atomicAdd(counts+4,1ULL);atomicAdd(improvement,gn_cost-cand_cost);
  }
}

struct Result {
  unsigned long long flagged=0, eligible=0, margin_rejects=0, algebra_failures=0, wins=0;
  double improvement=0;
};

} // namespace eta2_w5_a1

struct Eta2W5TargetedTriangulation {
  unsigned char* flags=nullptr;unsigned long long* counts=nullptr;double* improvement=nullptr;
  explicit Eta2W5TargetedTriangulation(int nobs){
    CUDA_CHECK(cudaMalloc(&flags,(size_t)nobs));CUDA_CHECK(cudaMalloc(&counts,5*sizeof(*counts)));
    CUDA_CHECK(cudaMalloc(&improvement,sizeof(*improvement)));
  }
  ~Eta2W5TargetedTriangulation(){cudaFree(flags);cudaFree(counts);cudaFree(improvement);}
  Eta2W5TargetedTriangulation(const Eta2W5TargetedTriangulation&)=delete;
  eta2_w5_a1::Result Apply(const DeviceProblem& p,const DeviceState& old,
      const DeviceState& proposed,double* step,double k2mask,double mean_r2){
    CUDA_CHECK(cudaMemset(counts,0,5*sizeof(*counts)));CUDA_CHECK(cudaMemset(improvement,0,sizeof(*improvement)));
    eta2_w5_a1::detector<<<GridSize(p.nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,old.R,old.t,old.X,
      INTR_F(p,old),INTR_K1(p,old),INTR_K2(p,old),step,p.nobs,p.ncam,k2mask,mean_r2,flags,counts);
    eta2_w5_a1::repair<<<GridSize(p.npt),256>>>(p.point_obs_offsets,p.point_obs_list,p.cam_idx,p.uv,
      old.R,old.t,old.X,proposed.R,proposed.t,proposed.X,INTR_F(p,proposed),INTR_K1(p,proposed),
      INTR_K2(p,proposed),flags,p.npt,p.ncam,step,counts,improvement);
    eta2_w5_a1::Result result;unsigned long long h[5];
    CUDA_CHECK(cudaMemcpy(h,counts,5*sizeof(*counts),cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(&result.improvement,improvement,sizeof(*improvement),cudaMemcpyDeviceToHost));
    result.flagged=h[0];result.eligible=h[1];result.margin_rejects=h[2];result.algebra_failures=h[3];result.wins=h[4];
    return result;
  }
};
