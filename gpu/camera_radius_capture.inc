// Isolated instrumentation. No candidate/controller feedback to the owner.
if(camera_tr && getenv("OCA_RADIUS_CAPTURE") && (k==0||k==3||k==6) && !radius_captured[k]){
 radius_captured[k]=true;
 if(CD!=9||mf_fp32||shared_intr)throw std::runtime_error("radius capture requires plain unshared FP64 CD9");
 const std::string stem=std::string(getenv("OCA_RADIUS_CAPTURE"))+"-o"+std::to_string(k);
 auto stamp=[](){CUDA_CHECK(cudaDeviceSynchronize());return std::chrono::steady_clock::now();};
 auto elapsed=[](auto t){CUDA_CHECK(cudaDeviceSynchronize());return std::chrono::duration<double>(std::chrono::steady_clock::now()-t).count();};
 auto export_state=[&](const DeviceState& state,const std::string& path){
  FILE* f=std::fopen(path.c_str(),"wb");if(!f)throw std::runtime_error("capture export failed");
  std::fwrite("PRISMS01",1,8,f);uint64_t dims[]={uint64_t(ncam),uint64_t(npt),uint64_t(nobs)};std::fwrite(dims,8,3,f);
  auto out=[&](const double* ptr,size_t size){std::vector<double> v(size);CUDA_CHECK(cudaMemcpy(v.data(),ptr,size*8,cudaMemcpyDeviceToHost));if(std::fwrite(v.data(),8,size,f)!=size)throw std::runtime_error("capture write failed");};
  out(state.R,9ul*ncam);out(state.t,3ul*ncam);out(state.X,3ul*npt);out(state.intr,3ul*ncam);std::fclose(f);
 };
 export_state(s,stem+"-base.state");
 auto start=stamp();
 prism_recycle::Basis basis(n_c,64);basis.Reset(blas,bprime);basis.Grow(blas,KvS,64);
 const int m=basis.m;if(!m)throw std::runtime_error("Empty capture basis");
 Eigen::MatrixXd H(m,m);for(int i=0;i<m;++i)for(int j=0;j<m;++j)H(i,j)=basis.H[i*64+j];
 Eigen::VectorXd rhs=Eigen::VectorXd::Zero(m);rhs[0]=basis.norm;
 PrismProjectedRadius projected(H,rhs);
 double *z,*ax,*step;CUDA_CHECK(cudaMalloc(&z,n_c*8));CUDA_CHECK(cudaMalloc(&ax,n_c*8));CUDA_CHECK(cudaMalloc(&step,n*8));
 const double common=elapsed(start);
 // Validation/export are deliberately outside common candidate construction timing.
 std::vector<double> hostq(size_t(n_c)*m);CUDA_CHECK(cudaMemcpy(hostq.data(),basis.q,hostq.size()*8,cudaMemcpyDeviceToHost));
 Eigen::Map<Eigen::Matrix<double,Eigen::Dynamic,Eigen::Dynamic,Eigen::ColMajor>> Q(hostq.data(),n_c,m);
 const double gram=(Q.transpose()*Q-Eigen::MatrixXd::Identity(m,m)).cwiseAbs().maxCoeff();
 {std::ofstream f(stem+"-projected.txt");f.precision(17);f<<m<<" "<<basis.norm<<"\n"<<H<<"\n";}
 for(int index=0;index<3;++index){
  const double radius=tr->radius*std::pow(2.,index-1);start=stamp();auto result=projected.Solve(radius);
  CUDA_CHECK(cudaMemcpy(basis.coeff,result.y.data(),m*8,cudaMemcpyHostToDevice));
  const double one=1,zero=0,minus=-1;
  cublasDgemv(blas,CUBLAS_OP_N,n_c,m,&one,basis.q,n_c,basis.coeff,1,&zero,z,1);
  Lift(z);CUDA_CHECK(cudaMemset(tacc,0,n_p*8));
  MFPass1<CD,Scalar><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,xc_un,nobs,tacc);
  MFBackSub<<<GridSize(npt),256>>>(Rf,bp,tacc,npt,xpv);
  CUDA_CHECK(cudaMemcpy(step,xc_un,n_cf*8,cudaMemcpyDeviceToDevice));CUDA_CHECK(cudaMemcpy(step+n_cf,xpv,n_p*8,cudaMemcpyDeviceToDevice));
  KernelNegateInPlace<<<GridSize(n),256>>>(step,n);DoRetract(step,s_new);
  const double construct=elapsed(start);start=stamp();
  const double candidate_cost=ComputeCost(p,s_new,rk,rk_a2);const double score_seconds=elapsed(start);start=stamp();
  auto model=full_model->Evaluate(p,s,step,k2mask);const double model_seconds=elapsed(start);start=stamp();
  KvS(z,ax);double bx=0,zaz=0;cublasDdot(blas,n_c,bprime,1,z,1,&bx);cublasDdot(blas,n_c,z,1,ax,1,&zaz);
  cublasDaxpy(blas,n_c,&result.lambda,z,1,ax,1);cublasDaxpy(blas,n_c,&minus,bprime,1,ax,1);
  double residual=0,norm=0;cublasDnrm2(blas,n_c,ax,1,&residual);
  MFTRUnscale<<<GridSize(n_c),256>>>(step,E,ax,n_c);cublasDnrm2(blas,n_c,ax,1,&norm);
  const double kkt=(H*result.y+result.lambda*result.y-rhs).norm()/std::max(1.,rhs.norm());
  const std::string prefix=stem+"-r"+std::to_string(index);
  export_state(s_new,prefix+".state");
  {std::ofstream f(prefix+"-y.txt");f.precision(17);f<<result.y<<"\n";}
  std::vector<double> hostz(n_c);CUDA_CHECK(cudaMemcpy(hostz.data(),z,n_c*8,cudaMemcpyDeviceToHost));
  {std::ofstream f(prefix+"-z.txt");f.precision(17);for(double value:hostz)f<<value<<"\n";}
  const double validation=elapsed(start);
  std::printf("RADIUS_CAPTURE o=%d index=%d depth=%d tau=%.17g radius=%.17g norm=%.17g lambda=%.17g base=%.17g cost=%.17g prediction=%.17g reduced_prediction=%.17g rho=%.17g kkt=%.17g full_residual=%.17g gram=%.17g common_seconds=%.17g construct_seconds=%.17g score_seconds=%.17g model_seconds=%.17g validation_seconds=%.17g\n",k,index,m,(double)tau_eff,radius,norm,result.lambda,(double)cost,candidate_cost,model.prediction,bx-.5*zaz,((double)cost-candidate_cost)/model.prediction,kkt,residual/basis.norm,gram,common,construct,score_seconds,model_seconds,validation);
 }
 cudaFree(z);cudaFree(ax);cudaFree(step);
}
