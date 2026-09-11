        if constexpr(CD==9){
        if(depth_active==2 && !curvature_captured && getenv("OCA_CURVATURE_CAPTURE")){
          if(shared_intr||mf_fp32||block_on||poly_on||rk||selected_floor!=0||!use_equil||!tau_split)
            throw std::runtime_error("curvature audit requires plain guarded Eta2 geometry");
          const std::string dir=getenv("OCA_CURVATURE_CAPTURE");
          auto save=[&](const char* name,const void* device,size_t bytes){
            std::vector<char> h(bytes);CUDA_CHECK(cudaMemcpy(h.data(),device,bytes,cudaMemcpyDeviceToHost));
            std::ofstream f(dir+"/"+name,std::ios::binary);f.write(h.data(),bytes);f.close();
            if(!f)throw std::runtime_error("curvature capture write failed");
          };
          // Preserve the actual cutoff product before evaluating any alternatives.
          save("direction.f64",pv_,n_c*8ul);save("actual_product.f64",Ap_,n_c*8ul);
          save("E.f64",E,n_c*8ul);save("Hcc.f64",Hcc,ncam*81ul*8);
          save("Cdiag.f64",Cdiag,npt*3ul*8);save("R_stored.f64",Rf,npt*6ul*8);
          save("W32.f32",Gp,nobs*27ul*4);save("B32.f32",Bo,nobs*6ul*4);
          save("o2slot.i32",fragment_o2slot,nobs*4ul);
          save("fragment_cams.i32",fragment_cams,nobs*4ul);
          save("fragment_points.i32",fragment_points,nobs*4ul);
          save("obs_cams.i32",p.cam_idx,nobs*4ul);save("obs_points.i32",p.pt_idx,nobs*4ul);
          save("R_state.f64",s.R,ncam*9ul*8);save("t_state.f64",s.t,ncam*3ul*8);
          save("X_state.f64",s.X,npt*3ul*8);save("intr_state.f64",s.intr,ncam*3ul*8);
          std::ofstream meta(dir+"/metadata.txt");meta.precision(17);
          meta<<"ncam="<<ncam<<"\nnpt="<<npt<<"\nnobs="<<nobs<<"\nouter="<<k
            <<"\ncg_completed="<<cg_it<<"\ncost="<<cost<<"\nlambda="<<shifts[0]
            <<"\ntau="<<tau_eff<<"\npAp="<<pAp<<"\npp="<<pp
            <<"\nquotient="<<pAp/pp<<"\ncutoff=1e-14\nintr_damp="<<intr_damp
            <<"\nk2mask="<<k2mask<<"\nradius="<<attr_R<<"\n";
          meta.close();if(!meta)throw std::runtime_error("metadata write failed");
          std::vector<Scalar*> allocated;
          auto alloc=[&](size_t count){Scalar* q=nullptr;M((void**)&q,count*8);allocated.push_back(q);return q;};
          Scalar* G64=alloc(27ul*nobs),*B64=alloc(6ul*nobs),*J64=alloc(18ul*nobs);
          Scalar* H64=alloc(81ul*ncam),*C64=alloc(3ul*npt),*bc64=alloc(n_c),*bp64=alloc(n_p);
          Scalar* R64=alloc(6ul*npt),*R32qr=alloc(6ul*npt),*Rtemp=alloc(6ul*npt);
          Scalar* trial=alloc(n_c),*v=alloc(n_c),*gpoint=alloc(n_p),*upoint=alloc(n_p);
          CUDA_CHECK(cudaMemset(H64,0,ncam*81ul*8));CUDA_CHECK(cudaMemset(C64,0,npt*3ul*8));
          CUDA_CHECK(cudaMemset(bc64,0,n_c*8ul));CUDA_CHECK(cudaMemset(bp64,0,n_p*8ul));
          MFAssemble<9,double><<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
            INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),fragment_o2slot,p.obs2cslot,nobs,
            H64,C64,G64,nullptr,B64,bc64,bp64,k2mask,nullptr,nullptr,0,0);
          if(r2acc)KernelDampIntr9<<<GridSize(ncam),256>>>(H64,INTR_F(p,s),r2acc,obscnt,ncam,intr_damp,k2mask);
          CurvatureCameraRows<<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
            INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),nobs,k2mask,J64);
          MFPointFactorObs<double><<<GridSize(npt),256>>>(B64,p.point_obs_offsets,p.point_obs_list,npt,Rtemp);
          MFPointFactorTau<<<GridSize(npt),256>>>(Cdiag,Rtemp,tau_eff,npt,R64,okf);
          MFPointFactorObs<float><<<GridSize(npt),256>>>(Bo,p.point_obs_offsets,p.point_obs_list,npt,Rtemp);
          MFPointFactorTau<<<GridSize(npt),256>>>(Cdiag,Rtemp,tau_eff,npt,R32qr,okf);
          save("W64.f64",G64,nobs*27ul*8);save("B64.f64",B64,nobs*6ul*8);
          save("Jc64.f64",J64,nobs*18ul*8);save("Hcc_rebuilt.f64",H64,ncam*81ul*8);
          save("Cdiag_rebuilt.f64",C64,npt*3ul*8);save("R_fp64qr.f64",R64,npt*6ul*8);
          save("R_fp32qr.f64",R32qr,npt*6ul*8);
          std::ofstream csv(dir+"/gpu_rayleigh.csv");csv.precision(17);csv<<"operator,rep,pAp,quotient\n";
          for(int repeat=0;repeat<5;++repeat){
            KvS(pv_,trial);cublasDaxpy(blas,n_c,&shifts[0],pv_,1,trial,1);
            double q;cublasDdot(blas,n_c,pv_,1,trial,1,&q);
            csv<<"stored_repeat,"<<repeat<<","<<q<<","<<q/pp<<"\n";
          }
          CUDA_CHECK(cudaMemcpy(v,pv_,n_c*8ul,cudaMemcpyDeviceToDevice));MFScaleVec<<<GridSize(n_c),256>>>(v,E,n_c);
          auto measure=[&](bool full64,const Scalar* factor,const char* tag){
            CUDA_CHECK(cudaMemset(gpoint,0,n_p*8ul));
            if(full64)MFPass1<9,double><<<GridSize(nobs),256>>>(G64,fragment_cams,fragment_points,v,nobs,gpoint);
            else MFPass1<9,float><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,v,nobs,gpoint);
            MFVinvApply<<<GridSize(npt),256>>>(factor,gpoint,npt,upoint);
            if(full64)MFPass2<9,double><<<ncam,256>>>(G64,p.mf_cspt,p.mf_coff,upoint,Hcc,v,nobs,trial,fragment_slots);
            else MFPass2<9,float><<<ncam,256>>>(Gp,p.mf_cspt,p.mf_coff,upoint,Hcc,v,nobs,trial,fragment_slots);
            MFScaleVec<<<GridSize(n_c),256>>>(trial,E,n_c);cublasDaxpy(blas,n_c,&shifts[0],pv_,1,trial,1);
            double q;cublasDdot(blas,n_c,pv_,1,trial,1,&q);
            csv<<tag<<",0,"<<q<<","<<q/pp<<"\n";
            save((std::string(tag)+"_product.f64").c_str(),trial,n_c*8ul);
          };
          measure(false,Rf,"stored");measure(false,R32qr,"W32_R32qr");
          measure(true,Rf,"W64_Rstored");measure(false,R64,"W32_R64qr");
          measure(true,R64,"W64_R64qr");
          csv.close();if(!csv)throw std::runtime_error("Rayleigh CSV write failed");
          for(auto* q:allocated)CUDA_CHECK(cudaFree(q));
          curvature_captured=true;
          std::printf("CURVATURE_CAPTURE outer=%d cg=%d quotient=%.17g cutoff=1e-14 directory=%s\n",k,cg_it,pAp/pp,dir.c_str());
        }}
