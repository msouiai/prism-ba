
   if(depth_pending){
     depth_active=depth_pending;depth_pending=0;
     if(depth_active==1)depth_stop_spent=true;else depth_declip_spent=true;
     depth_restore=[&,sl=lam_cam,sp=lam_pre_streak,sw=tau_win,su=tau_used,sb=tau_base,
       sn=prev_bnorm,sr=attr_R,so=attr_old_R,snl=attr_next_lambda,sraw=attr_raw_norm,
       san=attr_norm,snu=lm_nu,srho=lm_rho,spr=lm_prediction,sf=numeric_floor,
       srel=last_rel,sft=ftol_streak,ssk=stuck,sbc=backtrack_confirm,
       sre=retries,spd=pcg->last_depth,spo=pcg->last_outer](){
       lam_cam=sl;lam_pre_streak=sp;tau_win=sw;tau_used=su;tau_base=sb;
       prev_bnorm=sn;attr_R=sr;attr_old_R=so;attr_next_lambda=snl;attr_raw_norm=sraw;
       attr_norm=san;lm_nu=snu;lm_rho=srho;lm_prediction=spr;numeric_floor=sf;
       last_rel=srel;ftol_streak=sft;stuck=ssk;backtrack_confirm=sbc;retries=sre;
       pcg->last_depth=spd;pcg->last_outer=spo;factor_cached=false;
     };
     if(depth_active==1)lam_cam=std::clamp(depth_requested_center,numeric_floor,1e16);
     else attr_R=std::min(1e16,4*attr_R);
     factor_cached=false;depth_true_residual=-1;depth_linear_iterations=0;
     depth_begin_mv=st.matvecs;++depth_calls;
     depth_start_seconds=std::chrono::duration<double>(now()-budget_start).count();
     std::printf("DEPTH_BEGIN kind=%d o=%d cost=%.17g lambda=%.17g radius=%.17g seconds=%.17g\n",
       depth_active,k,(double)cost,(double)lam_cam,attr_R,depth_start_seconds);
   }
   const int depth_kind_this_attempt=depth_active;
   const double depth_attempt_center=rej_streak>0?lam_pre_streak:lam_cam;
