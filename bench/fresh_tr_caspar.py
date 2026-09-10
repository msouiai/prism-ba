#!/usr/bin/env python3
"""Fresh bounded paired TR vs Caspar FP64/FP32, original and larger BAL scenes."""
import pathlib,json,os,re,subprocess,time,shutil,csv,math
from profile_iterations import COMMON,sha
from novelty_ablation import EXEC
from cached_benchmark_input import load_input
from audit_prism_state import audit
ROOT=pathlib.Path('/workspace/prism-fresh-tr-caspar')
BINS={'tr':pathlib.Path('/workspace/prism-tr-candidate/prism-tr'),'caspar64':pathlib.Path('/workspace/prism-caspar-current/caspar64'),'caspar32':pathlib.Path('/workspace/prism-caspar-current/caspar32')}
SCENES=[('trafalgar-126',104534.24152926281,4),('dubrovnik-88',359003.9111293723,4),('final-1936',5074937.9725361075,12),('final-4585',7488277.5282109585,20),('final-13682',27318392.631312046,20)]
def write(p,v):
 tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(v,indent=2)+'\n');tmp.replace(p)
def main():
 ROOT.mkdir(exist_ok=True);flags=dict(COMMON,**EXEC,OCA_MENU_BACKTRACK='8',OCA_BACKTRACK_REARM='1',OCA_COMPACT_FRAGMENTS='2',OCA_POINT_SAFEGUARD='1',OCA_DEMAND_MENU='0',OCA_SWITCH_RESTART='0',OCA_CAMERA_TR='1',OCA_NSHIFTS='1',OCA_TR_RECURRENCE='1')
 jobs=[];arms=list(BINS)
 for rep in range(1,4):
  scene_order=SCENES[rep-1:]+SCENES[:rep-1]
  for i,(s,t,cap) in enumerate(scene_order):
   shift=(rep-1+next(k for k,x in enumerate(SCENES) if x[0]==s))%3;order=arms[shift:]+arms[:shift]
   for arm in order:jobs.append(dict(scene=s,nominal=t,target=t*(1-1e-8),cap=cap,arm=arm,rep=rep,name=f'{s}-{arm}-{rep}'))
 tooling=[pathlib.Path(__file__),pathlib.Path(__file__).with_name('profile_iterations.py'),pathlib.Path(__file__).with_name('novelty_ablation.py'),pathlib.Path(__file__).with_name('cached_benchmark_input.py'),pathlib.Path(__file__).with_name('audit_prism_state.py'),pathlib.Path('/workspace/prism-caspar-current/driver32.cc'),pathlib.Path('/workspace/prism-caspar-current/driver64.cc'),pathlib.Path('/workspace/prism-caspar-current/precision-proof.json'),pathlib.Path('/workspace/prism-tr-candidate/build-manifest.json')]
 protocol=dict(jobs=jobs,flags=flags,binary_sha256={a:sha(p) for a,p in BINS.items()},data_sha256={s:sha(pathlib.Path('/workspace/bal')/(s+'.txt')) for s,_,_ in SCENES},tooling_sha256={str(p):sha(p) for p in tooling},repeats=3,precision='TR FP64, pinned COLMAP Caspar generated f64 and f32 driver variants, defaults:pcg20 diag_init1 pcg_tol1e-4. FP32 rounds parameters/observations as its implementation requires; original double observations used for independent certification.',quality='Frozen historical medium targets, same effective target nominal*(1-1e-8). Native crossing only certified if original-observation CPU endpoint also meets it. No retuning or guard adjustment after FP32 results.',timing='Native target crossing (TR solver-local setup included, CLI upload excluded; Caspar graph setup excluded). Process wall separately, includes different internal CPU audit scopes; not normalized application wall. No profiling or model-audit logs.',failure='Keep all misses/crashes. No speed ratio for misses. A native target hit with audited cost above target is uncertified, not a successful FP32 solve.',max_native_budget_seconds=sum(j['cap'] for j in jobs),process_timeout_seconds=240)
 pp=ROOT/'protocol.json'
 if pp.exists():assert json.loads(pp.read_text())==protocol
 else:
  write(pp,protocol);(ROOT/'tooling').mkdir(exist_ok=True)
  for p in tooling:shutil.copy2(p,ROOT/'tooling'/p.name)
 base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};cache={};rows=[]
 for j in jobs:
  stem=ROOT/j['name'];rp=stem.with_suffix('.result.json')
  if rp.exists():rows.append(json.loads(rp.read_text()));continue
  assert not stem.with_suffix('.log').exists(),'Inspect incomplete run; do not overwrite'
  data=pathlib.Path('/workspace/bal')/(j['scene']+'.txt')
  if j['scene'] not in cache:
   print('LOAD/AUDIT INPUT',j['scene'],flush=True);cache[j['scene']]=load_input(data,'/workspace/prism-caspar-expanded/cpu-cache')
  dh,(dims,obs),initial=cache[j['scene']];assert dh==protocol['data_sha256'][j['scene']]
  binary=BINS[j['arm']];assert sha(binary)==protocol['binary_sha256'][j['arm']]
  env=dict(base)
  if j['arm']=='tr':
   env.update(flags);env.update(OCA_TARGET_COST=str(j['nominal']),OCA_MAX_SECONDS=str(j['cap']))
   cmd=[str(binary),'--problem',str(data),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','100000','--csv',str(stem.with_suffix('.csv')),'--state_out',str(stem.with_suffix('.state'))]
  else:
   env.update(CASPAR_TARGET_COST=str(j['target']),CASPAR_MAX_SECONDS=str(j['cap']),CASPAR_STATE_OUT=str(stem.with_suffix('.state')))
   cmd=[str(binary),str(data),'100000','default']
  cmd=['flock','/tmp/prism_gpu.lock','timeout','240']+cmd
  write(stem.with_suffix('.manifest.json'),dict(job=j,command=cmd,flags={k:v for k,v in env.items() if k.startswith(('OCA_','CASPAR_'))},binary_sha256=sha(binary),data_sha256=dh,dimensions=dims))
  print('RUN',j['name'],'cap',j['cap'],flush=True);start=time.monotonic()
  with stem.with_suffix('.log').open('x') as f,stem.with_suffix('.stderr').open('x') as e:q=subprocess.run(cmd,env=env,stdout=f,stderr=e)
  wall=time.monotonic()-start;write(stem.with_suffix('.process.json'),dict(returncode=q.returncode,wall=wall))
  row=dict(j,status='ok',hit=False,crossing=None,process_wall=wall,returncode=q.returncode,initial_reference=initial)
  if q.returncode:
   row.update(status='process_failure',stderr_tail=stem.with_suffix('.stderr').read_text()[-2500:])
  else:
   log=stem.with_suffix('.log').read_text()
   try:
    cost=audit(stem.with_suffix('.state'),dims,obs);assert math.isfinite(cost)
    row['cost']=cost
    if j['arm']=='tr':
     m=re.search(r'RESULT .*?final_cost=(\S+) solve_seconds=(\S+)',log);assert m
     c=re.search(r'TARGET reached outer=(\d+) seconds=(\S+)',log)
     row.update(native_cost=float(m[1]),seconds=float(m[2]),crossing=float(c[2]) if c else None,precision='f64',setup_seconds=None)
     counts=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+).*?cand_evals=(\d+)',log);assert counts
     row.update(accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]),candidate_evals=int(counts[4]))
     with stem.with_suffix('.csv').open() as f:trace=list(csv.DictReader(l for l in f if not l.startswith('#')))
     assert abs(float(trace[0]['cost'])-initial)<1e-7*initial
     assert all(float(b['cost'])<=float(a['cost'])*(1+1e-10) for a,b in zip(trace,trace[1:]))
     reported=float(m[1]);row['initial_cpu_gap']=abs(float(trace[0]['cost'])-initial)/initial
    else:
     m=re.search(r'RESULT exit=(\d+) iters=(\d+) final_score=(\S+) runtime=(\S+)',log);check=re.search(r'CHECK final_score=(\S+)',log);ci=re.search(r'CHECK_INITIAL score=(\S+) precision=(\S+)',log);init=re.search(r'INITIAL score=(\S+) setup_seconds=(\S+)',log);assert m and check and ci and init
     assert ci[2]==('f64' if j['arm']=='caspar64' else 'f32')
     trace=[dict(iter=int(i),cost=float(c),seconds=float(t)) for i,c,t in re.findall(r'TRACE iter=(\d+) cost=(\S+) seconds=(\S+)',log)]
     candidates=[x for x in trace if x['cost']<=j['target']];cross=min((x['seconds'] for x in candidates),default=None)
     reported=float(check[1]);row.update(native_cost=float(m[3]),seconds=float(m[4]),crossing=cross,precision=ci[2],setup_seconds=float(init[2]),exit=int(m[1]),iters=int(m[2]),trace=trace,initial_native=float(init[1]),initial_cpu=float(ci[1]),initial_cpu_gap=abs(float(ci[1])-initial)/initial,initial_native_gap=abs(float(init[1])-initial)/initial)
     if j['arm']=='caspar64':assert row['initial_cpu_gap']<1e-6 and row['initial_native_gap']<1e-6
    row['audit_error']=abs(cost-reported)/max(1,abs(cost));assert row['audit_error']<1e-7
    row['native_cpu_gap']=abs(cost-row['native_cost'])/max(1,abs(cost));row['native_hit']=row['crossing'] is not None and row['crossing']<=j['cap']
    row['hit']=row['native_hit'] and cost<=j['target']
    row['uncertified_native_hit']=row['native_hit'] and not row['hit']
    row['endpoint_over_target_fraction']=cost/j['target']-1
   except Exception as error:
    row.update(status='audit_or_parse_failure',hit=False,error=repr(error))
  write(rp,row);rows.append(row);write(ROOT/'results.json',rows)
  print('DONE',j['name'],row['status'],'hit',row['hit'],'cross',row.get('crossing'),'cost',row.get('cost'),'native_gap',row.get('native_cpu_gap'),flush=True)
 write(ROOT/'results.json',rows);print('COMPLETE',len(rows),flush=True)
if __name__=='__main__':main()
