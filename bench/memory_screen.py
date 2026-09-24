#!/usr/bin/env python3
"""Short correctness/scaling screen of exact FP64 fragment deduplication."""
import argparse,json,os,pathlib,re,subprocess,sys
from profile_iterations import COMMON,sha
from novelty_ablation import EXEC
from audit_prism_state import observations,audit

def main():
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['gates','largest']);p.add_argument('--scene',default='final-13682');p.add_argument('--mode',type=int,choices=[1,2],default=1);p.add_argument('--root',type=pathlib.Path,default=pathlib.Path('/workspace/prism-memory'));a=p.parse_args();root=a.root
 binary=root/'prism-frozen';reference=pathlib.Path('/workspace/prism-validation/prism-frozen')
 if a.phase=='largest':
  import validation_study as study
  study.COMMON.update(OCA_COMPACT_FRAGMENTS=str(a.mode))
  sys.argv=['validation_study.py','budgets','--root',str(root),'--binary',str(binary),'--caspar','/workspace/prism-validation/caspar-frozen','--scenes',a.scene,'--reps','1','--budget-seconds','30','--timeout','180','--keep-going']
  study.main();return
 out=root/'gates';out.mkdir(exist_ok=True)
 env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};env.update(COMMON);env.update(EXEC);env.update(OCA_NSHIFTS='5',OCA_MENU_BACKTRACK='8',OCA_BACKTRACK_REARM='1')
 rows=[]
 for scene,arms,outer in [('ladybug-49',['reference','off','compact'],12),('dubrovnik-173',['reference','compact'],12),('final-4585',['reference','compact'],10)]:
  data=pathlib.Path('/workspace/bal')/(scene+'.txt');dims,obs=observations(data)
  for arm in arms:
   stem=out/(scene+'-'+arm);state=stem.with_suffix('.state');runenv=dict(env)
   if arm=='compact':runenv['OCA_COMPACT_FRAGMENTS']=str(a.mode)
   exe=reference if arm=='reference' else binary
   cmd=['flock','/tmp/prism_gpu.lock','timeout','90',str(exe),'--problem',str(data),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter',str(outer),'--csv',str(stem.with_suffix('.csv')),'--state_out',str(state)]
   assert not stem.with_suffix('.log').exists(),'do not overwrite retained runs'
   manifest=dict(command=cmd,binary_sha256=sha(exe),data_sha256=sha(data),flags={k:v for k,v in runenv.items() if k.startswith('OCA_')})
   stem.with_suffix('.manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
   print('RUN',scene,arm,flush=True)
   with stem.with_suffix('.log').open('w') as f,stem.with_suffix('.stderr').open('w') as e:proc=subprocess.run(cmd,env=runenv,stdout=f,stderr=e)
   assert proc.returncode==0,(scene,arm,proc.returncode)
   log=stem.with_suffix('.log').read_text();res=re.search(r'RESULT .*?iters=(\d+) final_cost=([\d.e+-]+) solve_seconds=([\d.e+-]+)',log);assert res
   cost=audit(state,dims,obs);err=abs(cost-float(res[2]))/max(1,abs(cost));assert err<1e-7
   counts=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)',log);assert counts
   row=dict(scene=scene,arm=arm,iters=int(res[1]),cost=cost,seconds=float(res[3]),audit_relerr=err,accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]),state_sha256=sha(state))
   stem.with_suffix('.result.json').write_text(json.dumps(row,indent=2)+'\n');rows.append(row);print('DONE',row,flush=True)
 # End-to-end trajectories are not bitwise gates: assembly uses atomics.
 # Fixed-input kernel gate separately requires bitwise equality.
 for scene in {r['scene'] for r in rows}:
  group=[r for r in rows if r['scene']==scene];ref=next(r for r in group if r['arm']=='reference')
  for r in group:
   r['relative_to_reference_cost']=r['cost']/ref['cost']-1
   assert abs(r['relative_to_reference_cost'])<.01,('trajectory review required',r)
 (root/'gate-summary.json').write_text(json.dumps(rows,indent=2)+'\n')
if __name__=='__main__':main()
