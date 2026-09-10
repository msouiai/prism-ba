#!/usr/bin/env python3
"""Short controlled screen of exact-bound backtracking; audit runs are untimed."""
import json,os,pathlib,re,subprocess,time,statistics
from profile_iterations import COMMON,sha
from novelty_ablation import EXEC
from audit_prism_state import observations,audit
ROOT=pathlib.Path('/workspace/prism-bounded-cost')
TARGETS={'ladybug-1197':(366600,6),'dubrovnik-356':(754100,12)}

def main():
 binary=ROOT/'prism-frozen';out=ROOT/'runs';out.mkdir(exist_ok=True)
 base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}
 base.update(COMMON);base.update(EXEC)
 base.update(OCA_NSHIFTS='5',OCA_MENU_BACKTRACK='8',OCA_BACKTRACK_REARM='1',OCA_COMPACT_FRAGMENTS='2',OCA_DEMAND_MENU='2')
 plan=dict(targets=TARGETS,reps=2,binary_sha256=sha(binary),flags={k:v for k,v in base.items() if k.startswith('OCA_')},audit='one shadow full-cost run per scene before timing; 30-second audit cap')
 (ROOT/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
 rows=[]
 for scene,(target,cap) in TARGETS.items():
  data=pathlib.Path('/workspace/bal')/(scene+'.txt');dims,obs=observations(data)
  for rep,arm in [(0,'audit'),(1,'reference'),(1,'bounded'),(2,'bounded'),(2,'reference')]:
   stem=out/f'{scene}-{arm}-{rep}';assert not stem.with_suffix('.log').exists()
   env=dict(base,OCA_MAX_SECONDS=str(30 if arm=='audit' else cap),OCA_TARGET_COST=str(target))
   if arm!='reference':env['OCA_BOUNDED_BACKTRACK']='1'
   if arm=='audit':env['OCA_BOUNDED_BACKTRACK_AUDIT']='1'
   cmd=['flock','/tmp/prism_gpu.lock','timeout','60',str(binary),'--problem',str(data),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','100000','--csv',str(stem.with_suffix('.csv')),'--state_out',str(stem.with_suffix('.state'))]
   assert sha(binary)==plan['binary_sha256']
   stem.with_suffix('.manifest.json').write_text(json.dumps(dict(command=cmd,flags={k:v for k,v in env.items() if k.startswith('OCA_')},binary_sha256=plan['binary_sha256'],data_sha256=sha(data)),indent=2)+'\n')
   print('RUN',scene,arm,rep,flush=True)
   with stem.with_suffix('.log').open('w') as f,stem.with_suffix('.stderr').open('w') as e:r=subprocess.run(cmd,env=env,stdout=f,stderr=e)
   assert r.returncode==0,(scene,arm,r.returncode)
   log=stem.with_suffix('.log').read_text();m=re.search(r'RESULT .*?iters=(\d+) final_cost=([\d.e+-]+) solve_seconds=([\d.e+-]+)',log);assert m
   cost=audit(stem.with_suffix('.state'),dims,obs);err=abs(cost-float(m[2]))/max(1,abs(cost));assert err<1e-7
   crossing=re.search(r'TARGET reached outer=(\d+) seconds=(\S+)',log)
   counts=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)',log);sc=re.search(r'\[scoring\] menu_evals=(\d+) alpha_evals=(\d+) backtrack_evals=(\d+) total_scored=(\d+)',log)
   bc=re.search(r'BOUNDED_COST calls=(\d+) rejected=(\d+) blocks=(\d+) skipped=(\d+) audited=(\d+)',log)
   row=dict(scene=scene,arm=arm,rep=rep,cost=cost,seconds=float(m[3]),crossing_seconds=float(crossing[2]) if crossing else None,hit=bool(crossing and float(crossing[2])<=(30 if arm=='audit' else cap) and cost<=target),iters=int(m[1]),audit_relerr=err,accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]),menu=int(sc[1]),alpha=int(sc[2]),backtrack=int(sc[3]),scored=int(sc[4]))
   if bc:row.update(zip(['bounded_calls','early_rejects','blocks','skipped','shadow_audits'],map(int,bc.groups())))
   if arm=='audit':assert row.get('shadow_audits',0)==row['backtrack'] and row['hit']
   stem.with_suffix('.result.json').write_text(json.dumps(row,indent=2)+'\n');rows.append(row)
   (ROOT/'results.json').write_text(json.dumps(rows,indent=2)+'\n');print('DONE',row,flush=True)
 summary={}
 for scene in TARGETS:
  x={arm:[r for r in rows if r['scene']==scene and r['arm']==arm] for arm in ['reference','bounded']}
  summary[scene]={arm:dict(hits=sum(r['hit'] for r in rs),median_crossing=statistics.median(r['crossing_seconds'] for r in rs) if all(r['hit'] for r in rs) else None) for arm,rs in x.items()}
  if all(r['hit'] for rs in x.values() for r in rs):summary[scene]['speedup']=summary[scene]['reference']['median_crossing']/summary[scene]['bounded']['median_crossing']
 (ROOT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
