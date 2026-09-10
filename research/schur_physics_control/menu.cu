// Reuse the identical captured operator and PCG implementation for every arm.
#define PRISM_FIXED_LIBRARY
#include "fixed.cu"
#include "point_factor.cuh"
__global__ void rhs_add(int n,const double*bc,const double*E,double*b){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)b[i]=(b[i]+bc[i])*E[i];}
__global__ void spectral_transform(int np,const double*F,const double*x,double*y){int p=blockIdx.x*blockDim.x+threadIdx.x;if(p<np)for(int j=0;j<3;++j){double v=0;for(int i=0;i<3;++i)v+=F[9ul*p+3*i+j]*x[3ul*p+i];y[3ul*p+j]=v;}}
__global__ void spectral_weight(size_t size,int rows,const double*eig,double tau,const double*x,double*y){size_t i=size_t(blockIdx.x)*blockDim.x+threadIdx.x;if(i<size)y[i]=x[i]/(eig[i%rows]+tau);}
__global__ void camera_product(int nc,const double*U,const double*E,const double*x,double*y){int c=blockIdx.x*blockDim.x+threadIdx.x;if(c<nc)for(int i=0;i<9;++i){double v=0;for(int j=0;j<9;++j)v+=U[81ul*c+9*i+j]*E[9*c+j]*x[9*c+j];y[9*c+i]=E[9*c+i]*v;}}
struct Family {
 System&s;double *R0,*diag,*bc,*bp,*F,*eig,*point_b;int*ok;
 Family(System&sys,std::string path):s(sys){path+="/";R0=load<double>(path+"R0",6ul*s.np);diag=load<double>(path+"Cdiag",3ul*s.np);bc=load<double>(path+"bc",s.n);bp=load<double>(path+"bp",3ul*s.np);F=load<double>(path+"spectral_F",9ul*s.np);eig=load<double>(path+"spectral_values",3ul*s.np);ok=alloc<int>(s.np);point_b=alloc<double>(3ul*s.np);}
 ~Family(){for(auto x:{R0,diag,bc,bp,F,eig,point_b})cudaFree(x);cudaFree(ok);}
 void Set(double lambda){s.sig=lambda;MFPointFactorTau<<<(s.np+255)/256,256>>>(diag,R0,lambda,s.np,s.R,ok);
  MFVinvApply<<<(s.np+255)/256,256>>>(s.R,bp,s.np,s.u);CK(cudaMemset(s.v,0,s.n*8ul));
  MFPass2<9,float><<<s.nc,256>>>(s.W,s.pt,s.off,s.u,s.U,s.v,s.no,s.b);rhs_add<<<(s.n+255)/256,256>>>(s.n,bc,s.E,s.b);
 }
};
int main(int argc,char**argv){
 if(argc<2||argc>3)return 2;System s(argv[1]);double center=s.sig;
 double cpu_ms=argc==3?atof(argv[2]):0;Family family(s,argv[1]);
 cublasHandle_t h;PrismCoarse::blas(cublasCreate(&h));double one=1,zero=0,minus=-1;
 auto dot=[&](const double*a,const double*b,int n){double v;PrismCoarse::blas(cublasDdot(h,n,a,1,b,1,&v));return v;};
 std::vector<double> saved_b(s.n);CK(cudaMemcpy(saved_b.data(),s.b,s.n*8ul,cudaMemcpyDeviceToHost));family.Set(center);
 std::vector<double> rebuilt_b(s.n);CK(cudaMemcpy(rebuilt_b.data(),s.b,s.n*8ul,cudaMemcpyDeviceToHost));
 double err=0,norm=0;for(int i=0;i<s.n;++i){double d=rebuilt_b[i]-saved_b[i];err+=d*d;norm+=saved_b[i]*saved_b[i];}
 printf("MENU_CENTER_PARITY rhs_relative=%.17g\n",sqrt(err/norm));if(sqrt(err/norm)>1e-9)throw std::runtime_error("center RHS mismatch");
 int repetitions=getenv("PRISM_MENU_REPS")?atoi(getenv("PRISM_MENU_REPS")):3;
 for(int rep=-1;rep<repetitions;++rep)for(int a=0;a<3;++a){int ranks[3]={0,8,16};int rank=ranks[(a+std::max(rep,0))%3];
  if(rank==0){Timer all;all.Start();int hits=0,products=0;double center_ms=0;
   for(double factor:{.25,.5,1.,2.,4.}){Timer t;t.Start();family.Set(center*factor);s.Prepare();double prep=t.End();auto r=Solve(s,h,nullptr,false);hits+=r.hit;products+=r.products;
    if(factor==1)center_ms=prep+r.ms;
    if(rep>=0)printf("MENU_MEMBER rep=%d rank=0 factor=%.9g hit=%d residual=%.17g iterations=%d products=%d ms=%.9g negative=%d\n",rep,factor,r.hit,r.relative,r.iterations,r.products,prep+r.ms,r.negative);
   }
   double total=all.End();if(rep>=0)printf("MENU_TOTAL rep=%d rank=0 hits=%d members=5 gpu_host_ms=%.9g charged_ms=%.9g products=%d single_center_ms=%.9g\n",rep,hits,total,total,products,center_ms);fflush(stdout);continue;
  }
  Timer all;all.Start();PrismCoarse coarse(s.n,rank);
  auto anchor=alloc<double>(s.n),x=alloc<double>(s.n),ap=alloc<double>(s.n);
  family.Set(center);s.Prepare();auto seed=Solve(s,h,&coarse,true,anchor);
  coarse.Prepare(h,[&](const double*u,double*v){s.Apply(u,v);},0);
  int m=std::max(1,coarse.used);double anchor_norm=sqrt(dot(anchor,anchor,s.n));
  if(!(anchor_norm>0))throw std::runtime_error("no center direction");
  CK(cudaMemcpy(coarse.Z+size_t(m-1)*s.n,anchor,s.n*8ul,cudaMemcpyDeviceToDevice));double scale=1/anchor_norm;
  cublasDscal(h,s.n,&scale,coarse.Z+size_t(m-1)*s.n,1);
  // Preserve the center solve as an anchor; other columns are current Ritz modes.
  Eigen::MatrixXd gram=coarse.Gram(h,coarse.Z,coarse.Z,m);
  for(int j=0;j<m;++j)camera_product<<<(s.nc+255)/256,256>>>(s.nc,s.U,s.E,coarse.Z+size_t(j)*s.n,coarse.AZ+size_t(j)*s.n);
  Eigen::MatrixXd B=coarse.Gram(h,coarse.Z,coarse.AZ,m);
  scaled<<<(s.n+255)/256,256>>>(s.n,family.bc,s.E,s.v);
  cublasDgemv(h,CUBLAS_OP_T,s.n,m,&one,coarse.Z,s.n,s.v,1,&zero,coarse.dotbuf,1);
  Eigen::VectorXd h0(m);CK(cudaMemcpy(h0.data(),coarse.dotbuf,m*8ul,cudaMemcpyDeviceToHost));
  int rows=3*s.np;size_t entries=size_t(rows)*m;
  auto A=alloc<double>(entries),weighted=alloc<double>(entries),wb=alloc<double>(rows);
  for(int j=0;j<m;++j){
   scaled<<<(s.n+255)/256,256>>>(s.n,coarse.Z+size_t(j)*s.n,s.E,s.v);CK(cudaMemset(s.t,0,rows*8ul));
   MFPass1<9,float><<<(s.no+255)/256,256>>>(s.W,s.cam,s.pt,s.v,s.no,s.t);
   spectral_transform<<<(s.np+255)/256,256>>>(s.np,family.F,s.t,A+size_t(j)*rows);
  }
  spectral_transform<<<(s.np+255)/256,256>>>(s.np,family.F,family.bp,family.point_b);
  double setup=all.End();Timer candidates;candidates.Start();int hits=0,anchor_hits=0;
  for(double factor:{.25,.5,1.,2.,4.}){
   double lambda=center*factor;spectral_weight<<<(entries+255)/256,256>>>(entries,rows,family.eig,lambda,A,weighted);
   spectral_weight<<<(rows+255)/256,256>>>(rows,rows,family.eig,lambda,family.point_b,wb);
   cublasDgemm(h,CUBLAS_OP_T,CUBLAS_OP_N,m,m,rows,&one,A,rows,weighted,rows,&zero,coarse.dense,m);
   Eigen::MatrixXd correction(m,m);CK(cudaMemcpy(correction.data(),coarse.dense,size_t(m)*m*8,cudaMemcpyDeviceToHost));
   cublasDgemv(h,CUBLAS_OP_T,rows,m,&one,A,rows,wb,1,&zero,coarse.dotbuf,1);
   Eigen::VectorXd hcorr(m);CK(cudaMemcpy(hcorr.data(),coarse.dotbuf,m*8ul,cudaMemcpyDeviceToHost));
   Eigen::MatrixXd T=B+lambda*gram-correction;T=.5*(T+T.transpose()).eval();Eigen::VectorXd rhs=h0-hcorr;
   Eigen::LLT<Eigen::MatrixXd> llt(T);bool spd=llt.info()==Eigen::Success;
   double relative=INFINITY,model_error=INFINITY,rhs_error=INFINITY;
   if(spd){Eigen::VectorXd y=llt.solve(rhs);spd=y.allFinite();if(spd){
    CK(cudaMemcpy(coarse.coeff,y.data(),m*8ul,cudaMemcpyHostToDevice));
    cublasDgemv(h,CUBLAS_OP_N,s.n,m,&one,coarse.Z,s.n,coarse.coeff,1,&zero,x,1);
    family.Set(lambda);s.Apply(x,ap);
    cublasDgemv(h,CUBLAS_OP_T,s.n,m,&one,coarse.Z,s.n,ap,1,&zero,coarse.dotbuf,1);
    Eigen::VectorXd true_projected(m);CK(cudaMemcpy(true_projected.data(),coarse.dotbuf,m*8ul,cudaMemcpyDeviceToHost));
    model_error=(true_projected-T*y).norm()/std::max(1e-300,(T*y).norm());
    cublasDgemv(h,CUBLAS_OP_T,s.n,m,&one,coarse.Z,s.n,s.b,1,&zero,coarse.dotbuf,1);
    Eigen::VectorXd true_rhs(m);CK(cudaMemcpy(true_rhs.data(),coarse.dotbuf,m*8ul,cudaMemcpyDeviceToHost));rhs_error=(true_rhs-rhs).norm()/std::max(1e-300,rhs.norm());
    cublasDaxpy(h,s.n,&minus,s.b,1,ap,1);relative=sqrt(dot(ap,ap,s.n)/dot(s.b,s.b,s.n));
   }}
   bool hit=spd&&std::isfinite(relative)&&relative<=s.eta;hits+=hit;
   // An optional center-only fallback is disclosed separately, not counted as
   // a successful projected member or a complete five-member residual gate.
   if(factor==1&&seed.hit)++anchor_hits;
   if(rep>=0)printf("MENU_MEMBER rep=%d rank=%d used=%d factor=%.9g hit=%d residual=%.17g projected_spd=%d model_relative=%.17g rhs_relative=%.17g\n",rep,rank,m,factor,hit,relative,spd,model_error,rhs_error);
  }
  double candidate_ms=candidates.End();
  for(auto p:{anchor,x,ap,A,weighted,wb})cudaFree(p);
  if(rep>=0)printf("MENU_TOTAL rep=%d rank=%d used=%d hits=%d members=5 gpu_host_ms=%.9g cpu_point_setup_ms=%.9g charged_ms=%.9g setup_ms=%.9g candidate_ms=%.9g seed_iterations=%d seed_hit=%d center_fallback_available=%d\n",rep,rank,m,hits,setup+candidate_ms,cpu_ms,setup+candidate_ms+cpu_ms,setup,candidate_ms,seed.iterations,seed.hit,anchor_hits);
  fflush(stdout);
 }
 cublasDestroy(h);
}
