#!/usr/bin/env python3
"""Audit the packaged candidate, including exact patch equivalence to timed source."""
import pathlib,subprocess,json,re
from cached_benchmark_input import load_input
from audit_prism_state import audit
from build_tr_candidate import sha
ROOT=pathlib.Path('/workspace/prism-tr-candidate');BENCH=pathlib.Path(__file__).resolve().parent

def main():
 source=(ROOT/'source.cu').read_text();timed=pathlib.Path('/workspace/prism-tr-recurrence/source.cu').read_text();guard='\n  tr_residual_scales.resize(std::max(1,L),1.);tr_model_shifts.resize(std::max(1,L),0.);';assert source.replace(guard,'')==timed
 rows=[]
 for scene in ['trafalgar-126','dubrovnik-88','final-1936']:
  stem=ROOT/('validate-'+scene);data=pathlib.Path('/workspace/bal')/(scene+'.txt')
  print('PACKAGE VALIDATE',scene,flush=True)
  cmd=['python',str(BENCH/'run_tr_candidate.py'),'--problem',str(data),'--target','1e-100','--seconds','8' if scene=='final-1936' else '4','--iterations','16','--output',str(stem),'--audit-model']
  subprocess.run(cmd,check=True)
  dh,(dims,obs),initial=load_input(data,'/workspace/prism-caspar-expanded/cpu-cache');cost=audit(stem.with_suffix('.state'),dims,obs)
  log=stem.with_suffix('.log').read_text();m=re.search(r'RESULT .*?final_cost=(\S+) solve_seconds=(\S+)',log);assert m
  error=abs(cost-float(m[1]))/max(1,cost);assert error<1e-7
  errors=[float(re.search(r'error=(\S+)',l)[1]) for l in log.splitlines() if l.startswith('TR_RECURRENCE o=')];assert errors and max(errors)<1e-7
  rows.append(dict(scene=scene,audit_error=error,curvature_checks=len(errors),max_curvature_error=max(errors),native=float(m[2]),cost=cost))
 out=dict(binary_sha256=sha(ROOT/'prism-tr'),source_sha256=sha(ROOT/'source.cu'),only_change_from_timed_source='Resize recurrence metadata vectors to actual shift count, protecting other CLI configurations; values/formulas unchanged for confirmed one/five-shift TR.',rows=rows)
 (ROOT/'verification.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
if __name__=='__main__':main()
