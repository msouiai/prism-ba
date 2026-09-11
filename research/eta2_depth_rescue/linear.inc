    if(depth_active){
      depth_linear_iterations=trunc?cg_it:(cg_broke?cg_it+1:maxck);
      KvS(xs[0],pcg->tmp);
      cublasDaxpy(blas,n_c,&shifts[0],xs[0],1,pcg->tmp,1);
      const double minus=-1;cublasDaxpy(blas,n_c,&minus,bprime,1,pcg->tmp,1);
      double norm;cublasDnrm2(blas,n_c,pcg->tmp,1,&norm);
      depth_true_residual=norm/std::max(1e-300,(double)nb);
    }
