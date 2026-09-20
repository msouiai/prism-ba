// Joint camera/point trust region in span{(dc,0),(0,dp)}.
// Metric is block-diagonal GN energy, diag(Jc'Jc,Jp'Jp), restricted to span.
bool joint_checked=false,joint_ok=false;double joint_norm=0,joint_prediction=0,joint_rho=-1,joint_old_radius=joint_radius;
if(joint_mode && have){
 auto b=joint_model->Evaluate(p,s,d_best,k2mask);++joint_model_calls;
 if(b.cc>0&&b.pp>0&&std::isfinite(b.cc+b.pp+b.cp+b.gc+b.gp)){
  const double sc=std::sqrt(b.cc),sp=std::sqrt(b.pp);
  Eigen::MatrixXd H(2,2);H<<1,b.cp/(sc*sp),b.cp/(sc*sp),1;
  Eigen::VectorXd rhs(2);rhs<<-b.gc/sc,-b.gp/sp;
  PrismProjectedRadius model(H,rhs);
  if(!(joint_radius>0))joint_radius=std::hypot(sc,sp);
  joint_old_radius=joint_radius;
  CUDA_CHECK(cudaMemcpy(joint_seed,d_best,n*8,cudaMemcpyDeviceToDevice));
  const double original_cost=best_cost,base_norm=std::hypot(sc,sp),base_pred=-(b.gc+b.gp+.5*(b.cc+2*b.cp+b.pp));
  have=prism_camera_tr::accept(cost-original_cost,base_pred,base_norm,joint_radius);
  best_cost=have?original_cost:cost;
  if(have){joint_norm=base_norm;joint_prediction=base_pred;joint_rho=(cost-original_cost)/base_pred;joint_ok=true;}
  double selected_radius=joint_radius;
  auto Trial=[&](double radius){
   auto result=model.Solve(radius);const double ac=result.y[0]/sc,ap=result.y[1]/sp;
   MFAlphaScale<<<GridSize(n),256>>>(dfull,joint_seed,ac,ap,n_cf,n);DoRetract(dfull,s_new);
   double c=ComputeCost(p,s_new,rk,rk_a2);++st.cand_evals;++joint_trials;
   double prediction=rhs.dot(result.y)-.5*result.y.dot(H*result.y),norm=result.y.norm();
   double rho=prediction>0?(cost-c)/prediction:-1;
   bool ok=prism_camera_tr::accept(cost-c,prediction,norm,radius);
   if(ok&&(!have||c<best_cost)){
    have=true;best_cost=c;joint_norm=norm;joint_prediction=prediction;joint_rho=rho;joint_ok=true;selected_radius=radius;
    CUDA_CHECK(cudaMemcpy(d_best,dfull,n*8,cudaMemcpyDeviceToDevice));
   }
   if(getenv("OCA_JOINT_TRACE"))std::printf("JOINT_TRIAL o=%d radius=%.17g norm=%.17g ac=%.17g ap=%.17g prediction=%.17g rho=%.17g accept=%d cost=%.17g lambda=%.17g\n",k,radius,norm,ac,ap,prediction,rho,(int)ok,c,result.lambda);
   return std::make_tuple(ok,norm,rho);
  };
  auto result=Trial(joint_radius);
  if(!std::get<0>(result))Trial(std::max(1e-14,std::min(.25*joint_radius,.5*std::get<1>(result))));
  else if(std::get<2>(result)>.75&&std::get<1>(result)>=.8*joint_radius)Trial(2*joint_radius);
  joint_checked=true;joint_old_radius=selected_radius;
  joint_radius=prism_camera_tr::radius_after(selected_radius,joint_norm,joint_rho);
  if(!have)joint_radius=std::max(1e-14,.25*selected_radius);
 }
}
