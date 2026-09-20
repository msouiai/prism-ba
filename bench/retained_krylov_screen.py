#!/usr/bin/env python3
"""Frozen, short CPU-audited retained-basis ablation; no Caspar reruns."""
import argparse,csv,json,math,os,pathlib,re,subprocess,time
from profile_iterations import COMMON,sha
from novelty_ablation import EXEC
from audit_prism_state import observations,audit
ARMS={'legacy':{'OCA_DEMAND_MENU':'2'},'rebuild':{'OCA_DEMAND_MENU':'2','OCA_KRYLOV_REUSE':'2'},'reuse':{'OCA_DEMAND_MENU':'2','OCA_KRYLOV_REUSE':'1'}}
SCENES={'ladybug-1197':3,'dubrovnik-356':8}
def main():
 global ARMS,SCENES
 p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=pathlib.Path('/workspace/prism-recycle'));p.add_argument('--fixed-work',action='store_true');a=p.parse_args();root=a.root;
 if a.fixed_work: ARMS={k:v for k,v in ARMS.items() if k!='legacy'};SCENES={s:30 for s in SCENES}
 out=root/('fixed-work' if a.fixed_work else 'screen');out.mkdir(exist_ok=True);binary=root/'prism-frozen'
 base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};base.update(COMMON);base.update(EXEC);base.update(OCA_NSHIFTS='5',OCA_MENU_BACKTRACK='8',OCA_BACKTRACK_REARM='1',OCA_COMPACT_FRAGMENTS='2')
 plan=dict(arms=ARMS,scenes=SCENES,reps=2,binary_sha256=sha(binary),flags={k:v for k,v in base.items() if k.startswith('OCA_')})
 pp=root/('fixed-work-plan.json' if a.fixed_work else 'screen-plan.json')
 if pp.exists():assert json.loads(pp.read_text())==plan
 else:pp.write_text(json.dumps(plan,indent=2)+'\n')
 for si,(scene,budget) in enumerate(SCENES.items()):
  data=pathlib.Path('/workspace/bal')/(scene+'.txt');dh=sha(data);dims,obs=observations(data)
  for rep in [1,2]:
   order=list(ARMS);j=(si+rep-1)%len(ARMS);order=order[j:]+order[:j]
   if rep==2:order=order[::-1]
   for arm in order:
    stem=out/f'{scene}-{arm}-{rep}';jp=stem.with_suffix('.result.json')
    if jp.exists():continue
    assert not stem.with_suffix('.log').exists(),'inspect incomplete run before retrying'
    env=dict(base);env.update(ARMS[arm]);env['OCA_MAX_SECONDS']=str(budget)
    cmd=['flock','/tmp/prism_gpu.lock','timeout','90',str(binary),'--problem',str(data),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter',str({'ladybug-1197':30,'dubrovnik-356':100}[scene] if a.fixed_work else 100000),'--csv',str(stem.with_suffix('.csv')),'--state_out',str(stem.with_suffix('.state'))]
    assert sha(binary)==plan['binary_sha256']
    stem.with_suffix('.manifest.json').write_text(json.dumps(dict(command=cmd,flags={k:v for k,v in env.items() if k.startswith('OCA_')},data_sha256=dh,binary_sha256=plan['binary_sha256']),indent=2)+'\n')
    print('RUN',scene,arm,rep,flush=True);start=time.monotonic()
    with stem.with_suffix('.log').open('w') as f,stem.with_suffix('.stderr').open('w') as e:r=subprocess.run(cmd,env=env,stdout=f,stderr=e)
    row=dict(scene=scene,arm=arm,rep=rep,budget=budget,status='failed',returncode=r.returncode,process_seconds=time.monotonic()-start)
    if r.returncode==0:
     log=stem.with_suffix('.log').read_text();m=re.search(r'RESULT .*?iters=(\d+) final_cost=([\d.e+-]+) solve_seconds=([\d.e+-]+)',log);assert m
     cost=audit(stem.with_suffix('.state'),dims,obs);err=abs(cost-float(m[2]))/max(1,abs(cost));assert err<1e-7
     counts=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)',log);sc=re.search(r'\[scoring\].*?total_scored=(\d+)',log);assert counts and sc
     dm=re.search(r'DEMAND summary mode=(\d+) expansions=(\d+) narrow_accepts=(\d+) fallback_wins=(\d+) joint_rebuilds=(\d+)',log)
     with stem.with_suffix('.csv').open() as f:trace=list(csv.DictReader(line for line in f if not line.startswith('#')))
     costs=[float(t['cost']) for t in trace];assert all(math.isfinite(c) for c in costs);assert all(b<=a+1e-10*max(1,a) for a,b in zip(costs,costs[1:]))
     row.update(status='ok',cost=cost,seconds=float(m[3]),iters=int(m[1]),audit_relerr=err,accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]),scored=int(sc[1]),expansions=int(dm[2]) if dm else 0,narrow_accepts=int(dm[3]) if dm else 0,fallback_wins=int(dm[4]) if dm else 0,joint_rebuilds=int(dm[5]) if dm else 0,rearms=log.count('rearmed after meaningful'),saved_budget_fallback='BUDGET stop=saved_predeadline_fallback' in log,state_sha256=sha(stem.with_suffix('.state')))
    if r.returncode==0:
     records=[dict(zip(['outer','slots','reused','prior','depth','residual','tolerance','fallback'],map(float,m))) for m in re.findall(r'RECYCLE o=(\d+) slots=(\d+) reused=(\d+) prior=(\d+) depth=(\d+) residual=([\deE.+-]+|inf) tolerance=([\deE.+-]+) fallback=(\d+)',log)]
     assert all(t['residual']<=t['tolerance'] for t in records if not t['fallback'])
     row.update(recycle_attempts=len(records),reuse_hits=sum(t['reused'] for t in records),fallbacks=sum(t['fallback'] for t in records),retained_vectors=sum(t['prior'] for t in records if t['reused']))
    jp.write_text(json.dumps(row,indent=2)+'\n');print('DONE',row,flush=True)
    if row['status']!='ok':raise RuntimeError('failed run retained')
if __name__=='__main__':main()
