#!/usr/bin/env python3
"""Short two-stage BA experiment; charge abandoned solver time and retain best state.

Native budgets exclude process loading/export. Total process wall is reported
separately, with independent CPU audits performed after all solver stages.
"""
import argparse,csv,json,math,os,pathlib,re,shutil,subprocess,time
from profile_iterations import COMMON,sha,score_initial
from novelty_ablation import EXEC
from audit_prism_state import observations,audit
from cached_benchmark_input import load_input

def main():
 ap=argparse.ArgumentParser();ap.add_argument('plan',type=pathlib.Path);args=ap.parse_args()
 plan=json.loads(args.plan.read_text());r=pathlib.Path(plan['root']);out=r/'screen';out.mkdir(exist_ok=True)
 base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}
 base.update(COMMON);base.update(EXEC)
 base.update(OCA_NSHIFTS='5',OCA_MENU_BACKTRACK='8',OCA_BACKTRACK_REARM='1',OCA_COMPACT_FRAGMENTS='2',OCA_POINT_SAFEGUARD='1')
 cache={};binary=pathlib.Path(plan['binary']);binary_hash=sha(binary)
 for job in plan['jobs']:
  stem=out/job['name'];result=stem.with_suffix('.result.json')
  if result.exists():continue
  assert not list(out.glob(job['name']+'-stage*.log')),'inspect incomplete run before retry'
  data=pathlib.Path(job.get('data',str(pathlib.Path('/workspace/bal')/(job['scene']+'.txt')))).resolve()
  if data not in cache:cache[data]=load_input(data,job.get('cpu_cache'))
  datahash,(dims,obs),initial=cache[data];stages=[];native_used=0.;wall_start=time.monotonic()
  print('RUN',job['name'],flush=True)
  for index in range(2):
   remaining=job['cap']-native_used
   if remaining<=0:break
   ss=out/(job['name']+'-stage'+str(index));env=dict(base)
   if job['arm']=='single':env['OCA_NSHIFTS']='1'
   if job.get('profile',False):env['OCA_PROFILE']='1'
   mode='2' if index or job['arm']=='paired' else ('3' if job['arm']=='restart' else '0')
   env.update(OCA_DEMAND_MENU=mode,OCA_SWITCH_RESTART='1' if mode=='3' else '0',
              OCA_MAX_SECONDS=str(remaining),OCA_TARGET_COST=str(job.get('prism_stop_target',job['target'])))
   if job.get('learn_log',True):env['OCA_LEARN_LOG']=str(ss.with_suffix('.jsonl'))
   else:assert mode!='3', 'restart audit requires attempt logging'
   cmd=['flock','/tmp/prism_gpu.lock','timeout',str(job.get('process_timeout',60)),str(binary),'--problem',str(data),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','100000','--csv',str(ss.with_suffix('.csv')),'--state_out',str(ss.with_suffix('.state'))]
   assert sha(binary)==binary_hash
   ss.with_suffix('.manifest.json').write_text(json.dumps(dict(job=job,stage=index,command=cmd,flags={k:v for k,v in env.items() if k.startswith('OCA_')},binary_sha256=binary_hash,data_sha256=datahash),indent=2)+'\n')
   with ss.with_suffix('.log').open('x') as f,ss.with_suffix('.stderr').open('x') as e:q=subprocess.run(cmd,env=env,stdout=f,stderr=e)
   assert q.returncode==0,(job['name'],index,q.returncode)
   log=ss.with_suffix('.log').read_text();m=re.search(r'RESULT .*?final_cost=([\d.e+-]+) solve_seconds=([\d.e+-]+)',log);assert m
   crossing=re.search(r'TARGET reached outer=(\d+) seconds=(\S+)',log)
   request=re.search(r'RESTART_REQUEST o=(\d+) streak=(\d+) cost=(\S+)',log)
   counts=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)',log)
   row=dict(stem=str(ss),seconds=float(m[2]),reported_cost=float(m[1]),crossing=float(crossing[2]) if crossing else None,
            cumulative_crossing=native_used+float(crossing[2]) if crossing else None,
            request_outer=int(request[1]) if request else None,accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]))
   if request:assert index==0 and mode=='3' and int(request[1])<=2 and int(request[2])==2
   stages.append(row);native_used+=row['seconds']
   if not request:break
  process_wall=time.monotonic()-wall_start
  # Audit only after solving, so the second stage does not wait for CPU scoring.
  for row in stages:
   ss=pathlib.Path(row['stem']);cost=audit(ss.with_suffix('.state'),dims,obs)
   row.update(cost=cost,audit_relerr=abs(cost-row['reported_cost'])/max(1,abs(cost)))
   assert row['audit_relerr']<1e-7
   with ss.with_suffix('.csv').open() as f:trace=list(csv.DictReader(l for l in f if not l.startswith('#')))
   costs=[float(x['cost']) for x in trace];assert abs(costs[0]-initial)/max(1,initial)<1e-7
   assert all(math.isfinite(x) for x in costs) and all(b<=a+1e-10*max(1,a) for a,b in zip(costs,costs[1:]))
   assert abs(cost-costs[-1])/max(1,cost)<1e-7
   records=[]
   for line in (ss.with_suffix('.jsonl').read_text().splitlines() if ss.with_suffix('.jsonl').exists() else []):
    line=re.sub(r'(?<=[,:\[])(-?nan|[+-]?inf)(?=[,}\]])','NaN',line);d=json.loads(line)
    if d.get('t')=='a':records.append(d)
   if row['request_outer'] is not None:
    streak=0;eligible=[]
    for i,d in enumerate(records):
     streak=0 if d['acc'] else streak+1
     if streak>=2 and d['o']<=2:eligible.append(i)
    assert eligible==[len(records)-1] and records[-1]['o']==row['request_outer'] and not records[-1]['acc']
   if job['arm']=='restart':
    assert 'DEMAND_SWITCH o=' not in ss.with_suffix('.log').read_text()
  best=min(stages,key=lambda x:x['cost']);shutil.copyfile(pathlib.Path(best['stem']).with_suffix('.state'),stem.with_suffix('.best.state'))
  crossings=[x['cumulative_crossing'] for x in stages if x['crossing'] is not None and x['cost']<=job['target']]
  cross=min(crossings) if crossings else None
  row=dict(job,stages=stages,restarted=len(stages)==2,cost=best['cost'],selected_stage=stages.index(best),
           native_seconds=native_used,process_wall=process_wall,crossing=cross,hit=cross is not None and cross<=job['cap'],
           rejects=sum(x['rejects'] for x in stages),matvecs=sum(x['matvecs'] for x in stages))
  result.write_text(json.dumps(row,indent=2)+'\n');print('DONE',job['name'],row['hit'],cross,row['cost'],flush=True)
 (r/'results.json').write_text(json.dumps([json.loads((out/j['name']).with_suffix('.result.json').read_text()) for j in plan['jobs']],indent=2)+'\n')
if __name__=='__main__':main()
