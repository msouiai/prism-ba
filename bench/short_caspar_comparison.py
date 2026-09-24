#!/usr/bin/env python3
"""Two-scene interleaved target screen with shared exported-state CPU audits."""
import pathlib,json,os,subprocess,re,csv,statistics
from profile_iterations import COMMON,sha
from novelty_ablation import EXEC
from audit_prism_state import observations,audit
root=pathlib.Path('/workspace/prism-caspar-short');out=root/'runs';out.mkdir(exist_ok=True)
binaries={'prism':'/workspace/prism-local-curvature/prism-v1','caspar':str(root/'caspar-frozen')}
base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};jobs=[]
scenes=[('ladybug-1197',366600,6),('dubrovnik-356',754100,8)];arms=['single','multi','paired','caspar']
for rep in [1,2]:
 for scene,target,cap in (scenes if rep==1 else list(reversed(scenes))):
  for arm in (arms if rep==1 else list(reversed(arms))):jobs.append(dict(scene=scene,target=target,cap=cap,arm=arm,rep=rep))
plan=dict(jobs=jobs,binaries=binaries,hashes={k:sha(v) for k,v in binaries.items()})
p=root/'plan.json'
if p.exists():assert json.loads(p.read_text())==plan
else:p.write_text(json.dumps(plan,indent=2)+'\n')
cache={};rows=[]
for j in jobs:
 name=f"{j['scene']}-{j['arm']}-{j['rep']}";stem=out/name;rp=stem.with_suffix('.result.json')
 if rp.exists():rows.append(json.loads(rp.read_text()));continue
 assert not stem.with_suffix('.log').exists(),'Incomplete run retained; inspect before resuming'
 scene=j['scene'];data=pathlib.Path('/workspace/bal')/(scene+'.txt')
 if scene not in cache:cache[scene]=(sha(data),observations(data))
 datahash,(dims,obs)=cache[scene];caspar=j['arm']=='caspar';binary=binaries['caspar' if caspar else 'prism'];env=dict(base)
 if caspar:
  env.update(CASPAR_MAX_SECONDS=str(j['cap']),CASPAR_TARGET_COST=str(j['target']),CASPAR_STATE_OUT=str(stem.with_suffix('.state')))
  cmd=['flock','/tmp/prism_gpu.lock','timeout','60',binary,str(data),'100000','default']
 else:
  env.update(COMMON);env.update(EXEC);env.update(OCA_NSHIFTS='1' if j['arm']=='single' else '5',OCA_MENU_BACKTRACK='8',OCA_BACKTRACK_REARM='1',OCA_COMPACT_FRAGMENTS='2',OCA_DEMAND_MENU='2' if j['arm']=='paired' else '0',OCA_TARGET_COST=str(j['target']),OCA_MAX_SECONDS=str(j['cap']))
  cmd=['flock','/tmp/prism_gpu.lock','timeout','60',binary,'--problem',str(data),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','100000','--csv',str(stem.with_suffix('.csv')),'--state_out',str(stem.with_suffix('.state'))]
 assert sha(binary)==plan['hashes']['caspar' if caspar else 'prism']
 stem.with_suffix('.manifest.json').write_text(json.dumps(dict(job=j,command=cmd,flags={k:v for k,v in env.items() if k.startswith(('OCA_','CASPAR_'))},binary_sha256=sha(binary),data_sha256=datahash),indent=2)+'\n');print('RUN',name,flush=True)
 with stem.with_suffix('.log').open('w') as f,stem.with_suffix('.stderr').open('w') as e:r=subprocess.run(cmd,env=env,stdout=f,stderr=e)
 assert r.returncode==0,(name,r.returncode)
 text=stem.with_suffix('.log').read_text();cost=audit(stem.with_suffix('.state'),dims,obs);row=dict(j,cost=cost,state_sha256=sha(stem.with_suffix('.state')))
 if caspar:
  m=re.search(r'RESULT exit=(\d+) iters=(\d+) final_score=(\S+) runtime=(\S+)',text);check=re.search(r'CHECK final_score=(\S+)',text);setup=re.search(r'INITIAL score=(\S+) setup_seconds=(\S+)',text);assert m and check and setup
  trace=[dict(iter=int(i),native_cost=float(c),seconds=float(t)) for i,c,t in re.findall(r'TRACE iter=(\d+) cost=(\S+) seconds=(\S+)',text)];native_hit=bool(trace and trace[-1]['native_cost']<=j['target']);cross=trace[-1]['seconds'] if native_hit else None
  row.update(seconds=float(m[4]),exit=int(m[1]),iters=int(m[2]),native_cost=float(m[3]),setup_seconds=float(setup[2]),reported_cpu_cost=float(check[1]),trace=trace,native_target_hit=native_hit)
  row['native_cpu_gap']=abs(cost-row['native_cost'])/max(1,abs(cost));reported=row['reported_cpu_cost']
 else:
  m=re.search(r'RESULT .*?iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)',text);target=re.search(r'TARGET reached outer=(\d+) seconds=(\S+)',text);assert m
  cross=float(target[2]) if target else None;row.update(seconds=float(m[3]),iters=int(m[1]),setup_seconds=0);reported=float(m[2])
  with stem.with_suffix('.csv').open() as f:trace=list(csv.DictReader(line for line in f if not line.startswith('#')))
  costs=[float(x['cost']) for x in trace];assert all(b<=a+1e-10*max(1,a) for a,b in zip(costs,costs[1:]))
 error=abs(cost-reported)/max(1,abs(cost));assert error<1e-7,(name,error)
 row.update(audit_error=error,crossing_seconds=cross,hit=bool(cross is not None and cross<=j['cap'] and cost<=j['target']))
 row['setup_inclusive_crossing']=cross+row['setup_seconds'] if row['hit'] else None
 rp.write_text(json.dumps(row,indent=2)+'\n');rows.append(row);print('DONE',name,'hit',row['hit'],'cross',cross,'cost',cost,flush=True)
(root/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
summary={}
for scene,_,_ in scenes:
 summary[scene]={}
 for arm in arms:
  rr=[r for r in rows if r['scene']==scene and r['arm']==arm];allhit=all(r['hit'] for r in rr)
  summary[scene][arm]=dict(n=len(rr),hits=sum(r['hit'] for r in rr),crossing_seconds=statistics.median(r['crossing_seconds'] for r in rr) if allhit else None,setup_inclusive_crossing=statistics.median(r['setup_inclusive_crossing'] for r in rr) if allhit else None,cost=statistics.median(r['cost'] for r in rr),seconds=statistics.median(r['seconds'] for r in rr))
(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
