#!/usr/bin/env python3
"""Generate an isolated source from the hash-verified frozen champion."""
import pathlib,hashlib,json,subprocess,shutil
P=pathlib.Path(__file__).resolve().parent
B=P.parent/'eta2_champion'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    m=json.loads((B/'source_manifest.json').read_text())
    src=B/'source/prism_eta2.cu';headers=B/'source/headers'
    assert sha(src)==m['source_sha256']
    assert all(sha(headers/n)==h for n,h in m['headers_sha256'].items())
    build=P/'build';build.mkdir(exist_ok=True)
    code=src.read_text()
    def replace(old,new):
        nonlocal code
        assert code.count(old)==1,(old,code.count(old))
        code=code.replace(old,new)
    replace('#include "point_refinement_candidate.cuh"','#include "point_refinement_candidate.cuh"\n#include "point_overlay.cuh"')
    replace('  long lm_rescue_calls=0,lm_rescue_wins=0;double lm_rescue_seconds=0;', '''  long lm_rescue_calls=0,lm_rescue_wins=0;double lm_rescue_seconds=0;
  const int follow_point=getenv("OCA_FOLLOW_POINT")?atoi(getenv("OCA_FOLLOW_POINT")):0;
  const bool follow_loose=getenv("OCA_FOLLOW_LOOSE")&&atoi(getenv("OCA_FOLLOW_LOOSE"));
  if(follow_point<0||follow_point>3||((follow_point||follow_loose)&&(!classical_lm||CD!=9)))
    throw std::runtime_error("follow-up requires classical 9DOF LM; point=0..3");
  std::unique_ptr<PrismPointOverlay> follow_overlay;
  if(follow_point)follow_overlay=std::make_unique<PrismPointOverlay>();
  long follow_calls=0,follow_wins=0;unsigned long long follow_changed=0;double follow_seconds=0;
''')
    replace('    if(rld.enabled)eta=rld.Forcing(eta);', '''    const Scalar follow_raw_eta=eta;
    if(rld.enabled)eta=rld.Forcing(eta);
    if(follow_loose)eta=std::clamp(2*follow_raw_eta,(Scalar)1e-12,(Scalar).8);''')
    replace('''      auto model=full_model->Evaluate(p,s,have?d_best:dfull,k2mask);++full_model_calls;
      if(rld.collect)''','''      auto model=full_model->Evaluate(p,s,have?d_best:dfull,k2mask);++full_model_calls;
      if(follow_point && have && best_cost<cost){
        const auto begin=now();++follow_calls;
        CUDA_CHECK(cudaMemcpy(dfull,d_best,(size_t)n*sizeof(Scalar),cudaMemcpyDeviceToDevice));
        DoRetract(dfull,s_new);
        const auto changed=follow_overlay->Choose(p,s,s_new,Cdiag,tau_eff,dfull,follow_point);
        follow_changed+=changed;
        bool won=false;double candidate=best_cost,rho=-1;
        if(changed){
          DoRetract(dfull,s_new);candidate=ComputeCost(p,s_new,rk,rk_a2);
          if(std::isfinite(candidate)&&candidate<best_cost){
            auto alternative=full_model->Evaluate(p,s,dfull,k2mask);++full_model_calls;
            rho=alternative.prediction>0?(cost-candidate)/alternative.prediction:-1;
            if(std::isfinite(rho)&&rho>.1){
              best_cost=candidate;model=alternative;std::swap(d_best,dfull);won=true;++follow_wins;
            }
          }
        }
        follow_seconds+=std::chrono::duration<double>(now()-begin).count();
        std::printf("FOLLOW_POINT o=%d mode=%d changed=%llu candidate=%.17g rho=%.17g selected=%d\\n",k,follow_point,changed,candidate,rho,(int)won);
      }
      if(follow_point && BudgetExpired()){std::printf("BUDGET stop=after_point_overlay outer=%d\\n",k);break;}
      if(rld.collect)''')
    replace('  if(lm_point_rescue)std::printf("LM_RESCUE summary', '''  if(follow_point)std::printf("FOLLOW_POINT summary calls=%ld wins=%ld changed=%llu seconds=%.9g\\n",follow_calls,follow_wins,follow_changed,follow_seconds);
  if(lm_point_rescue)std::printf("LM_RESCUE summary''')
    source=build/'prism_followup.cu';source.write_text(code)
    # Existing point polish algorithm with an optional inexpensive geometry gate.
    refine=(headers/'point_refinement_candidate.cuh').read_text().split('struct PrismPointRefinement')[0]
    refine=refine.replace('MFPointRefine','MFFollowPointRefine').replace('PrismRefinePixel','PrismFollowPixel')
    refine=refine.replace('unsigned long long* changed){','unsigned long long* changed,bool selective){')
    refine=refine.replace('  if(point>=np)return;','''  if(point>=np)return;
  if(selective && !PrismLowParallax(offsets,order,ci,R,t,X,point,lane))return;''')
    (build/'follow_refine.cuh').write_text(refine)
    cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(headers),'-I'+str(P),'-I'+str(build),str(source),'-o',str(build/'prism-followup'),'-lcublas','-lcusolver']
    with (build/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
    (P/'build_manifest.json').write_text(json.dumps({'command':cmd,'binary_sha256':sha(build/'prism-followup'),'source_sha256':sha(source),'base_source_sha256':sha(src),'overlay_sha256':sha(P/'point_overlay.cuh')},indent=2)+'\n')
    print(build/'prism-followup',flush=True)
if __name__=='__main__':main()
