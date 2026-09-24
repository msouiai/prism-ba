#!/usr/bin/env python3
"""Frozen lightweight camera-TR screen, with audited real-state radius checks."""
import csv,json,os,pathlib,re,shutil,subprocess,time
from profile_iterations import COMMON,sha
from novelty_ablation import EXEC
from cached_benchmark_input import load_input
from audit_prism_state import audit
from expanded_caspar_screen import write
ROOT=pathlib.Path('/workspace/prism-camera-tr')
SCENES=[('trafalgar-126',104534.24152926281),('dubrovnik-88',359003.9111293723)]
def main():
 flags=dict(COMMON,**EXEC,OCA_MENU_BACKTRACK='8',OCA_BACKTRACK_REARM='1',OCA_COMPACT_FRAGMENTS='2',OCA_POINT_SAFEGUARD='1',OCA_DEMAND_MENU='0',OCA_SWITCH_RESTART='0')
 binaries=dict(single='/workspace/prism-early-restart/prism-v7',five='/workspace/prism-early-restart/prism-v7',tr=str(ROOT/'prism-tr'))
 jobs=[dict(name=s+'-sanity',scene=s,target=1e-100,arm='tr',cap=4,iterations=6,rep=0,sanity=True) for s,_ in SCENES]
 for rep in range(3):
  for i,(scene,target) in enumerate(SCENES if rep%2==0 else SCENES[::-1]):
   arms=['single','five','tr'];offset=(rep+i)%3
   for arm in arms[offset:]+arms[:offset]:jobs.append(dict(name=f'{scene}-{arm}-{rep+1}',scene=scene,target=target,arm=arm,cap=4,iterations=100000,rep=rep+1,sanity=False))
 source=pathlib.Path(__file__).resolve().parent
 files=[source/'camera_tr_study.py',source/'build_camera_tr.py',source/'audit_prism_state.py',source/'cached_benchmark_input.py',source/'profile_iterations.py',source/'novelty_ablation.py']
 files+=list((source.parent/'gpu').glob('*.h'))+list((source.parent/'gpu').glob('*.cuh'))
 protocol=dict(flags=flags,jobs=jobs,binaries=binaries,binary_sha256={a:sha(b) for a,b in binaries.items()},source_sha256=sha(ROOT/'source-tr.cu'),data_sha256={s:sha(pathlib.Path('/workspace/bal')/(s+'.txt')) for s,_ in SCENES},
  tooling_sha256={str(p):sha(p) for p in files},timing='No profiler or learn log. Native target crossing includes solver-local initialization; all candidate-model matvecs and retry work count.',
  method='Finite radially clipped shifted/depth candidates plus Cauchy, ranked by fixed-tau reduced-model prediction; actual full GN prediction for radius acceptance. Point safeguards retained, alpha grid disabled for TR. No exact KKT or joint-TR claim.',
  budget='Two six-iteration sanity runs then 18 target runs; all cap4s. No post-outcome parameter tuning.')
 pp=ROOT/'protocol.json'
 if pp.exists():assert json.loads(pp.read_text())==protocol
 else:
  write(pp,protocol);(ROOT/'tooling').mkdir(exist_ok=True)
  for p in files:shutil.copy2(p,ROOT/'tooling'/p.name)
 base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};cache={};rows=[]
 for j in jobs:
  stem=ROOT/j['name'];rp=stem.with_suffix('.result.json')
  if rp.exists():rows.append(json.loads(rp.read_text()));continue
  assert not stem.with_suffix('.log').exists(),'Retain and inspect incomplete run'
  data=pathlib.Path('/workspace/bal')/(j['scene']+'.txt')
  if j['scene'] not in cache:cache[j['scene']]=load_input(data,'/workspace/prism-caspar-expanded/cpu-cache')
  dh,(dims,obs),initial=cache[j['scene']];assert dh==protocol['data_sha256'][j['scene']]
  binary=binaries[j['arm']];assert sha(binary)==protocol['binary_sha256'][j['arm']]
  env=dict(base,**flags,OCA_NSHIFTS='1' if j['arm']=='single' else '5',OCA_TARGET_COST=str(j['target']),OCA_MAX_SECONDS=str(j['cap']))
  if j['arm']=='tr':env['OCA_CAMERA_TR']='1'
  cmd=['flock','/tmp/prism_gpu.lock','timeout','45',binary,'--problem',str(data),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter',str(j['iterations']),'--csv',str(stem.with_suffix('.csv')),'--state_out',str(stem.with_suffix('.state'))]
  write(stem.with_suffix('.manifest.json'),dict(job=j,command=cmd,flags={k:v for k,v in env.items() if k.startswith('OCA_')},binary_sha256=sha(binary),data_sha256=dh))
  print('RUN',j['name'],flush=True);start=time.monotonic()
  with stem.with_suffix('.log').open('x') as f,stem.with_suffix('.stderr').open('x') as e:q=subprocess.run(cmd,env=env,stdout=f,stderr=e)
  wall=time.monotonic()-start;write(stem.with_suffix('.process.json'),dict(returncode=q.returncode,wall=wall));assert q.returncode==0
  log=stem.with_suffix('.log').read_text();m=re.search(r'RESULT .*?final_cost=(\S+) solve_seconds=(\S+)',log);assert m
  cost=audit(stem.with_suffix('.state'),dims,obs);error=abs(cost-float(m[1]))/max(1,cost);assert error<1e-7
  with stem.with_suffix('.csv').open() as f:trace=list(csv.DictReader(l for l in f if not l.startswith('#')))
  assert abs(float(trace[0]['cost'])-initial)/initial<1e-7
  assert all(float(b['cost'])<=float(a['cost'])*(1+1e-10) for a,b in zip(trace,trace[1:]))
  assert abs(float(trace[-1]['cost'])-cost)/max(1,cost)<1e-7
  counts=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+).*?cand_evals=(\d+)',log);assert counts
  scoring=re.search(r'\[scoring\] menu_evals=(\d+) alpha_evals=(\d+) backtrack_evals=(\d+) total_scored=(\d+)',log);assert scoring
  crossing=re.search(r'TARGET reached outer=(\d+) seconds=(\S+)',log);cross=float(crossing[2]) if crossing else None
  tr=[]
  for line in log.splitlines():
   if not line.startswith('CAMERA_TR o='):continue
   d={k:float(v) for k,v in re.findall(r'(\w+)=([\d.e+-]+)',line)};tr.append(d)
   if d['accept']:assert d['norm']<=d['radius']*(1+1e-8) and d['prediction']>0 and d['rho']>=.1
   if d['reuse']:assert len(tr)>1 and tr[-2]['o']==d['o'] and tr[-2]['tau']==d['tau'] and not tr[-2]['accept']
  extra=re.search(r'CAMERA_TR summary reuses=(\d+) model_matvecs=(\d+) full_predictions=(\d+)',log)
  if j['arm']=='tr':assert tr and extra
  row=dict(j,cost=cost,initial=initial,audit_error=error,seconds=float(m[2]),process_wall=wall,crossing=cross,hit=cross is not None and cross<=j['cap'] and cost<=j['target']*(1-1e-8),
   accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]),menu_evals=int(counts[4]),total_scored=int(scoring[4]),tr_trace=tr,
   reuses=int(extra[1]) if extra else 0,model_matvecs=int(extra[2]) if extra else 0,full_predictions=int(extra[3]) if extra else 0)
  write(rp,row);rows.append(row);write(ROOT/'results.json',rows)
  print('DONE',j['name'],'hit',row['hit'],'cost',cost,'cross',cross,'rejects',row['rejects'],'reuse',row['reuses'],flush=True)
 write(ROOT/'results.json',rows);print('COMPLETE',len(rows),flush=True)
if __name__=='__main__':main()
