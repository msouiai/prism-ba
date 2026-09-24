// Diagnostic / experimental stopping on the SAME current reduced operator.
// FW gap is a global model-gap bound only when S is PSD. Mixed storage does
// not certify PSD; this implementation makes no global certificate claim.
if(camera_tr && getenv("OCA_CG_STOP") && last_ck_fired==cg_it+1 && cg_it+1>=16){
 const int mode=atoi(getenv("OCA_CG_STOP"));
 const bool trace=getenv("OCA_CG_STOP_TRACE")!=nullptr;
 if(mode || trace){
  KvS(tr->best,tr->ax);
  double bx=0,xx=0,xsx=0,gn=0;
  cublasDdot(blas,n_c,bprime,1,tr->best,1,&bx);
  cublasDdot(blas,n_c,tr->best,1,tr->best,1,&xx);
  cublasDdot(blas,n_c,tr->best,1,tr->ax,1,&xsx);
  const double minus=-1.;cublasDaxpy(blas,n_c,&minus,bprime,1,tr->ax,1);
  cublasDnrm2(blas,n_c,tr->ax,1,&gn);
  const double fw=std::max(0.,xsx-bx+tr->radius*gn);
  const double pred=bx-.5*xsx;
  const bool feasible=xx<=tr->radius*tr->radius*(1.+1e-10);
  const bool stop=pred>0 && feasible && std::isfinite(fw) && fw<=.05*pred;
  if(trace)std::printf("CG_STOP o=%d depth=%d chosen=%d radius=%.17g norm=%.17g sigma=%.17g eta=%.17g relative_residual=%.17g prediction=%.17g fw_gap=%.17g ratio=%.17g stop=%d\n",k,cg_it+1,tr->best_depth,tr->radius,std::sqrt(xx),(double)shifts[0],(double)eta,std::sqrt((double)rr_new)/(double)nb,pred,fw,fw/std::max(pred,1e-300),(int)stop);
  if(const char* dir=getenv("OCA_CG_CAPTURE")){
   const int outer=getenv("OCA_CG_CAPTURE_OUTER")?atoi(getenv("OCA_CG_CAPTURE_OUTER")):6;
   if(k==outer){
    const std::string prefix=std::string(dir)+"/depth-"+std::to_string(cg_it+1);
    prism_cg_save(prefix+".x",tr->best,(size_t)n_c*8);
    prism_cg_save(prefix+".gradient",tr->ax,(size_t)n_c*8);
    prism_cg_save(prefix+".cg_x",xs[0],(size_t)n_c*8);
    prism_cg_save(prefix+".cg_residual",r_,(size_t)n_c*8);
   }
  }
  if(mode==1 && stop){cg_broke=true;break;}
 }
}
