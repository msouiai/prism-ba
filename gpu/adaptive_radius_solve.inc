// Fixed-state projected solve replaces CG when verified; capped failure uses CG.
bool radius_ready=false;
int radius_depth=0;double radius_residual=0,radius_lambda=-1,radius_selected_lambda=-1;
std::unique_ptr<PrismProjectedRadius> radius_projected;
auto RadiusSolve=[&](double R){
 const double one=1,zero=0,minus=-1;
 for(;;){
  int target=radius_basis->m?std::min(128,2*radius_basis->m):16;
  if(!radius_projected){
   radius_basis->Grow(blas,KvS,target);int m=radius_basis->m;
   Eigen::MatrixXd H(m,m);for(int i=0;i<m;++i)for(int j=0;j<m;++j)H(i,j)=radius_basis->H[i*128+j];
   Eigen::VectorXd b=Eigen::VectorXd::Zero(m);b[0]=radius_basis->norm;
   radius_projected=std::make_unique<PrismProjectedRadius>(H,b);
  }
  auto result=radius_projected->Solve(R);radius_lambda=result.lambda;radius_depth=radius_basis->m;
  CUDA_CHECK(cudaMemcpy(radius_basis->coeff,result.y.data(),radius_depth*8,cudaMemcpyHostToDevice));
  cublasDgemv(blas,CUBLAS_OP_N,n_c,radius_depth,&one,radius_basis->q,n_c,radius_basis->coeff,1,&zero,radius_x,1);
  KvS(radius_x,radius_ax);cublasDaxpy(blas,n_c,&radius_lambda,radius_x,1,radius_ax,1);
  cublasDaxpy(blas,n_c,&minus,bprime,1,radius_ax,1);
  double residual;cublasDnrm2(blas,n_c,radius_ax,1,&residual);radius_residual=residual/std::max(1e-300,radius_basis->norm);
  if(std::isfinite(radius_residual)&&radius_residual<=.1)return true;
  if(radius_depth>=128||radius_basis->exhausted)return false;
  radius_projected.reset();
 }
};
if(radius_mode==1 && !tr_reuse && tr->radius>0){
 radius_basis->Reset(blas,bprime);
 radius_ready=RadiusSolve(tr->radius);
 if(radius_ready)projected_ok=true;
 if(getenv("OCA_RADIUS_TRACE"))std::printf("ADAPT_RADIUS o=%d depth=%d residual=%.17g fallback=%d\n",k,radius_depth,radius_residual,(int)!radius_ready);
}
