"""Read-only gradient instrumentation; terminal gradient uses fresh assembly."""
def patch_gradient(s):
    include='#include <cublas_v2.h>'
    assert include in s
    s=s.replace(include,include+'\n#include "gradient_audit.cuh"',1)
    start=s.index('RunLog SolveMFreeShiftedCG(')
    assembly=s.index('   if(need_assembly){',start)
    a=s.index('    CUDA_CHECK(cudaMemset(Hcc,0,',assembly)
    b=s.index('    if(r2acc) KernelDampIntr9',a)
    fresh=s[a:b]
    assert fresh.count('MFAssemble<')==2, 'must extract only the main assembly block'
    # Log current undamped blocks before any intrinsics-only damping is added.
    call='''    if(getenv("OCA_GRAD_AUDIT")){
      if(CD!=9||shared_intr||rk)throw std::runtime_error("gradient audit requires unshared 9DOF L2");
      PrismLogGradient<CD>(blas,Hcc,Cdiag,bc,bp,ncam,npt,w,uu,"assembly",k,cost,lam_cam,tau_used);
    }
'''
    s=s[:b]+call+s[b:]
    # At the end, cache may describe the state BEFORE the last accepted step.
    end=s.index('  int cheir1=CountCheiralityViolations(p,s);',start)
    terminal='''  if(getenv("OCA_GRAD_AUDIT")){
'''+fresh+'''    PrismLogGradient<CD>(blas,Hcc,Cdiag,bc,bp,ncam,npt,w,uu,"terminal",(int)log.costs.size()-1,cost,lam_cam,tau_used);
  }
'''
    s=s[:end]+terminal+s[end:]
    # This telemetry changes no state and allows lambda/gradient pairing on retries.
    needle='    tau_used = tau_eff;'
    a=s.index(needle,start)
    s=s[:a]+s[a:].replace(needle,needle+'''
    if(getenv("OCA_GRAD_AUDIT"))std::printf("DAMP_AUDIT outer=%d retry=%d cost=%.17g lambda=%.17g tau=%.17g\\n",k,retries,(double)cost,(double)lam_cam,(double)tau_eff);''',1)
    return s
