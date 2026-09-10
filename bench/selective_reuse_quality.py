#!/usr/bin/env python3
"""First accepted crossing of frozen common quality targets, with CPU audits."""
import argparse,csv,json,math,os,pathlib,re,subprocess,time
from profile_iterations import COMMON,sha
from novelty_ablation import EXEC
from audit_prism_state import observations,audit
ARMS={'legacy':{'OCA_DEMAND_MENU':'2'},'always':{'OCA_DEMAND_MENU':'2','OCA_KRYLOV_REUSE':'3'},'selective':{'OCA_DEMAND_MENU':'2','OCA_KRYLOV_REUSE':'5'}}

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=pathlib.Path('/workspace/prism-recycle-selective'));a=p.parse_args();root=a.root;out=root/'runs';out.mkdir(exist_ok=True);binary=root/'prism-frozen';targets=json.loads((root/'targets.json').read_text())
 base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};base.update(COMMON);base.update(EXEC);base.update(OCA_NSHIFTS='5',OCA_MENU_BACKTRACK='8',OCA_BACKTRACK_REARM='1',OCA_COMPACT_FRAGMENTS='2')
 plan=dict(arms=ARMS,targets=targets,reps=2,binary_sha256=sha(binary),flags={k:v for k,v in base.items() if k.startswith('OCA_')})
 pp=root/'plan.json'
 if pp.exists():assert json.loads(pp.read_text())==plan
 else:pp.write_text(json.dumps(plan,indent=2)+'\n')
 for si,(scene,config) in enumerate(targets.items()):
  target=config['target'];cap=config['cap_seconds'];data=pathlib.Path('/workspace/bal')/(scene+'.txt');dh=sha(data);dims,obs=observations(data)
  for rep in [1,2]:
   order=list(ARMS);j=(si+rep-1)%len(ARMS);order=order[j:]+order[:j]
   if rep==2:order=order[::-1]
   for arm in order:
    stem=out/f'{scene}-{arm}-{rep}';jp=stem.with_suffix('.result.json')
    if jp.exists():continue
    assert not stem.with_suffix('.log').exists(),'inspect incomplete run before retrying'
    env=dict(base);env.update(ARMS[arm]);env.update(OCA_MAX_SECONDS=str(cap),OCA_TARGET_COST=str(target))
    cmd=['flock','/tmp/prism_gpu.lock','timeout','60',str(binary),'--problem',str(data),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','100000','--csv',str(stem.with_suffix('.csv')),'--state_out',str(stem.with_suffix('.state'))]
    assert sha(binary)==plan['binary_sha256']
    stem.with_suffix('.manifest.json').write_text(json.dumps(dict(command=cmd,flags={k:v for k,v in env.items() if k.startswith('OCA_')},data_sha256=dh,binary_sha256=plan['binary_sha256']),indent=2)+'\n')
    print('RUN',scene,arm,rep,flush=True);start=time.monotonic()
    with stem.with_suffix('.log').open('w') as f,stem.with_suffix('.stderr').open('w') as e:r=subprocess.run(cmd,env=env,stdout=f,stderr=e)
    row=dict(scene=scene,arm=arm,rep=rep,target=target,cap_seconds=cap,status='failed',returncode=r.returncode,process_seconds=time.monotonic()-start)
    if r.returncode==0:
     log=stem.with_suffix('.log').read_text();m=re.search(r'RESULT .*?iters=(\d+) final_cost=([\d.e+-]+) solve_seconds=([\d.e+-]+)',log);assert m
     cost=audit(stem.with_suffix('.state'),dims,obs);err=abs(cost-float(m[2]))/max(1,abs(cost));assert err<1e-7
     counts=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)',log);sc=re.search(r'\[scoring\].*?total_scored=(\d+)',log);assert counts and sc
     dm=re.search(r'DEMAND summary mode=(\d+) expansions=(\d+) narrow_accepts=(\d+) fallback_wins=(\d+) joint_rebuilds=(\d+)',log)
     with stem.with_suffix('.csv').open() as f:trace=list(csv.DictReader(line for line in f if not line.startswith('#')))
     costs=[float(t['cost']) for t in trace];assert all(math.isfinite(c) for c in costs);assert all(b<=a+1e-10*max(1,a) for a,b in zip(costs,costs[1:]))
     crossings=re.findall(r'TARGET reached outer=(\d+) seconds=(\S+) cost=(\S+) threshold=(\S+)',log);assert len(crossings)<=1
     crossing=None;hit=False;reason='budget' if 'BUDGET stop=' in log else 'solver stopped above target'
     if crossings:
      outer,elapsed,reported,threshold=crossings[0];crossing=float(elapsed);assert float(threshold)==target;assert cost<=target,'CPU rejected target certification'
      assert abs(float(reported)-float(m[2]))<1e-8*max(1,cost)
      assert int(trace[-1]['iter'])==int(outer)
      assert all(c>target*(1-1e-8)-1e-8 for c in costs[:-1]),'not first accepted crossing'
      assert float(m[3])+1e-5>=crossing
      hit=crossing<=cap;reason='target' if hit else 'crossing after cap'
     row.update(status='ok',hit=hit,stop_reason=reason,crossing_seconds=crossing,cost=cost,seconds=float(m[3]),iters=int(m[1]),audit_relerr=err,accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]),scored=int(sc[1]),expansions=int(dm[2]) if dm else 0,narrow_accepts=int(dm[3]) if dm else 0,fallback_wins=int(dm[4]) if dm else 0,joint_rebuilds=int(dm[5]) if dm else 0,state_sha256=sha(stem.with_suffix('.state')))
    if r.returncode==0:
     decisions=[tuple(map(int,m)) for m in re.findall(r'SELECT_REUSE o=(\d+) depth=(\d+) decision=(\d+) cooldown=(\d+)',log)]
     assert len(decisions)==log.count('SELECT_REUSE o=')
     if arm=='selective':
      pending=row['expansions']-len(decisions)
      assert pending in (0,1) and (pending==0 or 'BUDGET stop=' in log)
      assert log.count('CAPTURE o=')==sum(d[2]==0 for d in decisions)
     row.update(reuse_selected=sum(d[2]==0 for d in decisions),cheap_skips=sum(d[2]==1 for d in decisions),capacity_skips=sum(d[2]==2 for d in decisions),cooldown_skips=sum(d[2]==3 for d in decisions),capture_fallbacks=sum(int(m) for m in re.findall(r'CAPTURE o=.*?fallback=(\d+)',log)))
    jp.write_text(json.dumps(row,indent=2)+'\n');print('DONE',{k:row.get(k) for k in ['scene','arm','rep','status','hit','crossing_seconds','cost','seconds','stop_reason']},flush=True)
    if row['status']!='ok':raise RuntimeError('failed run retained')
if __name__=='__main__':main()
