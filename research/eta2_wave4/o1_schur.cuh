#pragma once
// O1 research overlay. No mutations of the frozen Eta2 source or controller.
namespace O1 {
struct Buf {
 double* p=nullptr;size_t n=0;
 explicit Buf(size_t m):n(m){CUDA_CHECK(cudaMalloc(&p,m*sizeof(double)));zero();}
 ~Buf(){cudaFree(p);} Buf(const Buf&)=delete;
 void zero(){CUDA_CHECK(cudaMemset(p,0,n*sizeof(double)));}
 void from(const std::vector<double>& h){if(h.size()!=n)throw std::runtime_error("O1 buffer shape");CUDA_CHECK(cudaMemcpy(p,h.data(),8*n,cudaMemcpyHostToDevice));}
 std::vector<double> host() const {std::vector<double> h(n);CUDA_CHECK(cudaMemcpy(h.data(),p,8*n,cudaMemcpyDeviceToHost));return h;}
};
struct Group {int point,n,cam[3];double a[9],sgn[3],h[3],ki[9];};
__device__ void mv(const double* A,const double* x,double* y){for(int i=0;i<3;++i){y[i]=0;for(int j=0;j<3;++j)y[i]+=A[3*i+j]*x[j];}}
__device__ void coords(const double* R,const double* t,const double* X,int c,int j,double* y){mv(R+9*c,X+3*j,y);for(int k=0;k<3;++k)y[k]+=t[3*c+k];}
__device__ bool ray(double qx,double qy,double k,double curx,double cury,double* v){
 double u=hypot(qx,qy),roots[3];int n=0;
 if(u==0){v[0]=v[1]=0;v[2]=1;return true;}
 if(k==0)roots[n++]=u;
 else {double pp=1/k,qq=-u/k,D=qq*qq/4+pp*pp*pp/27;
  if(D>=0)roots[n++]=cbrt(-qq/2+sqrt(D))+cbrt(-qq/2-sqrt(D));
  else {double rad=2*sqrt(-pp/3),arg=fmax(-1.,fmin(1.,(3*qq/(2*pp))*sqrt(-3/pp))),a=acos(arg)/3;
   for(int j=0;j<3;++j)roots[n++]=rad*cos(a-2.09439510239319549*j);}}
 double best=INFINITY,r=0;for(int j=0;j<n;++j){double a=roots[j],err=hypot(qx*a/u-curx,qy*a/u-cury);if(err<best){best=err;r=a;}}
 // Newton polishing of the chosen real radial branch; no scene-dependent root selection.
 for(int it=0;it<3;++it){double d=1+3*k*r*r;if(fabs(d)>1e-14)r-=(r+k*r*r*r-u)/d;}
 if(!isfinite(r)||fabs(r+k*r*r*r-u)>1e-7*fmax(1.,u))return false;
 v[0]=-qx*r/u;v[1]=-qy*r/u;v[2]=1;double l=sqrt(v[0]*v[0]+v[1]*v[1]+1);for(int i=0;i<3;++i)v[i]/=l;return true;
}
__global__ void rays(DeviceProblem p,DeviceState s,double* v,double* w,double* depths,int* bad,bool weights){
 int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=p.nobs)return;int c=p.cam_idx[o],j=p.pt_idx[o];double y[3];coords(s.R,s.t,s.X,c,j,y);
 double f=s.intr[c],k=s.intr[p.ncam+c],qx=-y[0]/y[2],qy=-y[1]/y[2],vv[3];
 if(!isfinite(qx)||!isfinite(qy)||fabs(f)<1e-100||!ray(p.uv[2*o]/f,p.uv[2*o+1]/f,k,qx,qy,vv)){atomicAdd(bad,1);return;}
 for(int a=0;a<3;++a)v[3*o+a]=vv[a];
 if(weights){double fac=f*(1+k*(qx*qx+qy*qy)),rx=fac*qx-p.uv[2*o],ry=fac*qy-p.uv[2*o+1],dot=0;
  for(int a=0;a<3;++a)dot+=vv[a]*y[a];double ee=0;for(int a=0;a<3;++a)ee+=(y[a]-vv[a]*dot)*(y[a]-vv[a]*dot);
  double ss=rx*rx+ry*ry;w[o]=(ee>1e-30)?ss/ee:f*f/(y[2]*y[2]);depths[o]=y[2];if(!isfinite(w[o])||w[o]<0)atomicAdd(bad,1);}
}
__global__ void orient(DeviceProblem p,DeviceState s,const double* v,const double* w,double* cov){
 int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=p.nobs)return;int c=p.cam_idx[o],j=p.pt_idx[o];double y[3],a=0;coords(s.R,s.t,s.X,c,j,y);
 for(int k=0;k<3;++k)a+=v[3*o+k]*y[k];for(int k=0;k<3;++k)for(int l=0;l<3;++l)
  atomicAdd(cov+9*c+3*k+l,w[o]*(v[3*o+k]*a-s.t[3*c+k])*s.X[3*j+l]);
}
__global__ void rotationCheck(DeviceProblem p,DeviceState s,const double* depths,int* bad){
 int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=p.nobs)return;int c=p.cam_idx[o];double y[3];coords(s.R,s.t,s.X,c,p.pt_idx[o],y);
 if(copysign(1.,depths[o])*y[2]<.5*fabs(depths[o]))atomicExch(bad+c,1);
}
__global__ void rotationRestore(int n,double* R,const double* old,const int* bad){int c=blockIdx.x*blockDim.x+threadIdx.x;if(c<n&&bad[c])for(int k=0;k<9;++k)R[9*c+k]=old[9*c+k];}
__global__ void intrAssemble(DeviceProblem p,DeviceState s,double* normal){
 int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=p.nobs)return;int c=p.cam_idx[o];double y[3];coords(s.R,s.t,s.X,c,p.pt_idx[o],y);
 double x=-y[0]/y[2],z=-y[1]/y[2],a=x*x+z*z,b=x*p.uv[2*o]+z*p.uv[2*o+1];
 double v[5]={a,a*a,a*a*a,b,a*b};for(int k=0;k<5;++k)atomicAdd(normal+5*c+k,v[k]);
}
__global__ void intrUpdate(int n,double* intr,const double* norm){int c=blockIdx.x*blockDim.x+threadIdx.x;if(c>=n)return;
 const double* a=norm+5*c;double det=a[0]*a[2]-a[1]*a[1];if(det>1e-14*a[0]*a[2]){
 double f=(a[2]*a[3]-a[1]*a[4])/det,b=(a[0]*a[4]-a[1]*a[3])/det;
 if(isfinite(f)&&isfinite(b)&&fabs(f)>1e-12*fmax(1.,fabs(intr[c]))){intr[c]=f;intr[n+c]=b/f;}}}
__global__ void assemble(DeviceProblem p,DeviceState s,const double* v,const double* w,double* U,double* V,double* W,double* bc,double* bp){
 int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=p.nobs)return;int c=p.cam_idx[o],j=p.pt_idx[o];const double* R=s.R+9*c;double y[3],P[9],PR[9],e[3];coords(s.R,s.t,s.X,c,j,y);
 for(int a=0;a<3;++a)for(int b=0;b<3;++b)P[3*a+b]=(a==b)-v[3*o+a]*v[3*o+b];mv(P,y,e);
 for(int a=0;a<3;++a)for(int b=0;b<3;++b){double x=0;for(int k=0;k<3;++k)x+=P[3*a+k]*R[3*k+b];PR[3*a+b]=x;W[9*o+3*a+b]=w[o]*x;atomicAdd(U+9*c+3*a+b,w[o]*P[3*a+b]);}
 for(int a=0;a<3;++a){atomicAdd(bc+3*c+a,-w[o]*e[a]);double b=0;for(int k=0;k<3;++k)b+=R[3*k+a]*e[k];atomicAdd(bp+3*j+a,-w[o]*b);
  for(int b=0;b<3;++b){double x=0;for(int k=0;k<3;++k)x+=R[3*k+a]*PR[3*k+b];atomicAdd(V+9*j+3*a+b,w[o]*x);}}
}
__global__ void inverse(int n,const double* A,double* inv,int* bad){
 int id=blockIdx.x*blockDim.x+threadIdx.x;if(id>=n)return;double a[9],q[9]={1,0,0,0,1,0,0,0,1};for(int k=0;k<9;++k)a[k]=A[9*id+k];
 for(int it=0;it<18;++it)for(int p=0;p<2;++p)for(int r=p+1;r<3;++r){double ap=a[3*p+p],ar=a[3*r+r],off=a[3*p+r];
  if(fabs(off)<=1e-18*(fabs(ap)+fabs(ar)))continue;double t=.5*atan2(2*off,ar-ap),c=cos(t),s=sin(t);
  for(int k=0;k<3;++k){double x=a[3*k+p],y=a[3*k+r];a[3*k+p]=c*x-s*y;a[3*k+r]=s*x+c*y;}
  for(int k=0;k<3;++k){double x=a[3*p+k],y=a[3*r+k];a[3*p+k]=c*x-s*y;a[3*r+k]=s*x+c*y;}
  for(int k=0;k<3;++k){double x=q[3*k+p],y=q[3*k+r];q[3*k+p]=c*x-s*y;q[3*k+r]=s*x+c*y;}}
 double mx=fmax(a[0],fmax(a[4],a[8]));if(!isfinite(mx)||mx<=0){atomicAdd(bad,1);for(int k=0;k<9;++k)inv[9*id+k]=0;return;}
 for(int k=0;k<3;++k)if(a[4*k]<-1e-12*mx)atomicAdd(bad,1);
 for(int k=0;k<3;++k)for(int l=0;l<3;++l){double v=0;for(int h=0;h<3;++h)if(a[4*h]>1e-14*mx)v+=q[3*k+h]*q[3*l+h]/a[4*h];inv[9*id+3*k+l]=v;}
}
__global__ void blockApply(int n,const double* A,const double* x,double* y){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)mv(A+9*i,x+3*i,y+3*i);}
__global__ void wt(DeviceProblem p,const double* W,const double* z,double* q){int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=p.nobs)return;int c=p.cam_idx[o],j=p.pt_idx[o];for(int a=0;a<3;++a){double v=0;for(int b=0;b<3;++b)v+=W[9*o+3*b+a]*z[3*c+b];atomicAdd(q+3*j+a,v);}}
__global__ void wminus(DeviceProblem p,const double* W,const double* u,double* out){int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=p.nobs)return;int c=p.cam_idx[o],j=p.pt_idx[o];for(int a=0;a<3;++a){double v=0;for(int b=0;b<3;++b)v+=W[9*o+3*a+b]*u[3*j+b];atomicAdd(out+3*c+a,-v);}}
__global__ void project(int n,double* x,int far,const double* axis){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=n)return;if(i==0)for(int k=0;k<3;++k)x[k]=0;if(i==far){double d=0;for(int k=0;k<3;++k)d+=axis[k]*x[3*i+k];for(int k=0;k<3;++k)x[3*i+k]-=axis[k]*d;}}
// mode 0: Schur product correction; 1: constrained RHS; 2: point backsolve.
__global__ void groupPoint(int n,const Group* g,const double* vi,const double* q,const double* z,double* u,double* nu,int mode){
 int id=blockIdx.x*blockDim.x+threadIdx.x;if(id>=n)return;Group a=g[id];double t[3],rhs[3]={0,0,0},v[3]={0,0,0};mv(vi+9*a.point,q+3*a.point,t);
 for(int k=0;k<a.n;++k){double d=0;for(int l=0;l<3;++l)d+=a.a[3*k+l]*t[l];
  rhs[k]=mode==0?(a.sgn[k]*z[3*a.cam[k]+2]-d):(d-a.h[k]+(mode==2?a.sgn[k]*z[3*a.cam[k]+2]:0));}
 for(int k=0;k<a.n;++k){for(int l=0;l<a.n;++l)v[k]+=a.ki[3*k+l]*rhs[l];nu[3*id+k]=v[k];}
 double x[3];for(int l=0;l<3;++l){x[l]=q[3*a.point+l];for(int k=0;k<a.n;++k)x[l]+=(mode==0?1.:-1.)*a.a[3*k+l]*v[k];}mv(vi+9*a.point,x,u+3*a.point);
}
__global__ void groupCamera(int n,const Group* g,const double* nu,double* out,double sign){int id=blockIdx.x*blockDim.x+threadIdx.x;if(id>=n)return;for(int k=0;k<g[id].n;++k)atomicAdd(out+3*g[id].cam[k]+2,sign*g[id].sgn[k]*nu[3*id+k]);}
__global__ void fraction(DeviceProblem p,DeviceState s,const double* old,const double* tc,const double* xc,const double* tn,const double* xn,const int* active,double* a){
 int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=p.nobs)return;a[o]=1;if(active[o])return;int c=p.cam_idx[o],j=p.pt_idx[o];double y[3];coords(s.R,s.t,s.X,c,j,y);
 double sg=copysign(1.,old[o]),h=.5*fabs(old[o])-sg*y[2],lc=tc[3*c+2],ln=tn[3*c+2];for(int k=0;k<3;++k){lc+=s.R[9*c+6+k]*xc[3*j+k];ln+=s.R[9*c+6+k]*xn[3*j+k];}lc*=sg;ln*=sg;
 double tol=1e-9*fmax(fabs(old[o]),1e-12);if(ln<h-tol&&lc>ln)a[o]=fmax(0.,fmin(1.,(lc-h)/(lc-ln)));
}
__global__ void apply(int n,double* x,const double* dx){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)x[i]+=dx[i];}
__global__ void feasibility(DeviceProblem p,DeviceState s,const double* old,const double* dt,const double* dx,double* out){
 int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=p.nobs)return;int c=p.cam_idx[o],j=p.pt_idx[o];double y[3];coords(s.R,s.t,s.X,c,j,y);double dz=dt[3*c+2];for(int k=0;k<3;++k)dz+=s.R[9*c+6+k]*dx[3*j+k];
 out[o]=fmax(0.,.5-copysign(1.,old[o])*(y[2]+dz)/fmax(fabs(old[o]),1e-100));
}
__global__ void surrogate(DeviceProblem p,DeviceState s,const double* v,const double* w,double* out){int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=p.nobs)return;double y[3],d=0,e=0;coords(s.R,s.t,s.X,p.cam_idx[o],p.pt_idx[o],y);for(int k=0;k<3;++k)d+=v[3*o+k]*y[k];for(int k=0;k<3;++k)e+=(y[k]-v[3*o+k]*d)*(y[k]-v[3*o+k]*d);out[o]=.5*w[o]*e;}
__global__ void pointResidual(int n,const double* V,const double* dp,const double* q,const Group* groups,int ng,const double* nu,double* r){int j=blockIdx.x*blockDim.x+threadIdx.x;if(j>=n)return;mv(V+9*j,dp+3*j,r+3*j);for(int k=0;k<3;++k)r[3*j+k]-=q[3*j+k];}
__global__ void addPointConstraint(int n,const Group* g,const double* nu,double* r){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=n)return;for(int l=0;l<3;++l){double v=0;for(int k=0;k<g[i].n;++k)v+=g[i].a[3*k+l]*nu[3*i+k];r[3*g[i].point+l]+=v;}}


__global__ void schurDiagonal(DeviceProblem p,const double* W,const double* vi,double* diag){
 int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=p.nobs)return;int c=p.cam_idx[o],j=p.pt_idx[o];
 for(int k=0;k<3;++k)for(int l=0;l<3;++l){double x=0;for(int a=0;a<3;++a)for(int b=0;b<3;++b)x+=W[9*o+3*k+a]*vi[9*j+3*a+b]*W[9*o+3*l+b];atomicAdd(diag+9*c+3*k+l,-x);}
}

struct Solver {
 const DeviceProblem& p;DeviceState& s;
 Buf v,w,depth,U,V,W,ui,vi,bc,bp,q,u,rhs,z,r,pc,d,ad,tn,xn,tc,xc,frac,axis,nu;
 int *bad=nullptr,*active=nullptr;Group* dg=nullptr;std::vector<Group> groups;std::vector<int> act,ci,pi;std::vector<double> R,t,X,dep;int far=1,products=0,iterations=0;double linearResidual=0,pointResidualNorm=0;
 double feasibilityResidual=0; cublasHandle_t blas;
 Solver(const DeviceProblem& pp,DeviceState& ss):p(pp),s(ss),v(3*p.nobs),w(p.nobs),depth(p.nobs),U(9*p.ncam),V(9*p.npt),W(9*p.nobs),ui(9*p.ncam),vi(9*p.npt),bc(3*p.ncam),bp(3*p.npt),q(3*p.npt),u(3*p.npt),rhs(3*p.ncam),z(3*p.ncam),r(3*p.ncam),pc(3*p.ncam),d(3*p.ncam),ad(3*p.ncam),tn(3*p.ncam),xn(3*p.npt),tc(3*p.ncam),xc(3*p.npt),frac(p.nobs),axis(3),nu(96){
  CUDA_CHECK(cudaMalloc(&bad,sizeof(int)*p.ncam));CUDA_CHECK(cudaMalloc(&active,sizeof(int)*p.nobs));CUDA_CHECK(cudaMalloc(&dg,sizeof(Group)*32));cublasCreate(&blas);
  ci.resize(p.nobs);pi.resize(p.nobs);CUDA_CHECK(cudaMemcpy(ci.data(),p.cam_idx,4*p.nobs,cudaMemcpyDeviceToHost));CUDA_CHECK(cudaMemcpy(pi.data(),p.pt_idx,4*p.nobs,cudaMemcpyDeviceToHost));
 }
 ~Solver(){cudaFree(bad);cudaFree(active);cudaFree(dg);cublasDestroy(blas);}
 int grid(int n){return (n+255)/256;}
 void resetBad(){CUDA_CHECK(cudaMemset(bad,0,4*p.ncam));}
 void checkBad(){int n;CUDA_CHECK(cudaMemcpy(&n,bad,4,cudaMemcpyDeviceToHost));if(n)throw std::runtime_error("invalid_ray_or_nonPSD_block");}
 void copy(double* a,const double* b,int n){CUDA_CHECK(cudaMemcpy(a,b,8*n,cudaMemcpyDeviceToDevice));}
 double dot(const double* a,const double* b,int n){double v;cublasDdot(blas,n,a,1,b,1,&v);return v;}
 double norm(const double* a,int n){double v;cublasDnrm2(blas,n,a,1,&v);return v;}
 void axpy(double a,const double* x,double* y,int n){cublasDaxpy(blas,n,&a,x,1,y,1);}
 void scale(double a,double* x,int n){cublasDscal(blas,n,&a,x,1);}
 void proj(double* x){project<<<grid(p.ncam),256>>>(p.ncam,x,far,axis.p);}
 void initializeRays(){resetBad();rays<<<grid(p.nobs),256>>>(p,s,v.p,w.p,depth.p,bad,true);checkBad();}
 int rotation(){Buf cov(9*p.ncam),old(9*p.ncam);copy(old.p,s.R,9*p.ncam);orient<<<grid(p.nobs),256>>>(p,s,v.p,w.p,cov.p);auto h=cov.host();auto rot=old.host();
  for(int c=0;c<p.ncam;++c){Eigen::Matrix3d A;for(int k=0;k<3;++k)for(int l=0;l<3;++l)A(k,l)=h[9*c+3*k+l];if(!A.allFinite())throw std::runtime_error("nonfinite_rotation_covariance");
   Eigen::JacobiSVD<Eigen::Matrix3d> svd(A,Eigen::ComputeFullU|Eigen::ComputeFullV);Eigen::Matrix3d D=Eigen::Matrix3d::Identity();D(2,2)=(svd.matrixU()*svd.matrixV().transpose()).determinant();Eigen::Matrix3d Q=svd.matrixU()*D*svd.matrixV().transpose();
   for(int k=0;k<3;++k)for(int l=0;l<3;++l)rot[9*c+3*k+l]=Q(k,l);}
  CUDA_CHECK(cudaMemcpy(s.R,rot.data(),8*rot.size(),cudaMemcpyHostToDevice));resetBad();rotationCheck<<<grid(p.nobs),256>>>(p,s,depth.p,bad);std::vector<int> b(p.ncam);CUDA_CHECK(cudaMemcpy(b.data(),bad,4*p.ncam,cudaMemcpyDeviceToHost));int count=0;for(int x:b)count+=x;
  rotationRestore<<<grid(p.ncam),256>>>(p.ncam,s.R,old.p,bad);return count;
 }
 void intrinsics(){Buf normals(5*p.ncam);intrAssemble<<<grid(p.nobs),256>>>(p,s,normals.p);intrUpdate<<<grid(p.ncam),256>>>(p.ncam,s.intr,normals.p);resetBad();rays<<<grid(p.nobs),256>>>(p,s,v.p,w.p,depth.p,bad,false);checkBad();}
 void assembleBlocks(){
  U.zero();V.zero();bc.zero();bp.zero();assemble<<<grid(p.nobs),256>>>(p,s,v.p,w.p,U.p,V.p,W.p,bc.p,bp.p);resetBad();inverse<<<grid(p.npt),256>>>(p.npt,V.p,vi.p,bad);checkBad();
  {Buf diag(9*p.ncam);copy(diag.p,U.p,9*p.ncam);schurDiagonal<<<grid(p.nobs),256>>>(p,W.p,vi.p,diag.p);inverse<<<grid(p.ncam),256>>>(p.ncam,diag.p,ui.p,bad);checkBad();}

  R.resize(9*p.ncam);t.resize(3*p.ncam);X.resize(3*p.npt);CUDA_CHECK(cudaMemcpy(R.data(),s.R,8*R.size(),cudaMemcpyDeviceToHost));CUDA_CHECK(cudaMemcpy(t.data(),s.t,8*t.size(),cudaMemcpyDeviceToHost));CUDA_CHECK(cudaMemcpy(X.data(),s.X,8*X.size(),cudaMemcpyDeviceToHost));dep=depth.host();
  Eigen::Vector3d c0;for(int k=0;k<3;++k){c0[k]=0;for(int l=0;l<3;++l)c0[k]-=R[3*l+k]*t[l];}double best=0;Eigen::Vector3d dir;
  for(int c=1;c<p.ncam;++c){Eigen::Vector3d ci;for(int k=0;k<3;++k){ci[k]=0;for(int l=0;l<3;++l)ci[k]-=R[9*c+3*l+k]*t[3*c+l];}double d=(ci-c0).squaredNorm();if(d>best){best=d;far=c;dir=ci-c0;}}
  if(!(best>0))throw std::runtime_error("no_scale_anchor");dir.normalize();std::vector<double> a(3);for(int k=0;k<3;++k)for(int l=0;l<3;++l)a[k]+=R[9*far+3*k+l]*dir[l];axis.from(a);
  {std::vector<std::pair<int,int>> edges;edges.reserve(p.nobs);for(int o=0;o<p.nobs;++o)edges.emplace_back(pi[o],ci[o]);std::sort(edges.begin(),edges.end());if(std::adjacent_find(edges.begin(),edges.end())!=edges.end())throw std::runtime_error("duplicate_camera_point_edge");}
  act.clear();groups.clear();tc.zero();xc.zero();CUDA_CHECK(cudaMemset(active,0,4*p.nobs));
 }
 void buildGroups(){groups.clear();std::map<int,std::vector<int>> byPoint;for(int o:act)byPoint[pi[o]].push_back(o);
  for(auto& entry:byPoint){auto& obs=entry.second;if(obs.size()>3)throw std::runtime_error("more_than_three_active_point_constraints");Group g{};g.point=entry.first;g.n=obs.size();double vip[9];CUDA_CHECK(cudaMemcpy(vip,vi.p+9*g.point,72,cudaMemcpyDeviceToHost));Eigen::Matrix3d VI;for(int k=0;k<3;++k)for(int l=0;l<3;++l)VI(k,l)=vip[3*k+l];Eigen::MatrixXd A(g.n,3);
   for(int k=0;k<g.n;++k){int o=obs[k],c=ci[o];g.cam[k]=c;g.sgn[k]=std::copysign(1.,dep[o]);double zz=t[3*c+2];for(int l=0;l<3;++l){zz+=R[9*c+6+l]*X[3*g.point+l];A(k,l)=g.a[3*k+l]=g.sgn[k]*R[9*c+6+l];}g.h[k]=.5*std::abs(dep[o])-g.sgn[k]*zz;}
   Eigen::MatrixXd K=A*VI*A.transpose();Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> eig(K);if(eig.info()!=Eigen::Success||eig.eigenvalues()[0]<=1e-12*eig.eigenvalues().tail(1)[0])throw std::runtime_error("dependent_active_constraints");Eigen::MatrixXd inv=K.inverse();for(int k=0;k<g.n;++k)for(int l=0;l<g.n;++l)g.ki[3*k+l]=inv(k,l);groups.push_back(g);}
  if(!groups.empty())CUDA_CHECK(cudaMemcpy(dg,groups.data(),groups.size()*sizeof(Group),cudaMemcpyHostToDevice));CUDA_CHECK(cudaMemset(active,0,4*p.nobs));int one=1;for(int o:act)CUDA_CHECK(cudaMemcpy(active+o,&one,4,cudaMemcpyHostToDevice));
 }
 void correction(const double* qq,const double* zz,int mode){if(!groups.empty())groupPoint<<<grid(groups.size()),256>>>(groups.size(),dg,vi.p,qq,zz,u.p,nu.p,mode);}
 void cameraCorrection(double* out,double sign){if(!groups.empty())groupCamera<<<grid(groups.size()),256>>>(groups.size(),dg,nu.p,out,sign);}
 void reducedRhs(){blockApply<<<grid(p.npt),256>>>(p.npt,vi.p,bp.p,u.p);correction(bp.p,z.p,1);copy(rhs.p,bc.p,3*p.ncam);wminus<<<grid(p.nobs),256>>>(p,W.p,u.p,rhs.p);cameraCorrection(rhs.p,-1);proj(rhs.p);}
 void product(const double* x,double* out){q.zero();wt<<<grid(p.nobs),256>>>(p,W.p,x,q.p);blockApply<<<grid(p.npt),256>>>(p.npt,vi.p,q.p,u.p);correction(q.p,x,0);blockApply<<<grid(p.ncam),256>>>(p.ncam,U.p,x,out);wminus<<<grid(p.nobs),256>>>(p,W.p,u.p,out);cameraCorrection(out,1);proj(out);++products;}
 void solve(){int n=3*p.ncam;reducedRhs();z.zero();copy(r.p,rhs.p,n);double bn=norm(rhs.p,n);if(bn==0){linearResidual=0;return;}blockApply<<<grid(p.ncam),256>>>(p.ncam,ui.p,r.p,pc.p);proj(pc.p);copy(d.p,pc.p,n);double rz=dot(r.p,pc.p,n);
  for(int it=0;it<1024;++it){product(d.p,ad.p);double pa=dot(d.p,ad.p,n);if(!(pa>0&&rz>0))throw std::runtime_error("nonpositive_schur_curvature");double a=rz/pa;axpy(a,d.p,z.p,n);axpy(-a,ad.p,r.p,n);++iterations;
   if(norm(r.p,n)<=1e-8*bn)break;blockApply<<<grid(p.ncam),256>>>(p.ncam,ui.p,r.p,pc.p);proj(pc.p);double next=dot(r.p,pc.p,n);scale(next/rz,d.p,n);axpy(1,pc.p,d.p,n);rz=next;}
  product(z.p,ad.p);axpy(-1,rhs.p,ad.p,n);linearResidual=norm(ad.p,n)/bn;if(!(linearResidual<=1e-7))throw std::runtime_error("pcg_residual_cap");
 }
 void backsolve(){copy(tn.p,z.p,3*p.ncam);q.zero();wt<<<grid(p.nobs),256>>>(p,W.p,z.p,q.p);scale(-1,q.p,3*p.npt);axpy(1,bp.p,q.p,3*p.npt);blockApply<<<grid(p.npt),256>>>(p.npt,vi.p,q.p,u.p);correction(q.p,z.p,2);copy(xn.p,u.p,3*p.npt);
  pointResidual<<<grid(p.npt),256>>>(p.npt,V.p,xn.p,q.p,dg,groups.size(),nu.p,u.p);if(!groups.empty())addPointConstraint<<<grid(groups.size()),256>>>(groups.size(),dg,nu.p,u.p);
  pointResidualNorm=norm(u.p,3*p.npt)/std::max(1e-30,norm(bp.p,3*p.npt));if(!(pointResidualNorm<=1e-7))throw std::runtime_error("point_range_residual");
 }
 double surrogateCost(){surrogate<<<grid(p.nobs),256>>>(p,s,v.p,w.p,frac.p);double cost;cublasDasum(blas,p.nobs,frac.p,1,&cost);return cost;}
 void auditFeasibility(){feasibility<<<grid(p.nobs),256>>>(p,s,depth.p,tc.p,xc.p,frac.p);int idx;cublasIdamax(blas,p.nobs,frac.p,1,&idx);CUDA_CHECK(cudaMemcpy(&feasibilityResidual,frac.p+idx-1,8,cudaMemcpyDeviceToHost));if(!(feasibilityResidual<=1e-7))throw std::runtime_error("depth_feasibility_failure");}
 bool qp(const std::function<bool()>& expired){
  for(int it=0;it<64;++it){if(expired())throw std::runtime_error("opening_budget");buildGroups();solve();backsolve();fraction<<<grid(p.nobs),256>>>(p,s,depth.p,tc.p,xc.p,tn.p,xn.p,active,frac.p);int idx;cublasIdamin(blas,p.nobs,frac.p,1,&idx);--idx;double alpha;CUDA_CHECK(cudaMemcpy(&alpha,frac.p+idx,8,cudaMemcpyDeviceToHost));
   if(alpha<1){scale(1-alpha,tc.p,3*p.ncam);axpy(alpha,tn.p,tc.p,3*p.ncam);scale(1-alpha,xc.p,3*p.npt);axpy(alpha,xn.p,xc.p,3*p.npt);act.push_back(idx);if(act.size()>32)throw std::runtime_error("active_set_cap");continue;}
   copy(tc.p,tn.p,3*p.ncam);copy(xc.p,xn.p,3*p.npt);auto mult=nu.host();double worst=1e-8*std::max(1.,norm(bc.p,3*p.ncam));int remove=-1;
   for(int i=0;i<(int)groups.size();++i)for(int k=0;k<groups[i].n;++k)if(mult[3*i+k]>worst){worst=mult[3*i+k];for(int o:act)if(pi[o]==groups[i].point&&ci[o]==groups[i].cam[k])remove=o;}
   if(remove>=0){act.erase(std::find(act.begin(),act.end(),remove));continue;}auditFeasibility();return true;
  }throw std::runtime_error("active_iteration_cap");
 }
};

inline void opening(const DeviceProblem& p,DeviceState& s,int count,const std::function<bool()>& expired){
 auto start=std::chrono::steady_clock::now();double initial=ComputeCost(p,s,0,0),cost=initial;int accepted=0;std::string stop="schedule_complete";
 std::printf("O1_INIT k=%d l2=%.17g\n",count,cost);
 {Solver a(p,s);Buf oldR(9*p.ncam),oldt(3*p.ncam),oldX(3*p.npt),oldI(3*p.ncam);
 for(int k=0;k<count;++k){if(expired()){stop="opening_budget";break;}a.copy(oldR.p,s.R,9*p.ncam);a.copy(oldt.p,s.t,3*p.ncam);a.copy(oldX.p,s.X,3*p.npt);a.copy(oldI.p,s.intr,3*p.ncam);double candidate=cost,surrogate0=-1,surrogate1=-1;bool ok=false;int reverted=0;a.products=a.iterations=0;
  try{a.initializeRays();reverted=a.rotation();a.intrinsics();a.assembleBlocks();surrogate0=a.surrogateCost();a.qp(expired);apply<<<a.grid(3*p.ncam),256>>>(3*p.ncam,s.t,a.tc.p);apply<<<a.grid(3*p.npt),256>>>(3*p.npt,s.X,a.xc.p);surrogate1=a.surrogateCost();candidate=ComputeCost(p,s,0,0);ok=std::isfinite(candidate)&&candidate<cost&&!expired();if(!ok)stop=expired()?"opening_budget":"true_cost_rejection";}
  catch(const std::runtime_error& e){stop=e.what();}
  std::printf("O1_SWEEP sweep=%d old_l2=%.17g candidate_l2=%.17g accepted=%d active=%zu products=%d pcg=%d schur_residual=%.17g point_residual=%.17g rotation_reverts=%d reason=%s\n",k,cost,candidate,(int)ok,a.act.size(),a.products,a.iterations,a.linearResidual,a.pointResidualNorm,reverted,ok?"accepted":stop.c_str());
  std::printf("O1_QP sweep=%d surrogate_before=%.17g surrogate_after=%.17g feasibility_residual=%.17g\n",k,surrogate0,surrogate1,a.feasibilityResidual);
  if(ok){cost=candidate;++accepted;}else{a.copy(s.R,oldR.p,9*p.ncam);a.copy(s.t,oldt.p,3*p.ncam);a.copy(s.X,oldX.p,3*p.npt);a.copy(s.intr,oldI.p,3*p.ncam);break;}
 }}
 double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();std::printf("O1_FINAL k=%d accepted=%d l2=%.17g seconds=%.9f complete=%d reason=%s\n",count,accepted,cost,seconds,(int)(accepted==count),stop.c_str());
}
} // namespace O1
