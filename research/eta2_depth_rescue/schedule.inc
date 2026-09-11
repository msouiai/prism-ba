    if(converged && depth_stop && !depth_stop_spent && k+1<max_iter){
      depth_pending=1;depth_requested_center=depth_flat_center;
      std::printf("DEPTH_TRIGGER kind=1 outer=%d cost=%.17g seconds=%.17g center=%.17g current_lambda=%.17g\n",
        k+1,(double)cost,std::chrono::duration<double>(now()-budget_start).count(),
        depth_requested_center,(double)lam_cam);
      converged=false;
    }
    if(!converged && !depth_pending && depth_declip && !depth_declip_spent &&
       !depth_kind_this_attempt && accepted && attr_old_R>0 &&
       attr_raw_norm/attr_old_R>10 && lm_rho>=.25 && lm_rho<=.75 && k+1<max_iter){
      depth_pending=2;
      std::printf("DEPTH_TRIGGER kind=2 outer=%d cost=%.17g seconds=%.17g ratio=%.17g rho=%.17g\n",
        k+1,(double)cost,std::chrono::duration<double>(now()-budget_start).count(),
        attr_raw_norm/attr_old_R,lm_rho);
    }
