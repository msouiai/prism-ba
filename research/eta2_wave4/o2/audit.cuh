#pragma once
// Tiny-only diagnostics, never enabled in a timed cohort. CPU checks use the
// separately finite-difference-verified host primitive. GPU outputs come from
// the actual production assembly/factor/model/mask kernels.
template<class T> std::vector<T> O2Copy(const T* ptr,size_t n){
  std::vector<T> v(n);CUDA_CHECK(cudaMemcpy(v.data(),ptr,n*sizeof(T),cudaMemcpyDeviceToHost));return v;
}
static double O2Relative(const std::vector<double>& a,const std::vector<double>& b){
  double err=0,den=0;for(size_t i=0;i<a.size();++i){err+=(a[i]-b[i])*(a[i]-b[i]);den+=b[i]*b[i];}
  return std::sqrt(err/std::max(den,1e-300));
}
static void O2AuditAssembly(const DeviceProblem& p,const DeviceState& state,
 const O2Runtime& runtime,const double* Hcc,const double* Cdiag,const float* Gp,
 const float* Bo,const double* bc,const double* bp,const int* o2slot){
  if(!getenv("OCA_O2_AUDIT"))return;
  if(p.nobs>2000 || p.ncam>20)throw std::runtime_error("O2 audit restricted to tiny inputs");
  static bool seen[6]={};if(seen[runtime.index])return;seen[runtime.index]=true;
  const int nc=p.ncam,np=p.npt,no=p.nobs,n=9*nc+3*np;
  auto R=O2Copy(state.R,9*nc),t=O2Copy(state.t,3*nc),X=O2Copy(state.X,3*np),uv=O2Copy(p.uv,2*no);
  auto f=O2Copy(INTR_F(p,state),nc),k1=O2Copy(INTR_K1(p,state),nc),k2=O2Copy(INTR_K2(p,state),nc);
  auto ci=O2Copy(p.cam_idx,no),pi=O2Copy(p.pt_idx,no),slot=O2Copy(o2slot,no);
  auto depth=O2Copy(runtime.depth,no);
  std::vector<double> hc(81*nc),cd(3*np),gc(9*nc),gp(3*np),cross(27*no),rows(6*no),r2sum(nc),counts(nc);
  std::vector<double> direction(n);for(int j=0;j<n;++j)direction[j]=.01*std::sin(.7*(j+1));
  for(int c=0;c<nc;++c){for(int j=0;j<3;++j)direction[9*c+j]*=.01;direction[9*c+6]*=10;direction[9*c+8]=0;}
  double cost=0,gd=0,jj=0;
  for(int o=0;o<no;++o){int c=ci[o],p0=pi[o];double gx[12],gy[12],rx,ry;
    o2::ResidualGrad12(R.data()+9*c,t.data()+3*c,X.data()+3*p0,f[c],k1[c],k2[c],uv[2*o],uv[2*o+1],depth[o],O2Runtime::Stage(runtime.index),gx,gy,&rx,&ry);
    gx[8]=gy[8]=0;cost+=.5*(rx*rx+ry*ry);
    double jx=0,jy=0;for(int j=0;j<12;++j){double d=direction[j<9?9*c+j:9*nc+3*p0+j-9];jx+=gx[j]*d;jy+=gy[j]*d;}
    gd+=rx*jx+ry*jy;jj+=jx*jx+jy*jy;
    for(int j=0;j<9;++j){gc[9*c+j]+=rx*gx[j]+ry*gy[j];
      for(int k=0;k<9;++k)hc[81*c+9*j+k]+=gx[j]*gx[k]+gy[j]*gy[k];
      for(int k=0;k<3;++k)cross[(3*j+k)*no+slot[o]]=float(gx[j]*gx[9+k]+gy[j]*gy[9+k]);}
    for(int j=0;j<3;++j){gp[3*p0+j]+=rx*gx[9+j]+ry*gy[9+j];cd[3*p0+j]+=gx[9+j]*gx[9+j]+gy[9+j]*gy[9+j];
      rows[6*o+j]=float(gx[9+j]);rows[6*o+3+j]=float(gy[9+j]);}
  }
  auto hc_gpu=O2Copy(Hcc,81*nc),cd_gpu=O2Copy(Cdiag,3*np),gc_gpu=O2Copy(bc,9*nc),gp_gpu=O2Copy(bp,3*np);
  auto cross_f=O2Copy(Gp,27*no),rows_f=O2Copy(Bo,6*no);
  std::vector<double> cross_gpu(cross_f.begin(),cross_f.end()),rows_gpu(rows_f.begin(),rows_f.end());
  double errors[6]={O2Relative(hc_gpu,hc),O2Relative(cd_gpu,cd),O2Relative(gc_gpu,gc),O2Relative(gp_gpu,gp),O2Relative(cross_gpu,cross),O2Relative(rows_gpu,rows)};
  for(double e:errors)if(!(e<2e-6))throw std::runtime_error("O2 stage assembly reference mismatch");
  double native_cost=ComputeCost(p,state);double cost_error=std::abs(native_cost-cost)/std::max(1.,std::abs(cost));
  if(!(cost_error<1e-10))throw std::runtime_error("O2 stage cost mismatch");
  double* d=nullptr;CUDA_CHECK(cudaMalloc(&d,n*sizeof(double)));CUDA_CHECK(cudaMemcpy(d,direction.data(),n*sizeof(double),cudaMemcpyHostToDevice));
  PrismFullModel model;auto m=model.Evaluate(p,state,d,0);
  double model_error=std::max(std::abs(m.slope-gd)/std::max(1.,std::abs(gd)),std::abs(m.curvature-jj)/std::max(1.,std::abs(jj)));
  if(!(model_error<1e-10))throw std::runtime_error("O2 joint full model mismatch");
  double* factor=nullptr;double* u=nullptr;int* ok=nullptr;
  CUDA_CHECK(cudaMalloc(&factor,6*np*sizeof(double)));CUDA_CHECK(cudaMalloc(&u,3*np*sizeof(double)));CUDA_CHECK(cudaMalloc(&ok,np*sizeof(int)));
  MFPointFactor<float><<<GridSize(np),256>>>(Bo,Cdiag,p.point_obs_offsets,p.point_obs_list,.1,np,factor,ok);
  MFVinvApply<<<GridSize(np),256>>>(factor,bp,np,u);auto solved=O2Copy(u,3*np);
  std::vector<double> applied(3*np);
  for(int o=0;o<no;++o){int q=pi[o];for(int row=0;row<2;++row){double dot=0;for(int j=0;j<3;++j)dot+=rows_gpu[6*o+3*row+j]*solved[3*q+j];
    for(int j=0;j<3;++j)applied[3*q+j]+=rows_gpu[6*o+3*row+j]*dot;}}
  for(int q=0;q<np;++q){double floor=.1*(cd_gpu[3*q]+cd_gpu[3*q+1]+cd_gpu[3*q+2])/3.;if(!(floor>0))floor=1e-32;
    for(int j=0;j<3;++j)applied[3*q+j]+=std::max(.1*cd_gpu[3*q+j],1e-3*floor)*solved[3*q+j];}
  double point_error=O2Relative(applied,gp_gpu);if(!(point_error<1e-8))throw std::runtime_error("O2 point normal solve mismatch");
  DeviceState trial;AllocState(trial,nc,np,true);RetractDof9(p,state,d,trial);
  auto tr=O2Copy(trial.R,9*nc),tt=O2Copy(trial.t,3*nc),tx=O2Copy(trial.X,3*np);
  auto tf=O2Copy(INTR_F(p,trial),nc),tk1=O2Copy(INTR_K1(p,trial),nc),tk2=O2Copy(INTR_K2(p,trial),nc);
  std::vector<double> keep(np),move(np);
  for(int o=0;o<no;++o){int c=ci[o],q=pi[o];for(int arm=0;arm<2;++arm){const double* x=(arm?tx:X).data()+3*q;double y[3],pix[2];
    for(int j=0;j<3;++j)y[j]=tr[9*c+3*j]*x[0]+tr[9*c+3*j+1]*x[1]+tr[9*c+3*j+2]*x[2]+tt[3*c+j];
    o2::Projection(y,tf[c],tk1[c],tk2[c],depth[o],O2Runtime::Stage(runtime.index),pix);
    double a=pix[0]-uv[2*o],b=pix[1]-uv[2*o+1];(arm?move:keep)[q]+=.5*(a*a+b*b);}}
  PrismPointSafeguard safeguard;auto frozen=safeguard.Choose(p,state,trial,d);auto chosen=O2Copy(d,n);
  unsigned long long expected_frozen=0;for(int q=0;q<np;++q){bool freeze=keep[q]<move[q];expected_frozen+=freeze;
    for(int j=0;j<3;++j)if(chosen[9*nc+3*q+j]!=(freeze?0.:direction[9*nc+3*q+j]))throw std::runtime_error("O2 per-point mask mismatch");}
  if(frozen!=expected_frozen)throw std::runtime_error("O2 mask count mismatch");
  cudaFree(trial.R);cudaFree(trial.t);cudaFree(trial.X);cudaFree(trial.intr);
  cudaFree(d);cudaFree(factor);cudaFree(u);cudaFree(ok);
  std::printf("O2_AUDIT stage=%.17g cost_rel=%.17g Hcc_rel=%.17g Cdiag_rel=%.17g bc_rel=%.17g bp_rel=%.17g cross_rel=%.17g rows_rel=%.17g model_rel=%.17g point_solve_rel=%.17g mask_frozen=%llu passed=1\n",
    O2Runtime::Stage(runtime.index),cost_error,errors[0],errors[1],errors[2],errors[3],errors[4],errors[5],model_error,point_error,frozen);
}
