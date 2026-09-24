#!/usr/bin/env python3
"""Interleaved frozen PRISM policies and separately labelled Caspar precisions."""
import argparse,json,pathlib,os,re,subprocess,time,sys
from profile_iterations import sha,score_initial
from audit_prism_state import observations,audit
from cached_benchmark_input import load_input

def main():
 ap=argparse.ArgumentParser();ap.add_argument('plan',type=pathlib.Path);a=ap.parse_args()
 plan=json.loads(a.plan.read_text());r=pathlib.Path(plan['root']);out=r/'caspar-runs';out.mkdir(exist_ok=True)
 base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}
 cache={};rows=[]
 for j in plan['jobs']:
  print('RUN',j['name'],flush=True)
  if not j['arm'].startswith('caspar'):
   pp=r/'prism'/('plan-'+j['name']+'.json');pp.write_text(json.dumps(dict(root=str(r/'prism'),binary=plan['prism_binary'],jobs=[j]),indent=2)+'\n')
   with (r/'prism'/(j['name']+'.runner.log')).open('a') as f:
    q=subprocess.run([sys.executable,str(pathlib.Path(__file__).with_name('early_restart_screen.py')),str(pp)],stdout=f,stderr=subprocess.STDOUT)
   assert q.returncode==0,(j['name'],q.returncode)
   x=json.loads((r/'prism/screen'/(j['name']+'.result.json')).read_text())
   row=dict(j,cost=x['cost'],hit=x['hit'],crossing=x['crossing'],seconds=x['native_seconds'],process_wall=x['process_wall'],restarted=x['restarted'],audit_error=max(s['audit_relerr'] for s in x['stages']),stages=x['stages'])
  else:
   stem=out/j['name'];rp=stem.with_suffix('.result.json')
   if rp.exists():rows.append(json.loads(rp.read_text()));continue
   assert not stem.with_suffix('.log').exists(),'inspect incomplete run'
   data=pathlib.Path(j.get('data',str(pathlib.Path('/workspace/bal')/(j['scene']+'.txt')))).resolve()
   if data not in cache:cache[data]=load_input(data,j.get('cpu_cache'))
   dh,(dims,obs),initial=cache[data];binary=r/j['arm'];env=dict(base)
   env.update(CASPAR_MAX_SECONDS=str(j['cap']),CASPAR_TARGET_COST=str(j['target']),CASPAR_STATE_OUT=str(stem.with_suffix('.state')))
   cmd=['flock','/tmp/prism_gpu.lock','timeout',str(j.get('process_timeout',60)),str(binary),str(data),'100000','default']
   stem.with_suffix('.manifest.json').write_text(json.dumps(dict(job=j,command=cmd,flags={k:v for k,v in env.items() if k.startswith('CASPAR_')},binary_sha256=sha(binary),data_sha256=dh),indent=2)+'\n')
   start=time.monotonic()
   with stem.with_suffix('.log').open('x') as f,stem.with_suffix('.stderr').open('x') as e:q=subprocess.run(cmd,env=env,stdout=f,stderr=e)
   wall=time.monotonic()-start;assert q.returncode==0,(j['name'],q.returncode)
   log=stem.with_suffix('.log').read_text();cost=audit(stem.with_suffix('.state'),dims,obs)
   m=re.search(r'RESULT exit=(\d+) iters=(\d+) final_score=(\S+) runtime=(\S+)',log)
   check=re.search(r'CHECK final_score=(\S+)',log);ci=re.search(r'CHECK_INITIAL score=(\S+) precision=(\S+)',log)
   init=re.search(r'INITIAL score=(\S+) setup_seconds=(\S+)',log);assert m and check and ci and init
   assert ci[2]==('f64' if j['arm']=='caspar64' else 'f32')
   error=abs(cost-float(check[1]))/max(1,abs(cost));assert error<1e-7
   initial_native_gap=abs(float(init[1])-initial)/max(1,abs(initial))
   initial_cpu_gap=abs(float(ci[1])-initial)/max(1,abs(initial))
   if j['arm']=='caspar64':assert initial_native_gap<1e-6 and initial_cpu_gap<1e-6
   trace=[dict(iter=int(i),cost=float(c),seconds=float(t)) for i,c,t in re.findall(r'TRACE iter=(\d+) cost=(\S+) seconds=(\S+)',log)]
   times=[x['seconds'] for x in trace if x['cost']<=j['target']];cross=min(times) if times else None
   row=dict(j,cost=cost,native_cost=float(m[3]),seconds=float(m[4]),process_wall=wall,exit=int(m[1]),iters=int(m[2]),
            initial_reference=initial,initial_native=float(init[1]),initial_cpu=float(ci[1]),initial_native_gap=initial_native_gap,initial_cpu_gap=initial_cpu_gap,
            setup_seconds=float(init[2]),trace=trace,crossing=cross,hit=cross is not None and cross<=j['cap'] and cost<=j['target'],
            audit_error=error,native_cpu_gap=abs(cost-float(m[3]))/max(1,abs(cost)))
   rp.write_text(json.dumps(row,indent=2)+'\n')
  rows.append(row);(r/'partial-results.json').write_text(json.dumps(rows,indent=2)+'\n')
  print('DONE',j['name'],'hit',row['hit'],'cross',row['crossing'],'cost',row['cost'],flush=True)
 (r/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
if __name__=='__main__':main()
