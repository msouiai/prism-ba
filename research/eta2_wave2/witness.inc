    if(const char* folder=getenv("OCA_W2_WITNESS")){
      if(CD!=9||!classical_lm||!pcg||!attr_radius||shared_intr||k2mask!=0||rk)
        throw std::runtime_error("wave witness requires original unshared SIMPLE_RADIAL Eta2");
      const std::string source=folder,dest=getenv("OCA_W2_OUTPUT");
      WaveLoad(source,"E.f64",E,n_c);WaveLoad(source,"Cdiag.f64",Cdiag,n_p);
      WaveLoad(source,"Hcc.f64",Hcc,81ul*ncam);
      const double radius=atof(getenv("OCA_W2_RADIUS")),base_lambda=lam_cam;
      const bool geo=getenv("OCA_W2_GEODESIC")!=nullptr;
      std::ofstream out(dest+"/directions.csv");out.precision(17);
      out<<"arm,rep,lambda,tau,raw_norm,radius,cost,decrease,prediction,rho,iterations,residual,certified,root_updates,fallback,guard_ratio,guard_pass,seconds\n";
      auto emit=[&](const char* arm,int rep,double* step,double lambda,double tau,double raw,int depth,double rel,bool cert,int roots,bool fallback,double guard,bool guardpass,double seconds){
        auto model=full_model->Evaluate(p,s,step,k2mask);DoRetract(step,s_new);double c=ComputeCost(p,s_new);
        out<<arm<<","<<rep<<","<<lambda<<","<<tau<<","<<raw<<","<<radius<<","<<c<<","<<cost-c<<","<<model.prediction<<","<<(cost-c)/model.prediction
           <<","<<depth<<","<<rel<<","<<int(cert)<<","<<roots<<","<<int(fallback)<<","<<guard<<","<<int(guardpass)<<","<<seconds<<"\n";out.flush();
        printf("W2_DIRECTION arm=%s rep=%d gain=%.17g rho=%.17g norm=%.17g R=%.17g guard=%.9g cert=%d\n",arm,rep,(double)cost-c,(cost-c)/model.prediction,raw,radius,guard,int(cert));fflush(stdout);
      };
      WaveLoad(source,"eta2-0.step",dfull,n);emit("eta2_saved",0,dfull,base_lambda,base_lambda,0,0,0,false,0,false,0,true,0);
      for(int repeat=0;repeat<3;++repeat){
        auto start=now();
        Brief0Reference ref(p,s,E,Cdiag,r2acc,obscnt,base_lambda);
        auto factor=[&](double lambda,double tau,bool rebuild){
          ref.lambda=lambda;
          if(rebuild){
            MFPointFactorTau<<<GridSize(npt),256>>>(Cdiag,ref.Rtmp,tau,npt,ref.R,ref.ok);
            MFVinvApply<<<GridSize(npt),256>>>(ref.R,ref.gp,npt,ref.u);
            B0Adjoint<<<ncam,256>>>(p.mf_coff,ref.order,p.pt_idx,ref.Jc,ref.Jp,ref.residual,ref.u,E,ref.Q,nullptr,0,ncam,ref.rhs);
          }
          pcg->Prepare(Hcc,E,lambda,0,1,nullptr,nullptr,nullptr,nullptr,nobs);
        };
        factor(base_lambda,base_lambda,false);
        auto original=ref.Solve(blas,*pcg,dest+"/reference-"+std::to_string(repeat)+".csv");
        double orig_norm=0;cublasDnrm2(blas,n_c,ref.x,1,&orig_norm);
        emit("reference_raw",repeat,ref.Compose(blas,-1),base_lambda,base_lambda,orig_norm,original.iterations,original.true_relative,original.certified,0,false,0,true,std::chrono::duration<double>(now()-start).count());
        emit("reference_clip",repeat,ref.Compose(blas,radius),base_lambda,base_lambda,orig_norm,original.iterations,original.true_relative,original.certified,0,false,0,true,std::chrono::duration<double>(now()-start).count());
        double *first=nullptr;CUDA_CHECK(cudaMalloc(&first,8ul*n));CUDA_CHECK(cudaMemcpy(first,ref.step,8ul*n,cudaMemcpyDeviceToDevice));
        for(int mode=0;mode<2;++mode){
          auto begin=now();double l=base_lambda,tau=base_lambda,norm=orig_norm,prev_l=0,prev_norm=0,lo=base_lambda,hi=0;
          int depth=0,updates=0;auto result=original;
          factor(base_lambda,base_lambda,true);
          result=ref.Solve(blas,*pcg,dest+"/root-"+std::to_string(mode)+"-"+std::to_string(repeat)+"-0.csv");depth+=result.iterations;
          cublasDnrm2(blas,n_c,ref.x,1,&norm);
          const bool triggered=norm>2*radius;
          while(triggered&&result.certified&&(norm>radius||norm<.5*radius)&&updates<8){
            if(norm>radius)lo=l;else hi=l;
            double next=0;
            if(hi>0)next=sqrt(lo*hi);
            else{
              double power=1.;
              if(prev_l>0&&norm>0&&prev_norm>0){double slope=std::log(norm/prev_norm)/std::log(l/prev_l);if(slope<-.05)power=std::clamp(-1./slope,.25,4.);}
              next=l*std::clamp(pow(norm/(.75*radius),power),2.,1e8);
            }
            prev_l=l;prev_norm=norm;l=std::clamp(next,base_lambda,1e16);tau=mode==0?l:base_lambda;
            factor(l,tau,mode==0);
            result=ref.Solve(blas,*pcg,dest+"/root-"+std::to_string(mode)+"-"+std::to_string(repeat)+"-"+std::to_string(++updates)+".csv");
            depth+=result.iterations;cublasDnrm2(blas,n_c,ref.x,1,&norm);
          }
          bool fallback=triggered&&(norm>radius||norm<.5*radius||!result.certified);
          emit(mode==0?"lambda_coupled":"lambda_frozen_tau",repeat,ref.Compose(blas,radius),l,tau,norm,depth,result.true_relative,result.certified,updates,fallback,0,true,std::chrono::duration<double>(now()-begin).count());
        }
        if(geo){
          auto begin=now();factor(base_lambda,base_lambda,true);
          double *jd=ref.New(2ul*nobs),*second=ref.New(2ul*nobs),*metric=ref.New(n),*candidate=ref.New(n);
          WaveFullJ<<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.obs2cslot,ref.Jc,ref.Jp,first,ncam,nobs,jd);
          CUDA_CHECK(cudaMemcpy(candidate,first,8ul*n,cudaMemcpyDeviceToDevice));double h=.1;cublasDscal(blas,n,&h,candidate,1);DoRetract(candidate,s_new);
          WaveSecondResidual<<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s_new.R,s_new.t,s_new.X,INTR_F(p,s_new),INTR_K1(p,s_new),INTR_K2(p,s_new),ref.residual,jd,nobs,h,second);
          auto saved_residual=ref.residual;ref.residual=second;
          B0PointRhs<<<(npt+7)/8,256>>>(p.point_obs_offsets,p.point_obs_list,ref.Jp,second,npt,ref.gp);
          factor(base_lambda,base_lambda,true);
          auto acceleration=ref.Solve(blas,*pcg,dest+"/geodesic-"+std::to_string(repeat)+".csv");
          double* d2=ref.Compose(blas,-1);double n1=0,n2=0;
          WaveMetric<<<GridSize(std::max(n_c,n_p)),256>>>(first,E,Cdiag,ncam,npt,metric);cublasDnrm2(blas,n,metric,1,&n1);
          WaveMetric<<<GridSize(std::max(n_c,n_p)),256>>>(d2,E,Cdiag,ncam,npt,metric);cublasDnrm2(blas,n,metric,1,&n2);
          double ratio=n2/std::max(1e-300,n1);bool pass=acceleration.certified&&ratio<=.75;
          CUDA_CHECK(cudaMemcpy(candidate,first,8ul*n,cudaMemcpyDeviceToDevice));double half=.5;
          if(pass)cublasDaxpy(blas,n,&half,d2,1,candidate,1);
          WaveMetric<<<GridSize(std::max(n_c,n_p)),256>>>(candidate,E,Cdiag,ncam,npt,metric);
          double cn=0;cublasDnrm2(blas,n_c,metric,1,&cn);if(cn>radius){double a=radius/cn;cublasDscal(blas,n,&a,candidate,1);}
          emit("geodesic_guarded",repeat,candidate,base_lambda,base_lambda,cn,acceleration.iterations,acceleration.true_relative,acceleration.certified,0,false,ratio,pass,std::chrono::duration<double>(now()-begin).count());
          WaveSave(dest+"/first-"+std::to_string(repeat)+".step",first,n);WaveSave(dest+"/second-"+std::to_string(repeat)+".step",d2,n);
          WaveSave(dest+"/geodesic-"+std::to_string(repeat)+".step",candidate,n);
          ref.residual=saved_residual;
        }
        cudaFree(first);
      }
      out.close();if(!out)throw std::runtime_error("wave directions write failed");
      printf("W2_WITNESS_COMPLETE\n");fflush(stdout);break;
    }
