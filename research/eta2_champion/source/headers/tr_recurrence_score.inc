// At a CG snapshot, (S+sigma I)x = b - r_sigma.
// Shifted residual r_sigma=zeta*r_seed: curvature=bd-sigma*||x||²-zeta*x'r.
// Audit mode compares against the original operator and records drift.
if(tr_fast_model){
 PrismCameraTR::Entry e{};e.sh=l;e.depth=depth;
 cublasDnrm2(blas,n_c,xs[l],1,&e.norm);cublasDdot(blas,n_c,bprime,1,xs[l],1,&e.bd);
 double xr=0;cublasDdot(blas,n_c,xs[l],1,r_,1,&xr);
 e.curvature=e.bd-tr_model_shifts[l]*e.norm*e.norm-tr_residual_scales[l]*xr;
 if(tr_fast_audit){
  KvS(xs[l],tr->ax);double explicit_c=0;cublasDdot(blas,n_c,xs[l],1,tr->ax,1,&explicit_c);
  double error=std::abs(e.curvature-explicit_c)/std::max({1.,std::abs(e.curvature),std::abs(explicit_c)});
  std::printf("TR_RECURRENCE o=%d sh=%d depth=%d curvature=%.17g explicit=%.17g error=%.17g\n",k,l,depth,e.curvature,explicit_c,error);
  if(error>1e-7)throw std::runtime_error("TR recurrence curvature drift");
 }
 if(tr->entries.size()>=64)throw std::runtime_error("TR recurrence bank capacity");
 double* saved=tr->bank+tr->entries.size()*n_c;
 CUDA_CHECK(cudaMemcpy(saved,xs[l],n_c*8,cudaMemcpyDeviceToDevice));tr->entries.push_back(e);tr->Select(saved,e,blas);
 if(legacy_tr){legacy_tr->radius=tr->radius;legacy_tr->Select(saved,e,blas);}
 ++tr_fast_calls;
}else tr->Add(xs[l],l,depth,bprime,blas,KvS);
