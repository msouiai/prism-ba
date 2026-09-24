#!/usr/bin/env python3
"""Manifest-driven short BA runs, with independent exported-state validation."""
import argparse,csv,json,os,pathlib,re,subprocess,time,math
from profile_iterations import COMMON,sha
from novelty_ablation import EXEC
from audit_prism_state import observations,audit

def main():
 p=argparse.ArgumentParser();p.add_argument('plan',type=pathlib.Path);a=p.parse_args();plan=json.loads(a.plan.read_text());root=pathlib.Path(plan['root']);out=root/plan['stage'];out.mkdir(parents=True,exist_ok=True)
 base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};base.update(COMMON);base.update(EXEC);base.update(OCA_NSHIFTS='5',OCA_MENU_BACKTRACK='8',OCA_BACKTRACK_REARM='1',OCA_COMPACT_FRAGMENTS='2',OCA_DEMAND_MENU='2')
 cached={}
 for job in plan['jobs']:
  scene=job['scene'];stem=out/job['name'];jp=stem.with_suffix('.result.json')
  if jp.exists():continue
  assert not stem.with_suffix('.log').exists(),'incomplete run retained; inspect before retry'
  data=pathlib.Path(job['data']) if 'data' in job else pathlib.Path('/workspace/bal')/(scene+'.txt')
  data=data.resolve()
  if data not in cached:cached[data]=(sha(data),observations(data))
  datahash,(dims,obs)=cached[data];binary=pathlib.Path(job.get('binary',plan['binary']));env=dict(base);env.update(job.get('flags',{}));env['OCA_MAX_SECONDS']=str(job['cap'])
  if 'target' in job:env['OCA_TARGET_COST']=str(job['target'])
  if job.get('trace'):env['OCA_LEARN_LOG']=str(stem.with_suffix('.jsonl'))
  cmd=['flock','/tmp/prism_gpu.lock','timeout','60',str(binary),'--problem',str(data),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter',str(job.get('iters',100000)),'--csv',str(stem.with_suffix('.csv')),'--state_out',str(stem.with_suffix('.state'))]
  manifest=dict(job=job,command=cmd,flags={k:v for k,v in env.items() if k.startswith('OCA_')},binary_sha256=sha(binary),data_sha256=datahash)
  stem.with_suffix('.manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('RUN',job['name'],flush=True)
  start=time.monotonic()
  with stem.with_suffix('.log').open('w') as f,stem.with_suffix('.stderr').open('w') as e:r=subprocess.run(cmd,env=env,stdout=f,stderr=e)
  assert r.returncode==0,(job['name'],r.returncode)
  log=stem.with_suffix('.log').read_text();m=re.search(r'RESULT .*?iters=(\d+) final_cost=([\d.e+-]+) solve_seconds=([\d.e+-]+)',log);assert m
  cost=audit(stem.with_suffix('.state'),dims,obs);err=abs(cost-float(m[2]))/max(1,abs(cost));assert err<1e-7
  with stem.with_suffix('.csv').open() as f:trace=list(csv.DictReader(line for line in f if not line.startswith('#')))
  costs=[float(t['cost']) for t in trace];assert all(math.isfinite(c) for c in costs);assert all(b<=a+1e-10*max(1,a) for a,b in zip(costs,costs[1:]))
  count=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)',log);sc=re.search(r'\[scoring\] menu_evals=(\d+) alpha_evals=(\d+) backtrack_evals=(\d+) total_scored=(\d+)',log);bt=re.search(r'\[menu-backtrack\] trials=(\d+) rescues=(\d+) evals=(\d+)',log)
  crossing=re.search(r'TARGET reached outer=(\d+) seconds=(\S+)',log)
  row=dict(job,seconds=float(m[3]),cost=cost,audit_relerr=err,actual_iters=int(m[1]),accepts=int(count[1]),rejects=int(count[2]),matvecs=int(count[3]),menu=int(sc[1]),alpha=int(sc[2]),backtrack=int(sc[3]),scored=int(sc[4]),bt_trials=int(bt[1]),bt_rescues=int(bt[2]),process_seconds=time.monotonic()-start)
  if 'target' in job:
   row.update(crossing_seconds=float(crossing[2]) if crossing else None,hit=bool(crossing and float(crossing[2])<=job['cap'] and cost<=job['target']))
   if crossing:
    assert all(c>job['target']*(1-1e-8)-1e-8 for c in costs[:-1]);assert int(trace[-1]['iter'])==int(crossing[1])
  policy=re.search(r'BT_POLICY mode=(\d+) searches=(\d+) predicted=(\d+) probes=(\d+) recoveries=(\d+)',log)
  if policy:row.update(zip(['mode','searches','predicted','probes','recoveries'],map(int,policy.groups())))
  upward=re.search(r'BT_UPWARD probes=(\d+) wins=(\d+)',log)
  if upward:row.update(upward_probes=int(upward[1]),upward_wins=int(upward[2]))
  pt=re.search(r'POINT_TRUST summary mode=(\d+) updates=(\d+) invalid=(\d+) kernels=(\d+) seconds=(\S+)',log)
  if pt:row.update(point_mode=int(pt[1]),point_updates=int(pt[2]),point_invalid=int(pt[3]),point_kernels=int(pt[4]),point_seconds=float(pt[5]))
  fm=re.search(r'FULL_MODEL summary calls=(\d+) nonpositive=(\d+) seconds=(\S+)',log)
  if fm:row.update(full_model_calls=int(fm[1]),full_model_nonpositive=int(fm[2]),full_model_seconds=float(fm[3]))
  ss=re.search(r'SUBSPACE summary mode=(\d+) calls=(\d+) evals=(\d+) wins=(\d+) invalid=(\d+) seconds=(\S+)',log)
  if ss:row.update(subspace_mode=int(ss[1]),subspace_calls=int(ss[2]),subspace_evals=int(ss[3]),subspace_wins=int(ss[4]),subspace_invalid=int(ss[5]),subspace_seconds=float(ss[6]))
  split=re.search(r'REPAIR_SPLIT summary camera_down=(\d+) point_down=(\d+) seconds=(\S+)',log)
  if split:row.update(split_camera_down=int(split[1]),split_point_down=int(split[2]),split_seconds=float(split[3]))
  probes=re.search(r'REPAIR_PROBES summary evaluated=(\d+) skipped=(\d+)',log)
  if probes:row.update(split_probe_evals=int(probes[1]),split_probe_skips=int(probes[2]))
  rm=re.search(r'REPAIR_MODEL summary mode=(\d+) calls=(\d+) invalid=(\d+) down=(\d+) up=(\d+) seconds=(\S+)',log)
  if rm:row.update(repair_mode=int(rm[1]),repair_calls=int(rm[2]),repair_invalid=int(rm[3]),repair_down=int(rm[4]),repair_up=int(rm[5]),repair_seconds=float(rm[6]))
  ps=re.search(r'POINT_SAFE summary calls=(\d+) evals=(\d+) wins=(\d+) frozen=(\d+) seconds=(\S+)',log)
  if ps:row.update(point_safe_calls=int(ps[1]),point_safe_evals=int(ps[2]),point_safe_wins=int(ps[3]),point_safe_frozen=int(ps[4]),point_safe_seconds=float(ps[5]))
  assert row.get('subspace_evals',0)<=row['bt_trials']
  assert row['backtrack']<=8*row['bt_trials']+row.get('subspace_evals',0)+row.get('point_safe_evals',0) and row['bt_rescues']<=row['bt_trials']
  jp.write_text(json.dumps(row,indent=2)+'\n');print('DONE',row,flush=True)
 (out/'results.json').write_text(json.dumps([json.loads((out/j['name']).with_suffix('.result.json').read_text()) for j in plan['jobs']],indent=2)+'\n')
if __name__=='__main__':main()
