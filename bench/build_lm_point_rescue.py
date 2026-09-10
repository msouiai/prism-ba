"""Frozen ablation binary plus isolated LM failed-step point rescue."""
import json
import pathlib
import shutil
import subprocess
from build_tr_candidate import sha

base = pathlib.Path('/workspace/prism-tr-novelty-ablation/build')
root = pathlib.Path('/tmp/prism-lm-point-rescue/build')
root.mkdir(parents=True)
m = json.loads((base / 'manifest.json').read_text())
assert sha(base / 'source.cu') == m['source_sha256']
assert all(sha(base / 'headers' / k) == v for k, v in m['headers_sha256'].items())
shutil.copytree(base / 'headers', root / 'headers')
shutil.copy2('gpu/point_refinement_candidate.cuh', root / 'headers')
s = (base / 'source.cu').read_text()


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub('#include "point_safeguard.cuh"', '#include "point_safeguard.cuh"\n#include "point_refinement_candidate.cuh"')
sub('  double lm_nu=2,lm_rho=0,lm_prediction=0;', '''  double lm_nu=2,lm_rho=0,lm_prediction=0;
  const int lm_point_rescue=getenv("OCA_LM_POINT_RESCUE")?atoi(getenv("OCA_LM_POINT_RESCUE")):0;
  if(lm_point_rescue<0||lm_point_rescue>2||(lm_point_rescue&&!classical_lm))throw std::runtime_error("LM point rescue requires classical LM; 1=zero/full, 2=one nonlinear point GN step");
  std::unique_ptr<PrismPointSafeguard> lm_safe;
  std::unique_ptr<PrismPointRefinement> lm_refine;
  if(lm_point_rescue==1)lm_safe=std::make_unique<PrismPointSafeguard>();
  if(lm_point_rescue==2)lm_refine=std::make_unique<PrismPointRefinement>();
  long lm_rescue_calls=0,lm_rescue_wins=0;double lm_rescue_seconds=0;
''')
sub('    if(classical_lm){\n      auto model=', '''    if(classical_lm && lm_point_rescue && !have){
      auto begin=now();++lm_rescue_calls;
      // The single terminal Score leaves its failed full proposal in dfull.
      // Both alternatives hold those proposed cameras fixed and alter points.
      DoRetract(dfull,s_new);
      unsigned long long changed=lm_point_rescue==1?lm_safe->Choose(p,s,s_new,dfull):lm_refine->Choose(p,s_new,dfull);
      Scalar dc=0,dp=0;cublasDdot(blas,n_cf,bc,1,dfull,1,&dc);cublasDdot(blas,n_p,bp,1,dfull+n_cf,1,&dp);
      double slope=dc+dp,candidate=std::numeric_limits<double>::infinity();bool won=false;
      if(changed && std::isfinite(slope) && slope<0){
        DoRetract(dfull,s_new);candidate=ComputeCost(p,s_new,rk,rk_a2);
        if(std::isfinite(candidate)&&candidate<cost&&candidate<=cost+1e-4*slope){
          best_cost=candidate;best_sh=0;best_ck=cg_broke?cg_it+1:maxck;have=true;
          std::swap(d_best,dfull);won=true;++lm_rescue_wins;
        }
      }
      lm_rescue_seconds+=std::chrono::duration<double>(now()-begin).count();
      std::printf("LM_RESCUE o=%d mode=%d changed=%llu slope=%.17g candidate=%.17g current=%.17g won=%d\\n",k,lm_point_rescue,changed,slope,candidate,(double)cost,(int)won);
    }
    if(classical_lm){
      auto model=''')
sub('  if(point_safeguard_mode)std::printf("POINT_SAFE summary', '''  if(lm_point_rescue)std::printf("LM_RESCUE summary calls=%ld wins=%ld seconds=%.9g\\n",lm_rescue_calls,lm_rescue_wins,lm_rescue_seconds);
  if(point_safeguard_mode)std::printf("POINT_SAFE summary''')
(root / 'source.cu').write_text(s)
cmd = ['nvcc', '-O3', '-DNDEBUG', '-std=c++17', '-arch=sm_89', '-I/usr/include/eigen3', '-I'+str(root/'headers'), str(root/'source.cu'), '-o', str(root/'prism-tr'), '-lcublas', '-lcusolver']
with (root / 'build.log').open('w') as f:
    subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, check=True)
(root/'manifest.json').write_text(json.dumps(dict(command=cmd, source_sha256=sha(root/'source.cu'), binary_sha256=sha(root/'prism-tr'), headers_sha256={p.name:sha(p) for p in (root/'headers').iterdir()}, parent=m, scope='LM failed-step rescue only; fixed proposed cameras, zero/full point menu or one bounded point GN step. Original full GN acceptance and Nielsen controller retained.'), indent=2))
