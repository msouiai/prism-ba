      if(brief_capture_active){
        const std::string dir=getenv("OCA_BRIEF0_DIR");
        if(CD!=9||!classical_lm||!pcg||!attr_radius||shared_intr||mf_fp32||rk||intr_damp!=1||k2mask!=0||!r2acc)
          throw std::runtime_error("Brief0 requires the frozen Eta2 objective and flags");
        auto save=[&](const std::string& name,const void* device,size_t bytes){
          std::vector<char> data(bytes);CUDA_CHECK(cudaMemcpy(data.data(),device,bytes,cudaMemcpyDeviceToHost));
          std::ofstream f(dir+"/"+name,std::ios::binary);f.write(data.data(),bytes);f.close();
          if(!f)throw std::runtime_error("Brief0 write failed");
        };
        save("eta2.step",have?d_best:dfull,8ul*n);
        save("E.f64",E,8ul*n_c);save("R_state.f64",s.R,72ul*ncam);save("t_state.f64",s.t,24ul*ncam);
        save("X_state.f64",s.X,24ul*npt);save("intr_state.f64",s.intr,24ul*ncam);
        save("Hcc.f64",Hcc,81ul*ncam*8);save("Cdiag.f64",Cdiag,24ul*npt);
        save("eta2_raw_scaled.f64",brief_raw,8ul*n_c);
        std::ofstream meta(dir+"/metadata.txt");meta.precision(17);
        meta<<"ncam="<<ncam<<"\nnpt="<<npt<<"\nnobs="<<nobs<<"\nouter="<<k<<"\ncost="<<cost
          <<"\nlambda="<<lam_cam<<"\ntau="<<tau_eff<<"\nradius="<<attr_old_R<<"\nfloor="<<numeric_floor
          <<"\nprevious_rhs_norm="<<numeric_prior_bnorm<<"\nrhs_norm="<<nb<<"\neta="<<eta
          <<"\neta2_cg="<<(cg_broke?cg_it+1:maxck)<<"\neta2_recursive_residual="<<sqrt(rr)/std::max(1e-300,(double)nb)
          <<"\neta2_cutoff="<<int(trunc)<<"\nterminal_witness="<<int(brief_pending)<<"\n";
        meta.close();
        std::ofstream out(dir+"/native_directions.csv");out.precision(17);
        out<<"arm,rep,cost,prediction,decrease,rho,camera_norm,pcg_iterations,true_residual,certified,seconds,reason\n";
        auto score=[&](const char* arm,int rep,double* d,int it,double residual,bool cert,double seconds,const std::string& reason){
          auto model=full_model->Evaluate(p,s,d,k2mask);DoRetract(d,s_new);double c=ComputeCost(p,s_new,rk,rk_a2);
          MFTRUnscale<<<GridSize(n_c),256>>>(d,E,xc_un,n_c);double cn=0;cublasDnrm2(blas,n_c,xc_un,1,&cn);
          out<<arm<<","<<rep<<","<<c<<","<<model.prediction<<","<<cost-c<<","<<(cost-c)/model.prediction<<","<<cn
            <<","<<it<<","<<residual<<","<<int(cert)<<","<<seconds<<","<<reason<<"\n";out.flush();
          save(std::string(arm)+"-"+std::to_string(rep)+".step",d,8ul*n);
          printf("BRIEF0_DIRECTION arm=%s rep=%d cost=%.17g pred=%.17g rho=%.17g cg=%d residual=%.17g certified=%d seconds=%.6g\n",
            arm,rep,c,model.prediction,(cost-c)/model.prediction,it,residual,int(cert),seconds);fflush(stdout);
        };
        score("eta2",0,have?d_best:dfull,cg_broke?cg_it+1:maxck,sqrt(rr)/std::max(1e-300,(double)nb),false,0,"native_inexact");
        Brief0Reference reference(p,s,E,Cdiag,r2acc,obscnt,lam_cam);
        for(int repeat=0;repeat<3;++repeat){
          auto result=reference.Solve(blas,*pcg,dir+"/reference-"+std::to_string(repeat)+".csv");
          auto d=reference.Compose(blas,-1);score("exact",repeat,d,result.iterations,result.true_relative,result.certified,result.seconds,result.reason);
          d=reference.Compose(blas,attr_old_R);score("exact_clip",repeat,d,result.iterations,result.true_relative,result.certified,result.seconds,result.reason);
        }
        CUDA_CHECK(cudaFree(brief_raw));brief_raw=nullptr;brief_complete=true;
        printf("BRIEF0_COMPLETE outer=%d terminal=%d directory=%s\n",k,int(brief_pending),dir.c_str());fflush(stdout);
        break; // No diagnostic candidate is committed to the optimization state.
      }
