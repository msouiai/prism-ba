    if(depth_active){
      if(trunc||!std::isfinite(depth_true_residual))have=false;
      const bool won=have&&best_cost<cost;
      const double elapsed=std::chrono::duration<double>(now()-budget_start).count()-depth_start_seconds;
      depth_seconds+=elapsed;
      std::printf("DEPTH_RESULT kind=%d o=%d cost=%.17g candidate=%.17g accept=%d cg=%d residual=%.17g eta=%.17g cap_hit=%d trunc=%d rho=%.17g products=%ld seconds=%.17g\n",
        depth_active,k,(double)cost,(double)best_cost,(int)won,depth_linear_iterations,
        depth_true_residual,(double)eta,(int)(!cg_broke&&!trunc),(int)trunc,lm_rho,st.matvecs-depth_begin_mv,elapsed);
      if(won){++depth_wins;depth_active=0;ftol_streak=0;stuck=0;}
      else {
        const int failed_kind=depth_active;++depth_failures;++n_reject;
        depth_restore();depth_active=0;
        if(failed_kind==1){
          log.iters.push_back(k+1);log.costs.push_back(cost);CsvRow(k+1,(double)cost);
          std::printf("DEPTH_STOP confirmed outer=%d cost=%.17g\n",k+1,(double)cost);
          break;
        }
        // Accepted state is untouched. Rebuild the original coupled system.
        need_assembly=false;
        std::printf("DEPTH_RESTORE o=%d cost=%.17g lambda=%.17g radius=%.17g\n",
          k,(double)cost,(double)lam_cam,attr_R);
        continue;
      }
    }
