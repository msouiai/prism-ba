#!/usr/bin/env python3
"""Matched depth ablation: original TR128, TR64, joint TR64."""
import pathlib,os,json,re,subprocess,time,shutil
from profile_iterations import COMMON,sha
from novelty_ablation import EXEC
from cached_benchmark_input import load_input
from audit_prism_state import audit
ROOT=pathlib.Path('/workspace/prism-joint-tr');OUT=ROOT/'width_depth'
SCENES=[('trafalgar-126',104534.24152926281),('dubrovnik-88',359003.9111293723)]
def main():
 OUT.mkdir(exist_ok=True)
 flags=dict(COMMON,**EXEC,OCA_MENU_BACKTRACK='8',OCA_BACKTRACK_REARM='1',OCA_COMPACT_FRAGMENTS='2',OCA_POINT_SAFEGUARD='1',OCA_DEMAND_MENU='0',OCA_SWITCH_RESTART='0',OCA_CAMERA_TR='1',OCA_NSHIFTS='1')
 arms=[('tr1d128',1,'8,16,32,64,128'),('tr5d64',5,'8,16,32,64'),('tr5d32',5,'8,16,32')]
 jobs=[dict(scene=s,target=t,arm=a,mode=m,ckpts=c,rep=r) for r in range(1,4) for s,t in (SCENES if r%2 else SCENES[::-1]) for a,m,c in (arms if r%2 else arms[::-1])]
 protocol=dict(jobs=jobs,flags=flags,binary_sha256=sha(ROOT/'prism'),source_sha256=sha(ROOT/'source.cu'),headers={str(p):sha(p) for p in (ROOT/'tooling').iterdir()},data_sha256={s:sha(pathlib.Path('/workspace/bal')/(s+'.txt')) for s,_ in SCENES},cap=4,reason='Joint64 helps Dubrovnik but not Trafalgar. Test multishift width versus depth tradeoff: TRfive at64 and32 against TRone128. Two fixed depths, no scene-specific settings. Cauchy control and inherited TR controller remain. N3 fixed targets no profiler or detail traces. Exploratory development comparison.')
 pp=OUT/'protocol.json';assert not pp.exists();pp.write_text(json.dumps(protocol,indent=2));shutil.copy2(__file__,OUT/'harness.py')
 base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};cache={};rows=[]
 for j in jobs:
  stem=OUT/(j['scene']+'-'+j['arm']+'-'+str(j['rep']));data=pathlib.Path('/workspace/bal')/(j['scene']+'.txt')
  if j['scene'] not in cache:cache[j['scene']]=load_input(data,'/workspace/prism-caspar-expanded/cpu-cache')
  dh,(dims,obs),initial=cache[j['scene']];assert dh==protocol['data_sha256'][j['scene']]
  env=dict(base,**flags,OCA_JOINT_TR='0',OCA_TARGET_COST=str(j['target']),OCA_MAX_SECONDS='4')
  env['OCA_NSHIFTS']=str(j['mode'])
  cmd=['flock','/tmp/prism_gpu.lock','timeout','40',str(ROOT/'prism'),'--problem',str(data),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','100000','--cg-checkpoints',j['ckpts'],'--csv',str(stem.with_suffix('.csv')),'--state_out',str(stem.with_suffix('.state'))]
  stem.with_suffix('.manifest.json').write_text(json.dumps(dict(job=j,command=cmd,flags={k:v for k,v in env.items() if k.startswith('OCA_')}),indent=2))
  print('RUN',stem.name,flush=True);start=time.monotonic()
  with stem.with_suffix('.log').open('x') as f,stem.with_suffix('.stderr').open('x') as e:q=subprocess.run(cmd,env=env,stdout=f,stderr=e)
  wall=time.monotonic()-start;assert q.returncode==0
  log=stem.with_suffix('.log').read_text();m=re.search(r'RESULT .*?final_cost=(\S+) solve_seconds=(\S+)',log);assert m
  cost=audit(stem.with_suffix('.state'),dims,obs);err=abs(cost-float(m[1]))/max(1,cost);assert err<1e-7
  c=re.search(r'TARGET reached outer=(\d+) seconds=(\S+)',log);counts=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+).*?cand_evals=(\d+)',log)
  row=dict(j,cost=cost,audit_error=err,native=float(m[2]),wall=wall,crossing=float(c[2]) if c else None,hit=bool(c) and float(c[2])<=4 and cost<=j['target']*(1-1e-8),accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]),scores=int(counts[4]))
  stem.with_suffix('.result.json').write_text(json.dumps(row,indent=2));rows.append(row);(OUT/'results.json').write_text(json.dumps(rows,indent=2));print('DONE',row['hit'],row['crossing'],'mv',row['matvecs'],flush=True)
if __name__=='__main__':main()
