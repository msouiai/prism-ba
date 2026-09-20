if(cg_projection && (cg_it+1)%16==0 && tr->radius>0 && cg_projection->Solve(blas,bprime,tr->radius)){
 // Verify the recurrence-built model before inserting any direction into the bank.
 KvS(cg_projection->x,tr->ax);++tr->model_evals;
 double bx=0,xx=0,xsx=0,gn=0;
 cublasDdot(blas,n_c,bprime,1,cg_projection->x,1,&bx);
 cublasDdot(blas,n_c,cg_projection->x,1,cg_projection->x,1,&xx);
 cublasDdot(blas,n_c,cg_projection->x,1,tr->ax,1,&xsx);
 const double minus=-1.;cublasDaxpy(blas,n_c,&minus,bprime,1,tr->ax,1);
 cublasDnrm2(blas,n_c,tr->ax,1,&gn);
 double pred=bx-.5*xsx,fw=std::max(0.,xsx-bx+tr->radius*gn);
 double model_error=std::abs(pred-cg_projection->model_prediction)/std::max(1.,std::abs(pred));
 const bool verified=model_error<=1e-7 && xx<=tr->radius*tr->radius*(1+1e-10);
 if(verified && pred>0){
  if(tr->entries.size()>=64)throw std::runtime_error("CG projected TR bank capacity");
  PrismCameraTR::Entry e{};e.norm=std::sqrt(xx);e.bd=bx;e.curvature=xsx;e.sh=-2;e.depth=cg_it+1;
  double* saved=tr->bank+tr->entries.size()*n_c;
  CUDA_CHECK(cudaMemcpy(saved,cg_projection->x,n_c*8,cudaMemcpyDeviceToDevice));
  tr->entries.push_back(e);tr->Select(saved,e,blas);
 }
 const bool stop=verified && pred>0 && fw<=.05*tr->best_prediction;
 if(getenv("OCA_CG_STOP_TRACE"))std::printf("CG_PROJECTION o=%d depth=%d rank=%d lambda=%.17g norm=%.17g radius=%.17g prediction=%.17g fw_gap=%.17g ratio=%.17g model_error=%.17g stop=%d\n",k,cg_it+1,cg_projection->rank,cg_projection->multiplier,std::sqrt(xx),tr->radius,pred,fw,fw/std::max(pred,1e-300),model_error,(int)stop);
 if(!verified && getenv("OCA_CG_STOP_TRACE"))throw std::runtime_error("CG projected model audit failed");
 if(stop){cg_broke=true;break;}
}
