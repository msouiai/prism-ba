if(radius_mode && (radius_ready || radius_mode==2)){
 const double original_radius=tr->radius;double chosen_radius=original_radius,trial_norm=0,trial_rho=-1;
 auto RadiusTrial=[&](const double* z,double R,double lambda){
  Lift(z);CUDA_CHECK(cudaMemset(tacc,0,n_p*8));
  MFPass1<CD,Scalar><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,xc_un,nobs,tacc);
  MFBackSub<<<GridSize(npt),256>>>(Rf,bp,tacc,npt,xpv);
  CUDA_CHECK(cudaMemcpy(dfull,xc_un,n_cf*8,cudaMemcpyDeviceToDevice));CUDA_CHECK(cudaMemcpy(dfull+n_cf,xpv,n_p*8,cudaMemcpyDeviceToDevice));
  KernelNegateInPlace<<<GridSize(n),256>>>(dfull,n);DoRetract(dfull,s_new);
  double c=ComputeCost(p,s_new,rk,rk_a2);++st.cand_evals;
  auto model=full_model->Evaluate(p,s,dfull,k2mask);++full_model_calls;
  MFTRUnscale<<<GridSize(n_c),256>>>(dfull,E,radius_ax,n_c);cublasDnrm2(blas,n_c,radius_ax,1,&trial_norm);
  trial_rho=model.prediction>0?(cost-c)/model.prediction:-1;
  bool ok=prism_camera_tr::accept(cost-c,model.prediction,trial_norm,R);
  if(ok&&(!have||c<best_cost)){
   have=true;best_cost=c;best_sh=-1;best_ck=radius_depth;radius_selected_lambda=lambda;tr->radius=R;chosen_radius=R;
   CUDA_CHECK(cudaMemcpy(d_best,dfull,n*8,cudaMemcpyDeviceToDevice));
  }
  if(getenv("OCA_RADIUS_TRACE"))std::printf("RADIUS_TRIAL o=%d radius=%.17g norm=%.17g rho=%.17g accept=%d cost=%.17g\n",k,R,trial_norm,trial_rho,(int)ok,c);
  return ok;
 };
 have=false;best_cost=cost;
 bool ok=RadiusTrial(radius_ready?radius_x:tr->best,original_radius,radius_ready?radius_lambda:-1);
 double next_radius=original_radius;
 if(!ok)next_radius=std::max(1e-14,std::min(.25*original_radius,.5*trial_norm));
 else if(trial_rho>.75&&trial_norm>=.8*original_radius)next_radius=2*original_radius;
 if(next_radius!=original_radius){
  if(radius_ready){if(RadiusSolve(next_radius))RadiusTrial(radius_x,next_radius,radius_lambda);}
  else {
   // Cheap follow-up: rescore the existing direction bank at the new radius.
   tr->radius=next_radius;tr->Reset();
   for(size_t i=0;i<tr->entries.size();++i){
    const auto& e=tr->entries[i];if(!(e.norm>0&&e.bd>0))continue;
    double a=next_radius/e.norm;if(e.curvature>0)a=std::min(a,e.bd/e.curvature);
    double pred=a*e.bd-.5*a*a*e.curvature;
    if(pred>tr->best_prediction){tr->best_prediction=pred;
     CUDA_CHECK(cudaMemcpy(tr->best,tr->bank+i*n_c,n_c*8,cudaMemcpyDeviceToDevice));
     cublasDscal(blas,n_c,&a,tr->best,1);
    }
   }
   if(tr->best_prediction>0)RadiusTrial(tr->best,next_radius,-1);
   if(!have)tr->radius=original_radius;
  }
 }
 tr->radius=have?chosen_radius:original_radius;
}
