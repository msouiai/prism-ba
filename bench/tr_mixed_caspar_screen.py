#!/usr/bin/env python3
"""Frozen mixed-storage TR vs both Caspar precisions on two additional scenes, N1."""
import pathlib,json,os,subprocess,time,re,math
from profile_iterations import COMMON,sha
from novelty_ablation import EXEC
from cached_benchmark_input import load_input
from audit_prism_state import audit
ROOT=pathlib.Path('/workspace/prism-tr-mixed/extra-scenes')
BINS={'tr':pathlib.Path('/workspace/prism-tr-mixed/storage/prism-tr'),'caspar64':pathlib.Path('/workspace/prism-caspar-current/caspar64'),'caspar32':pathlib.Path('/workspace/prism-caspar-current/caspar32')}
SCENES=[('ladybug-1197',366600.,6),('final-4585',7488277.5282109585,20)]
def main():
 ROOT.mkdir(exist_ok=True);flags=dict(COMMON,**EXEC,OCA_MENU_BACKTRACK='8',OCA_BACKTRACK_REARM='1',OCA_COMPACT_FRAGMENTS='2',OCA_POINT_SAFEGUARD='1',OCA_DEMAND_MENU='0',OCA_SWITCH_RESTART='0',OCA_CAMERA_TR='1',OCA_NSHIFTS='1',OCA_TR_RECURRENCE='1')
 protocol=dict(scenes=SCENES,flags=flags,bins={k:sha(v) for k,v in BINS.items()},inputs={s:sha('/workspace/bal/'+s+'.txt') for s,_,_ in SCENES},scope='N1 screening only, two additional scenes, previously fixed targets. TR float fragments and point Jacobian storage, double arithmetic/state/acceptance. Caspar native FP64 and FP32. Effective target nominal*(1-1e-8), no FP32 stop-margin retuning. Independent original-double endpoint required. No instrumentation; misses not speed ratios.')
 pp=ROOT/'protocol.json';assert not pp.exists(),'Use a new artifact directory to rerun';pp.write_text(json.dumps(protocol,indent=2));rows=[]
 for i,(scene,nominal,cap) in enumerate(SCENES):
  dh,(dims,obs),initial=load_input(pathlib.Path('/workspace/bal')/(scene+'.txt'),'/workspace/prism-caspar-expanded/cpu-cache');assert dh==protocol['inputs'][scene]
  arms=list(BINS);arms=arms[i:]+arms[:i]
  for arm in arms:
   stem=ROOT/(scene+'-'+arm);target=nominal*(1-1e-8);env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}
   if arm=='tr':
    env.update(flags,OCA_TARGET_COST=str(nominal),OCA_MAX_SECONDS=str(cap));cmd=[str(BINS[arm]),'--problem','/workspace/bal/'+scene+'.txt','--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','100000','--state_out',str(stem)+'.state']
   else:
    env.update(CASPAR_TARGET_COST=str(target),CASPAR_MAX_SECONDS=str(cap),CASPAR_STATE_OUT=str(stem)+'.state');cmd=[str(BINS[arm]),'/workspace/bal/'+scene+'.txt','100000','default']
   cmd=['flock','/tmp/prism_gpu.lock','timeout','240']+cmd;stem.with_suffix('.manifest.json').write_text(json.dumps(dict(command=cmd,flags={k:v for k,v in env.items() if k.startswith(('OCA_','CASPAR_'))},binary_sha256=sha(BINS[arm]),input_sha256=dh),indent=2));print('RUN',stem.name,flush=True);t=time.monotonic()
   with stem.with_suffix('.log').open('x') as f,stem.with_suffix('.stderr').open('x') as e:q=subprocess.run(cmd,env=env,stdout=f,stderr=e)
   row=dict(scene=scene,arm=arm,returncode=q.returncode,process_wall=time.monotonic()-t,target=target,cap=cap,hit=False)
   if q.returncode==0:
    log=stem.with_suffix('.log').read_text();cost=audit(stem.with_suffix('.state'),dims,obs);assert math.isfinite(cost)
    if arm=='tr':
     m=re.search(r'RESULT .*?final_cost=(\S+) solve_seconds=(\S+)',log);reported=float(m[1]);seconds=float(m[2]);c=re.search(r'TARGET reached outer=(\d+) seconds=(\S+)',log);cross=float(c[2]) if c else None
    else:
     reported=float(re.search(r'CHECK final_score=(\S+)',log)[1]);seconds=float(re.search(r'RESULT .*?runtime=(\S+)',log)[1]);trace=re.findall(r'TRACE iter=\d+ cost=(\S+) seconds=(\S+)',log);cross=min((float(t) for c,t in trace if float(c)<=target),default=None)
    error=abs(cost-reported)/max(1,cost);assert error<1e-7;row.update(cost=cost,seconds=seconds,crossing=cross,hit=cross is not None and cross<=cap and cost<=target,audit_error=error,state_sha256=sha(stem.with_suffix('.state')))
   stem.with_suffix('.result.json').write_text(json.dumps(row,indent=2));rows.append(row);(ROOT/'results.json').write_text(json.dumps(rows,indent=2));print('DONE',json.dumps(row),flush=True)
if __name__=='__main__':main()
