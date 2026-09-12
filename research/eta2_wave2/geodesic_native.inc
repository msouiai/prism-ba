      if(geo){
        const auto geo_start=now();const long geo_before=st.matvecs;
        CUDA_CHECK(cudaMemcpy(geo->first,have?d_best:dfull,8ul*n,cudaMemcpyDeviceToDevice));
        WaveAnalyticSecond<<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,s.R,s.t,s.X,INTR_F(p,s),INTR_K1(p,s),geo->first,ncam,nobs,geo->second);
        CUDA_CHECK(cudaMemset(geo->gc,0,8ul*n_c));CUDA_CHECK(cudaMemset(geo->gp,0,8ul*n_p));
        GeoGradient<<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),geo->second,nobs,geo->gc,geo->gp);
        MFVinvApply<<<GridSize(npt),256>>>(Rf,geo->gp,npt,geo->u);
        CUDA_CHECK(cudaMemset(geo->corr,0,8ul*n_c));
        MFRhsPrime<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,geo->u,nobs,geo->corr);
        GeoRhs<<<GridSize(n_c),256>>>(geo->gc,geo->corr,E,n_c,geo->rhs);
        CUDA_CHECK(cudaMemset(geo->x,0,8ul*n_c));CUDA_CHECK(cudaMemcpy(geo->r,geo->rhs,8ul*n_c,cudaMemcpyDeviceToDevice));
        double nb2=0,nr2=0,rz=0,rel=1;int depth=0;bool cert=false,cutoff=false;
        cublasDnrm2(blas,n_c,geo->rhs,1,&nb2);pcg->Apply(geo->r);cublasDdot(blas,n_c,geo->r,1,pcg->z,1,&rz);
        CUDA_CHECK(cudaMemcpy(geo->v,pcg->z,8ul*n_c,cudaMemcpyDeviceToDevice));
        if(nb2==0){cert=true;rel=0;}
        for(int it=0;!cert&&it<maxck&&std::isfinite(nb2);++it){
          KvS(geo->v,geo->Ap);const double sig=lam_cam;cublasDaxpy(blas,n_c,&sig,geo->v,1,geo->Ap,1);
          double pAp=0,pp=0;cublasDdot(blas,n_c,geo->v,1,geo->Ap,1,&pAp);cublasDdot(blas,n_c,geo->v,1,geo->v,1,&pp);++depth;
          if(!(pAp>1e-14*pp&&rz>0&&std::isfinite(pAp))){cutoff=true;break;}
          double a=rz/pAp,minus=-a;cublasDaxpy(blas,n_c,&a,geo->v,1,geo->x,1);cublasDaxpy(blas,n_c,&minus,geo->Ap,1,geo->r,1);
          cublasDnrm2(blas,n_c,geo->r,1,&nr2);rel=nr2/nb2;
          bool refresh=rel<=.5;
          if(refresh){
            KvS(geo->x,geo->Ap);cublasDaxpy(blas,n_c,&sig,geo->x,1,geo->Ap,1);
            CUDA_CHECK(cudaMemcpy(geo->r,geo->rhs,8ul*n_c,cudaMemcpyDeviceToDevice));double m=-1;cublasDaxpy(blas,n_c,&m,geo->Ap,1,geo->r,1);
            cublasDnrm2(blas,n_c,geo->r,1,&nr2);rel=nr2/nb2;if(std::isfinite(rel)&&rel<=.505){cert=true;break;}
          }
          pcg->Apply(geo->r);double next=0;cublasDdot(blas,n_c,geo->r,1,pcg->z,1,&next);
          if(refresh)CUDA_CHECK(cudaMemcpy(geo->v,pcg->z,8ul*n_c,cudaMemcpyDeviceToDevice));
          else{double beta=next/rz,one=1;cublasDscal(blas,n_c,&beta,geo->v,1);cublasDaxpy(blas,n_c,&one,pcg->z,1,geo->v,1);}rz=next;
        }
        if(attempt_trace)attempt_clock.row.pcg_iterations+=depth;
        double guard=INFINITY,cn=0,candidate_cost=INFINITY,prediction=0,rho=-1;bool admitted=false,won=false;
        if(cert){
          Lift(geo->x);CUDA_CHECK(cudaMemcpy(geo->d2,xc_un,8ul*n_c,cudaMemcpyDeviceToDevice));
          CUDA_CHECK(cudaMemset(geo->tac,0,8ul*n_p));
          MFPass1<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,xc_un,nobs,geo->tac);
          MFBackSub<<<GridSize(npt),256>>>(Rf,geo->gp,geo->tac,npt,geo->d2+n_c);KernelNegateInPlace<<<GridSize(n),256>>>(geo->d2,n);
          if(const char* path=getenv("OCA_GEODESIC_AUDIT")){if(!geo->audit_written){
            std::string q(path);geo->audit_written=true;
            GeoDump(q,"R",s.R,9ul*ncam);GeoDump(q,"t",s.t,3ul*ncam);GeoDump(q,"X",s.X,3ul*npt);
            GeoDump(q,"f",INTR_F(p,s),ncam);GeoDump(q,"k1",INTR_K1(p,s),ncam);
            GeoDump(q,"ci",p.cam_idx,nobs);GeoDump(q,"pi",p.pt_idx,nobs);GeoDump(q,"uv",p.uv,2ul*nobs);
            GeoDump(q,"E",E,n_c);GeoDump(q,"Hcc",Hcc,81ul*ncam);GeoDump(q,"Rf",Rf,6ul*npt);
            GeoDump(q,"Gp",Gp,27ul*nobs);GeoDump(q,"fci",fragment_cams,nobs);GeoDump(q,"fpi",fragment_points,nobs);
            GeoDump(q,"first",geo->first,n);GeoDump(q,"second",geo->second,2ul*nobs);
            GeoDump(q,"gc",geo->gc,n_c);GeoDump(q,"gp",geo->gp,n_p);GeoDump(q,"rhs",geo->rhs,n_c);
            GeoDump(q,"x",geo->x,n_c);GeoDump(q,"Ap",geo->Ap,n_c);GeoDump(q,"d2",geo->d2,n);
            FILE* f=fopen((q+".meta").c_str(),"w");if(!f)throw std::runtime_error("geodesic audit metadata failed");
            fprintf(f,"%d %d %d %.17g %.17g\n",ncam,npt,nobs,lam_cam,rel);fclose(f);
          }}
          double n1=0,n2=0;GeoMetric<<<GridSize(std::max(n_c,n_p)),256>>>(geo->first,E,Cdiag,ncam,npt,geo->metric);cublasDnrm2(blas,n,geo->metric,1,&n1);
          GeoMetric<<<GridSize(std::max(n_c,n_p)),256>>>(geo->d2,E,Cdiag,ncam,npt,geo->metric);cublasDnrm2(blas,n,geo->metric,1,&n2);
          guard=n2/std::max(1e-300,n1);admitted=std::isfinite(guard)&&guard<=.75;
          if(admitted){
            CUDA_CHECK(cudaMemcpy(geo->candidate,geo->first,8ul*n,cudaMemcpyDeviceToDevice));double half=.5;cublasDaxpy(blas,n,&half,geo->d2,1,geo->candidate,1);
            GeoMetric<<<GridSize(std::max(n_c,n_p)),256>>>(geo->candidate,E,Cdiag,ncam,npt,geo->metric);cublasDnrm2(blas,n_c,geo->metric,1,&cn);
            if(cn>attr_R){double a=attr_R/cn;cublasDscal(blas,n,&a,geo->candidate,1);}
            auto model=full_model->Evaluate(p,s,geo->candidate,k2mask);++full_model_calls;prediction=model.prediction;
            DoRetract(geo->candidate,s_new);candidate_cost=ComputeCost(p,s_new);++st.cand_evals;
            rho=prediction>0?(cost-candidate_cost)/prediction:-1;
            if(std::isfinite(candidate_cost)&&candidate_cost<cost&&rho>.1&&(!have||candidate_cost<best_cost)){
              CUDA_CHECK(cudaMemcpy(d_best,geo->candidate,8ul*n,cudaMemcpyDeviceToDevice));have=true;best_cost=candidate_cost;best_sh=0;best_ck=cg_broke?cg_it+1:maxck;won=true;
            }
          }
        }
        std::printf("GEODESIC attempt=%zu outer=%d accepts_before=%d cg=%d products=%ld relative=%.17g certified=%d cutoff=%d guard=%.17g admitted=%d won=%d cost=%.17g prediction=%.17g rho=%.17g seconds=%.9g\n",wave_trace?wave_trace->rows.size():0,k,n_accept,depth,st.matvecs-geo_before,rel,(int)cert,(int)cutoff,guard,(int)admitted,(int)won,candidate_cost,prediction,rho,std::chrono::duration<double>(now()-geo_start).count());
      }
