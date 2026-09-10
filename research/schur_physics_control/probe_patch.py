"""Terminal descent probe: fresh gradient, four true-cost trials, no state update."""
from audit_patch import patch_gradient

def patch_probe(s, extended=False):
    s=patch_gradient(s)
    s=s.replace('#include "gradient_audit.cuh"', '#include "gradient_audit.cuh"\n#include "relaxation.cuh"',1)
    needle='    PrismLogGradient<CD>(blas,Hcc,Cdiag,bc,bp,ncam,npt,w,uu,"terminal",(int)log.costs.size()-1,cost,lam_cam,tau_used);'
    assert s.count(needle)==1
    probe=r'''
    if(getenv("OCA_RELAX_PROBE")){
      if(CD!=9||shared_intr||rk)throw std::runtime_error("relax probe requires unshared 9DOF L2");
      CUDA_CHECK(cudaDeviceSynchronize());
      auto t_probe=std::chrono::steady_clock::now();
      Scalar *d_relax=nullptr,*d_trial=nullptr;
      CUDA_CHECK(cudaMalloc(&d_relax,(size_t)n*sizeof(Scalar)));
      CUDA_CHECK(cudaMalloc(&d_trial,(size_t)n*sizeof(Scalar)));
      PrismRelaxCamera<CD><<<GridSize(ncam),256>>>(Hcc,bc,ncam,d_relax);
      PrismRelaxPoint<<<GridSize(npt),256>>>(Cdiag,bp,npt,d_relax+n_cf);
      double gdc=0,gdp=0;
      auto ck=[](cublasStatus_t e){if(e!=CUBLAS_STATUS_SUCCESS)throw std::runtime_error("relax probe cuBLAS");};
      ck(cublasDdot(blas,n_cf,bc,1,d_relax,1,&gdc));
      ck(cublasDdot(blas,n_p,bp,1,d_relax+n_cf,1,&gdp));
      const double gDg=-(gdc+gdp);
      auto ProbeCost=[&](double alpha){
        ck(cublasDcopy(blas,n,d_relax,1,d_trial,1));
        ck(cublasDscal(blas,n,&alpha,d_trial,1));
        DoRetract(d_trial,s_new);
        return (double)ComputeCost(p,s_new,rk,rk_a2);
      };
      const double eps=1e-6;
      const double cp=ProbeCost(eps),cm=ProbeCost(-eps);
      const double fd=(cp-cm)/(2*eps);
      int accepted=0,trials=0;double best=cost,best_alpha=0;
      for(int j=0;j<4;++j){
        const double alpha=(1.0/12.0)*std::pow(.25,j);
        const double candidate=ProbeCost(alpha);++trials;
        const bool pass=gDg>0&&std::isfinite(gDg)&&std::isfinite(candidate)&&candidate<=cost-1e-4*alpha*gDg;
        std::printf("RELAX_TRIAL alpha=%.17g cost=%.17g candidate=%.17g relative_gain=%.17g armijo=%d\n",alpha,(double)cost,candidate,((double)cost-candidate)/(double)cost,(int)pass);
        if(pass){accepted=1;best=candidate;best_alpha=alpha;break;}
      }
      CUDA_CHECK(cudaFree(d_relax));CUDA_CHECK(cudaFree(d_trial));
      CUDA_CHECK(cudaDeviceSynchronize());
      const double elapsed=std::chrono::duration<double>(std::chrono::steady_clock::now()-t_probe).count();
      std::printf("RELAX_PROBE accepted=%d trials=%d cost=%.17g candidate=%.17g alpha=%.17g relative_gain=%.17g gDg=%.17g finite_derivative=%.17g derivative_relative_error=%.17g seconds=%.9g state_changed=0\n",accepted,trials,(double)cost,best,best_alpha,((double)cost-best)/(double)cost,gDg,fd,std::abs(fd+gDg)/std::max(1e-300,gDg),elapsed);
    }
'''
    if extended:
        probe=probe.replace('for(int j=0;j<4;++j)', 'for(int j=0;j<12;++j)')
        # Multiple scales reveal whether the GN bound describes true curvature.
        # These are finite-difference estimates, not certified Hessian bounds.
        probe=probe.replace('      int accepted=0,trials=0;', r'''
      for(double e:{1e-4,1e-5,1e-6,1e-7,1e-8}){
        double plus=ProbeCost(e),minus=ProbeCost(-e);
        double first=(plus-minus)/(2*e);
        double second=(plus+minus-2*(double)cost)/(e*e);
        std::printf("RELAX_CURVATURE epsilon=%.17g plus=%.17g minus=%.17g derivative=%.17g derivative_relative_error=%.17g curvature_fd=%.17g gn_upper_bound=%.17g ratio_to_gn_bound=%.17g\n",e,plus,minus,first,std::abs(first+gDg)/std::max(1e-300,gDg),second,12*gDg,second/std::max(1e-300,12*gDg));
      }
      int accepted=0,trials=0;''')
    return s.replace(needle,needle+probe)
