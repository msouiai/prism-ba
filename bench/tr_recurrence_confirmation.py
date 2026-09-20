#!/usr/bin/env python3
"""Bounded sequential studies; phase B is only run after phase A is assessed."""
import pathlib,os,json,re,subprocess,time,sys,shutil
from profile_iterations import COMMON,sha
from novelty_ablation import EXEC
from cached_benchmark_input import load_input
from audit_prism_state import audit
ROOT=pathlib.Path('/workspace/prism-tr-recurrence')
SCENES=[('trafalgar-126',104534.24152926281),('dubrovnik-88',359003.9111293723),('final-1936',5074937.9725361075)]
def main():
 phase=sys.argv[1];assert phase=='confirmation'
 mode=1;out=ROOT/phase;out.mkdir(exist_ok=True)
 flags=dict(COMMON,**EXEC,OCA_MENU_BACKTRACK='8',OCA_BACKTRACK_REARM='1',OCA_COMPACT_FRAGMENTS='2',OCA_POINT_SAFEGUARD='1',OCA_DEMAND_MENU='0',OCA_SWITCH_RESTART='0',OCA_CAMERA_TR='1',OCA_NSHIFTS='1')
 jobs=[]
 jobs.append(dict(scene='final-1936',target=1e-100,mode=mode,rep=-1,iterations=16,trace=True,width=1))
 for rep in range(1,6):
  for s,t in SCENES if rep%2 else SCENES[::-1]:
   for arm in ([0,mode] if rep%2 else [mode,0]):jobs.append(dict(scene=s,target=t,mode=arm,rep=rep,iterations=100000,trace=False))
 protocol=dict(phase=phase,jobs=jobs,flags=flags,binary_sha256=sha(ROOT/'prism'),source_sha256=sha(ROOT/'source.cu'),data_sha256={s:sha(pathlib.Path('/workspace/bal')/(s+'.txt')) for s,_ in SCENES},cap={'small':4,'final-1936':8},policy='Replace explicit Schur curvature matvec at each CG snapshot with bdot-sigma*norm2-zeta*x_dot_recursive_residual. Full nonlinear cost and full GN acceptance unchanged. Confirmation after initial N3 improved both medians but only2/3pairs. One16-iteration recurrence audit on previously unused large Final1936 then N5 fresh paired repeats on all three scenes. Same source/binary/controller, frozen original medium targets. Caps4s small8s large. No settings tuned. Validation rather than scene-specific selection.',headers={str(p):sha(p) for p in (ROOT/'tooling').iterdir()})
 pp=out/'protocol.json';assert not pp.exists();pp.write_text(json.dumps(protocol,indent=2));shutil.copy2(__file__,out/'harness.py')
 base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};cache={};rows=[]
 for j in jobs:
  stem=out/(j['scene']+'-mode'+str(j['mode'])+'-rep'+str(j['rep']))
  data=pathlib.Path('/workspace/bal')/(j['scene']+'.txt')
  if j['scene'] not in cache:cache[j['scene']]=load_input(data,'/workspace/prism-caspar-expanded/cpu-cache')
  dh,(dims,obs),initial=cache[j['scene']];assert dh==protocol['data_sha256'][j['scene']]
  env=dict(base,**flags,OCA_TR_RECURRENCE=str(j['mode']),OCA_TARGET_COST=str(j['target']),OCA_MAX_SECONDS='8' if j['scene']=='final-1936' else '4')
  if j['trace']:env['OCA_TR_RECURRENCE_AUDIT']='1';env['OCA_NSHIFTS']=str(j['width'])
  cmd=['flock','/tmp/prism_gpu.lock','timeout','40',str(ROOT/'prism'),'--problem',str(data),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter',str(j['iterations']),'--csv',str(stem.with_suffix('.csv')),'--state_out',str(stem.with_suffix('.state'))]
  stem.with_suffix('.manifest.json').write_text(json.dumps(dict(job=j,command=cmd,flags={k:v for k,v in env.items() if k.startswith('OCA_')}),indent=2))
  print('RUN',phase,stem.name,flush=True);start=time.monotonic()
  with stem.with_suffix('.log').open('x') as f,stem.with_suffix('.stderr').open('x') as e:q=subprocess.run(cmd,env=env,stdout=f,stderr=e)
  wall=time.monotonic()-start;assert q.returncode==0
  log=stem.with_suffix('.log').read_text();m=re.search(r'RESULT .*?final_cost=(\S+) solve_seconds=(\S+)',log);assert m
  cost=audit(stem.with_suffix('.state'),dims,obs);err=abs(cost-float(m[1]))/max(1,cost);assert err<1e-7
  c=re.search(r'TARGET reached outer=(\d+) seconds=(\S+)',log)
  counts=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+).*?cand_evals=(\d+)',log);assert counts
  for line in log.splitlines():
   if line.startswith('CAMERA_TR o='):
    d={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)}
    if d['accept']:assert d['rho']>=.1 and d['norm']<=d['radius']*(1+1e-8)
  row=dict(j,cost=cost,audit_error=err,native=float(m[2]),wall=wall,crossing=float(c[2]) if c else None,hit=bool(c) and float(c[2])<=(8 if j['scene']=='final-1936' else 4) and cost<=j['target']*(1-1e-8),accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]),scores=int(counts[4]))
  stem.with_suffix('.result.json').write_text(json.dumps(row,indent=2));rows.append(row);(out/'results.json').write_text(json.dumps(rows,indent=2))
  print('DONE hit',row['hit'],'seconds',row['crossing'],'rejects',row['rejects'],'mv',row['matvecs'],flush=True)
if __name__=='__main__':main()
