#!/usr/bin/env python3
import pathlib,hashlib,json,subprocess
P=pathlib.Path(__file__).resolve().parent;B=P.parent/'eta2_champion'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    m=json.loads((B/'source_manifest.json').read_text());src=B/'source/prism_eta2.cu';h=B/'source/headers'
    assert sha(src)==m['source_sha256'] and all(sha(h/n)==v for n,v in m['headers_sha256'].items())
    code=src.read_text()
    def rep(old,new):
        nonlocal code
        assert code.count(old)==1,(old,code.count(old));code=code.replace(old,new)
    rep('#include "oca_rigfisheye.cuh"','#include "oca_rigfisheye.cuh"\n#include "shift_sweep.cuh"')
    rep('  long full_model_calls=0,full_model_nonpositive=0;double full_model_seconds=0;', '''  long full_model_calls=0,full_model_nonpositive=0;double full_model_seconds=0;
  const int hybrid_mode=getenv("OCA_PHASE_HYBRID")?atoi(getenv("OCA_PHASE_HYBRID")):0;
  if(hybrid_mode<0||hybrid_mode>3||(hybrid_mode&&(!classical_lm||!attr_radius||!attr_strict||CD!=9||shared_intr||mf_fp32||rk)))
    throw std::runtime_error("phase hybrid requires the frozen strict radius LM engine; modes 0..3");
  std::unique_ptr<PrismShiftSweep> hybrid;
  if(hybrid_mode)hybrid=std::make_unique<PrismShiftSweep>(n_c);
  bool hybrid_open=hybrid_mode!=0;int hybrid_flat_streak=0;
  long hybrid_calls=0,hybrid_failures=0,hybrid_products=0;double hybrid_seconds=0;
''')
    rep('    Scalar best_cost=cost; int best_sh=-1,best_ck=-1; bool have=false;', '''    Scalar best_cost=cost; int best_sh=-1,best_ck=-1; bool have=false;
    bool hybrid_used=false;int hybrid_scoring=-1,hybrid_best=-1;
''')
    rep('''        best_cost=c; best_sh=sh; best_ck=ck; have=true;
        if(rho_mode''','''        best_cost=c; best_sh=sh; best_ck=ck; have=true;
        if(hybrid_scoring>=0)hybrid_best=hybrid_scoring;
        if(rho_mode''')
    rep('''    if(!projected_ok){
    if(recycle_mode){''','''    if(hybrid_open){
      const auto hb0=now();const long prior_products=st.matvecs;++hybrid_calls;
      hybrid_used=hybrid->Solve(blas,KvS,bprime,lam_cam,eta,maxck);
      hybrid_products+=st.matvecs-prior_products;
      if(hybrid_used){
        // A new zero-start unpreconditioned sweep of the SAME fixed operator.
        // No PCG recurrence or point-damping changes inside the menu.
        projected_ok=true;cg_it=std::max(0,hybrid->depth-1);cg_broke=true;
        rr=std::pow(hybrid->residual[0]*(double)nb,2.);
        attr_raw_norm=hybrid->norm[2];
        if(!(attr_R>0))attr_R=std::isfinite(attr_raw_norm)&&attr_raw_norm>0?attr_raw_norm:1;
        attr_old_R=attr_R;hybrid->clipped_diameter=hybrid->Diameter(attr_R);
        const int order[5]={2,0,1,3,4};
        for(int a=0;a<(hybrid_mode==1?1:5);++a){
          int l=order[a];hybrid_scoring=l;
          CUDA_CHECK(cudaMemcpy(xs[0],hybrid->X+(size_t)l*n_c,n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
          if(hybrid->norm[l]>attr_R){double scale=attr_R/hybrid->norm[l];cublasDscal(blas,n_c,&scale,xs[0],1);}
          Score(xs[0],0,std::max(1,hybrid->depth));
        }
        hybrid_scoring=-1;
        if(hybrid_best>=0)attr_raw_norm=hybrid->norm[hybrid_best];
      }else {++hybrid_failures;hybrid_flat_streak=0;}
      hybrid_seconds+=std::chrono::duration<double>(now()-hb0).count();
      std::printf("PHASE_SWEEP o=%d mode=%d valid=%d depth=%d qualified=%d raw=%.17g clipped=%.17g selected=%d center=%.17g tau=%.17g worst_res=%.17g eta=%.17g\\n",k,hybrid_mode,(int)hybrid_used,hybrid->depth,(int)hybrid->qualified,hybrid->raw_diameter,hybrid->clipped_diameter,hybrid_best,(double)lam_cam,(double)tau_eff,*std::max_element(hybrid->residual,hybrid->residual+5),(double)eta);
    }
    if(!projected_ok){
    if(recycle_mode){''')
    rep('''        attr_next_lambda=(double)lam_cam*std::pow(attr_old_R/attr_R,2.);
        if(have&&attr_norm<.8*attr_old_R&&lm_rho>=.25)attr_next_lambda=std::min(attr_next_lambda,.1*(double)lam_cam);''','''        const double hybrid_anchor=hybrid_mode==3&&hybrid_used&&hybrid_best>=0&&have&&!backtrack_rescued?hybrid->lambda[hybrid_best]:(double)lam_cam;
        attr_next_lambda=hybrid_anchor*std::pow(attr_old_R/attr_R,2.);
        if(have&&attr_norm<.8*attr_old_R&&lm_rho>=.25)attr_next_lambda=std::min(attr_next_lambda,.1*hybrid_anchor);''')
    rep('''    if(TargetReached(cost,k+1)) break;''','''    if(hybrid_open){
      if(accepted&&hybrid_used&&!backtrack_rescued&&hybrid->qualified&&hybrid->clipped_diameter<=1e-3)++hybrid_flat_streak;
      else hybrid_flat_streak=0;
      if(hybrid_flat_streak>=2||n_accept>=8){
        hybrid_open=false;
        std::printf("PHASE_HANDOVER outer=%d reason=%s flat_streak=%d accepted=%d\\n",k+1,hybrid_flat_streak>=2?"collapse":"opening_cap",hybrid_flat_streak,n_accept);
      }
    }
    if(TargetReached(cost,k+1)) break;''')
    rep('  if(numeric_guard)std::printf("NUMERIC_REPAIR summary', '''  if(hybrid_mode)std::printf("PHASE_SUMMARY mode=%d sweeps=%ld failures=%ld products=%ld seconds=%.9g open=%d\\n",hybrid_mode,hybrid_calls,hybrid_failures,hybrid_products,hybrid_seconds,(int)hybrid_open);
  if(numeric_guard)std::printf("NUMERIC_REPAIR summary''')
    b=P/'build';b.mkdir(exist_ok=True);out=b/'prism-hybrid';s=b/'prism_hybrid.cu';s.write_text(code)
    cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(h),'-I'+str(P),str(s),'-o',str(out),'-lcublas','-lcusolver']
    with (b/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
    (P/'build_manifest.json').write_text(json.dumps(dict(command=cmd,binary_sha256=sha(out),source_sha256=sha(s),base_source_sha256=sha(src),sweep_header_sha256=sha(P/'shift_sweep.cuh')),indent=2)+'\n');print(out,flush=True)
if __name__=='__main__':main()
