// Brief 0: diagnostic-only FP64 Jacobian operator. No production path changes.
__global__ void B0Rows(const int* ci,const int* pi,const int* slot,const double* uv,
    const double* R,const double* t,const double* X,const double* f,const double* k1,
    const double* k2,int no,double* Jc,double* Jp,double* residual,int* order){
  int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=no)return;
  int c=ci[o],j=pi[o],a=slot[o];const double* r=R+9*c;const double* x=X+3*j;
  double gx[12],gy[12],rx,ry;
  BalResidualGrad12(r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7],r[8],
    t[3*c],t[3*c+1],t[3*c+2],x[0],x[1],x[2],f[c],k1[c],k2[c],uv[2*o],uv[2*o+1],gx,gy,&rx,&ry);
  gx[8]=gy[8]=0;
  for(int k=0;k<9;++k){Jc[18ul*a+k]=gx[k];Jc[18ul*a+9+k]=gy[k];}
  for(int k=0;k<3;++k){Jp[6ul*o+k]=gx[k+9];Jp[6ul*o+3+k]=gy[k+9];}
  residual[2ul*o]=rx;residual[2ul*o+1]=ry;order[a]=o;
}
__global__ void B0Forward(const int* ci,const int* slot,const double* Jc,
    const double* E,const double* x,int no,double* y){
  int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=no)return;int c=ci[o],a=slot[o];
  double u=0,v=0;for(int k=0;k<9;++k){double t=E[9*c+k]*x[9*c+k];u+=Jc[18ul*a+k]*t;v+=Jc[18ul*a+9+k]*t;}
  y[2ul*o]=u;y[2ul*o+1]=v;
}
__global__ void B0PointRhs(const int* offsets,const int* order,const double* Jp,
    const double* y,int np,double* g){
  int lane=threadIdx.x%32,j=(blockIdx.x*blockDim.x+threadIdx.x)/32;if(j>=np)return;
  double v[3]={};for(int a=offsets[j]+lane;a<offsets[j+1];a+=32){int o=order[a];
    for(int k=0;k<3;++k)v[k]+=Jp[6ul*o+k]*y[2ul*o]+Jp[6ul*o+3+k]*y[2ul*o+1];}
  for(int s=16;s;s/=2)for(int k=0;k<3;++k)v[k]+=__shfl_down_sync(0xffffffff,v[k],s);
  if(lane==0)for(int k=0;k<3;++k)g[3*j+k]=v[k];
}
__global__ void B0Prior(const double* f,const double* r2,const double* count,int nc,double* Q){
  int c=blockIdx.x*blockDim.x+threadIdx.x;if(c>=nc)return;
  for(int k=0;k<9;++k)Q[9*c+k]=0;
  if(count[c]>0){double m=fmax(r2[c]/count[c],1e-12),sf=.5*fabs(f[c])+1e-3;
    Q[9*c+6]=1/(sf*sf);Q[9*c+7]=m*m;}
}
__global__ void B0Adjoint(const int* offsets,const int* order,const int* pi,
    const double* Jc,const double* Jp,const double* y,const double* u,
    const double* E,const double* Q,const double* x,double lambda,int nc,double* out){
  int c=blockIdx.x;if(c>=nc)return;double v[9]={};
  for(int a=offsets[c]+threadIdx.x;a<offsets[c+1];a+=blockDim.x){int o=order[a],j=pi[o];
    double rx=y[2ul*o],ry=y[2ul*o+1];for(int k=0;k<3;++k){rx-=Jp[6ul*o+k]*u[3*j+k];ry-=Jp[6ul*o+3+k]*u[3*j+k];}
    for(int k=0;k<9;++k)v[k]+=Jc[18ul*a+k]*rx+Jc[18ul*a+9+k]*ry;
  }
  __shared__ double sum[9][256];for(int k=0;k<9;++k)sum[k][threadIdx.x]=v[k];__syncthreads();
  for(int s=128;s;s/=2){if(threadIdx.x<s)for(int k=0;k<9;++k)sum[k][threadIdx.x]+=sum[k][threadIdx.x+s];__syncthreads();}
  if(threadIdx.x<9){int k=threadIdx.x,a=9*c+k;out[a]=E[a]*sum[k][0]+(x?(lambda+E[a]*E[a]*Q[a])*x[a]:0);}
}
__global__ void B0Compose(const double* x,const double* E,const double* xp,int nc,int np,double* d){
  int a=blockIdx.x*blockDim.x+threadIdx.x;
  if(a<9*nc)d[a]=-E[a]*x[a];if(a<3*np)d[9ul*nc+a]=-xp[a];
}
struct Brief0Reference {
  const DeviceProblem& p;int nc,np,no,nc9,np3;double lambda;const double* E;
  double *Jc,*Jp,*residual,*Q,*R,*Rtmp,*gp,*y,*g,*u,*rhs,*x,*r,*v,*Ap,*true_r,*scaled,*point,*step;
  int* order;int* ok;std::vector<double*> allocations;
  double* New(size_t n){double* a=nullptr;CUDA_CHECK(cudaMalloc(&a,8*n));allocations.push_back(a);return a;}
  Brief0Reference(const DeviceProblem& problem,const DeviceState& s,const double* scaling,
      const double* Cdiag,const double* r2,const double* counts,double lam):p(problem),nc(p.ncam),np(p.npt),no(p.nobs),nc9(9*nc),np3(3*np),lambda(lam),E(scaling){
    Jc=New(18ul*no);Jp=New(6ul*no);residual=New(2ul*no);Q=New(nc9);R=New(6ul*np);Rtmp=New(6ul*np);
    gp=New(np3);y=New(2ul*no);g=New(np3);u=New(np3);point=New(np3);step=New(nc9+np3);
    rhs=New(nc9);x=New(nc9);r=New(nc9);v=New(nc9);Ap=New(nc9);true_r=New(nc9);scaled=New(nc9);
    CUDA_CHECK(cudaMalloc(&order,4ul*no));CUDA_CHECK(cudaMalloc(&ok,4ul*np));
    B0Rows<<<GridSize(no),256>>>(p.cam_idx,p.pt_idx,p.obs2cslot,p.uv,s.R,s.t,s.X,
      INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),no,Jc,Jp,residual,order);
    B0Prior<<<GridSize(nc),256>>>(INTR_F(p,s),r2,counts,nc,Q);
    MFPointFactorObs<double><<<GridSize(np),256>>>(Jp,p.point_obs_offsets,p.point_obs_list,np,Rtmp);
    CUDA_CHECK(cudaMemset(ok,0,4ul*np));
    MFPointFactorTau<<<GridSize(np),256>>>(Cdiag,Rtmp,lambda,np,R,ok);
    B0PointRhs<<<(np+7)/8,256>>>(p.point_obs_offsets,p.point_obs_list,Jp,residual,np,gp);
    MFVinvApply<<<GridSize(np),256>>>(R,gp,np,u);
    B0Adjoint<<<nc,256>>>(p.mf_coff,order,p.pt_idx,Jc,Jp,residual,u,E,Q,nullptr,0,nc,rhs);
  }
  ~Brief0Reference(){for(auto a:allocations)cudaFree(a);cudaFree(order);cudaFree(ok);}
  void Product(const double* a,double* out){
    B0Forward<<<GridSize(no),256>>>(p.cam_idx,p.obs2cslot,Jc,E,a,no,y);
    B0PointRhs<<<(np+7)/8,256>>>(p.point_obs_offsets,p.point_obs_list,Jp,y,np,g);
    MFVinvApply<<<GridSize(np),256>>>(R,g,np,u);
    B0Adjoint<<<nc,256>>>(p.mf_coff,order,p.pt_idx,Jc,Jp,y,u,E,Q,a,lambda,nc,out);
  }
  struct SolveResult {int iterations=0,restarts=0;double recursive=1,true_relative=1,seconds=0,min_rayleigh=INFINITY;bool certified=false;std::string reason="cap";};
  SolveResult Solve(cublasHandle_t blas,PrismPcg& M,const std::string& path){
    using Clock=std::chrono::steady_clock;auto begin=Clock::now();SolveResult ans;
    auto elapsed=[&](){return std::chrono::duration<double>(Clock::now()-begin).count();};
    std::ofstream trace(path);trace.precision(17);trace<<"iteration,recursive_relative,true_relative,pAp,seconds\n";
    CUDA_CHECK(cudaMemset(x,0,8ul*nc9));CUDA_CHECK(cudaMemcpy(r,rhs,8ul*nc9,cudaMemcpyDeviceToDevice));
    double nb=0,rz=0;cublasDnrm2(blas,nc9,rhs,1,&nb);
    if(nb==0){ans.certified=true;ans.reason="zero_rhs";ans.recursive=ans.true_relative=0;return ans;}
    M.Apply(r);cublasDdot(blas,nc9,r,1,M.z,1,&rz);CUDA_CHECK(cudaMemcpy(v,M.z,8ul*nc9,cudaMemcpyDeviceToDevice));
    for(int it=0;it<20000;++it){
      Product(v,Ap);double pAp=0,pp=0;cublasDdot(blas,nc9,v,1,Ap,1,&pAp);cublasDdot(blas,nc9,v,1,v,1,&pp);
      ans.min_rayleigh=std::min(ans.min_rayleigh,pAp/pp);
      if(!(pAp>0&&rz>0&&std::isfinite(pAp)&&std::isfinite(rz))){ans.reason="nonpositive_or_nonfinite";break;}
      double alpha=rz/pAp,minus=-alpha;cublasDaxpy(blas,nc9,&alpha,v,1,x,1);cublasDaxpy(blas,nc9,&minus,Ap,1,r,1);
      double nr=0;cublasDnrm2(blas,nc9,r,1,&nr);ans.recursive=nr/nb;ans.iterations=it+1;
      bool refresh=ans.recursive<=1e-10||(it+1)%128==0;
      if(refresh){
        Product(x,Ap);CUDA_CHECK(cudaMemcpy(true_r,rhs,8ul*nc9,cudaMemcpyDeviceToDevice));double m=-1;
        cublasDaxpy(blas,nc9,&m,Ap,1,true_r,1);cublasDnrm2(blas,nc9,true_r,1,&nr);ans.true_relative=nr/nb;
        trace<<it+1<<","<<ans.recursive<<","<<ans.true_relative<<","<<pAp<<","<<elapsed()<<"\n";
        if(ans.true_relative<=1e-10){ans.certified=true;ans.reason="true_residual";break;}
        CUDA_CHECK(cudaMemcpy(r,true_r,8ul*nc9,cudaMemcpyDeviceToDevice));M.Apply(r);
        cublasDdot(blas,nc9,r,1,M.z,1,&rz);CUDA_CHECK(cudaMemcpy(v,M.z,8ul*nc9,cudaMemcpyDeviceToDevice));++ans.restarts;
      }else{
        M.Apply(r);double next=0;cublasDdot(blas,nc9,r,1,M.z,1,&next);double beta=next/rz,one=1;
        cublasDscal(blas,nc9,&beta,v,1);cublasDaxpy(blas,nc9,&one,M.z,1,v,1);rz=next;
      }
      if((it+1)%32==0&&elapsed()>180){ans.reason="time_cap";break;}
    }
    Product(x,Ap);CUDA_CHECK(cudaMemcpy(true_r,rhs,8ul*nc9,cudaMemcpyDeviceToDevice));double m=-1,nr=0;
    cublasDaxpy(blas,nc9,&m,Ap,1,true_r,1);cublasDnrm2(blas,nc9,true_r,1,&nr);ans.true_relative=nr/nb;
    ans.certified=ans.true_relative<=1e-10;ans.seconds=elapsed();return ans;
  }
  double* Compose(cublasHandle_t blas,double radius){
    CUDA_CHECK(cudaMemcpy(scaled,x,8ul*nc9,cudaMemcpyDeviceToDevice));double norm=0;cublasDnrm2(blas,nc9,x,1,&norm);
    if(radius>0&&norm>radius){double a=radius/norm;cublasDscal(blas,nc9,&a,scaled,1);}
    B0Forward<<<GridSize(no),256>>>(p.cam_idx,p.obs2cslot,Jc,E,scaled,no,y);
    B0PointRhs<<<(np+7)/8,256>>>(p.point_obs_offsets,p.point_obs_list,Jp,y,np,g);
    MFBackSub<<<GridSize(np),256>>>(R,gp,g,np,point);
    B0Compose<<<GridSize(std::max(nc9,np3)),256>>>(scaled,E,point,nc,np,step);return step;
  }
};
