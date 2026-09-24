#!/usr/bin/env python3
"""Bounded paired compact-storage TR precision experiment, audited raw BAL cost."""
import pathlib,json,os,subprocess,time,re,math,argparse,statistics
from profile_iterations import COMMON,sha
from novelty_ablation import EXEC
from cached_benchmark_input import load_input
from audit_prism_state import audit
ROOT=pathlib.Path('/workspace/prism-tr-mixed')
SCENES={'trafalgar-126':(104534.24152926281,4),'dubrovnik-88':(359003.9111293723,4),'final-1936':(5074937.9725361075,12),'final-13682':(27318392.631312046,20)}
BINS={'double':pathlib.Path('/workspace/prism-tr-candidate/prism-tr'),'storage':ROOT/'storage/prism-tr'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['audit','timing'],required=True);ap.add_argument('--scenes',nargs='+',default=list(SCENES));ap.add_argument('--reps',type=int,default=3);ap.add_argument('--output',type=pathlib.Path);ap.add_argument('--candidate',type=pathlib.Path);ap.add_argument('--audit-full',action='store_true');a=ap.parse_args()
 if a.candidate:BINS['storage']=a.candidate
 out=a.output or ROOT/a.phase;out.mkdir(parents=True,exist_ok=True)
 flags=dict(COMMON,**EXEC,OCA_MENU_BACKTRACK='8',OCA_BACKTRACK_REARM='1',OCA_COMPACT_FRAGMENTS='2',OCA_POINT_SAFEGUARD='1',OCA_DEMAND_MENU='0',OCA_SWITCH_RESTART='0',OCA_CAMERA_TR='1',OCA_NSHIFTS='1',OCA_TR_RECURRENCE='1')
 if a.phase=='audit':flags['OCA_TR_RECURRENCE_AUDIT']='1'
 jobs=[]
 for rep in range(1,a.reps+1):
  for scene in a.scenes:
   for arm in (list(BINS) if rep%2 else list(BINS)[::-1]):jobs.append(dict(scene=scene,arm=arm,rep=rep))
 protocol=dict(jobs=jobs,flags=flags,bins={k:sha(v) for k,v in BINS.items()},scenes={s:dict(nominal=SCENES[s][0],cap=SCENES[s][1],input_sha256=sha('/workspace/bal/'+s+'.txt')) for s in a.scenes},scope='Isolated FP32 fragment storage; all arithmetic, state, raw objective, model acceptance FP64. Audit runs use 7 iterations and extra curvature matvecs; timing runs have no instrumentation. Native crossing certified only by independent original-double endpoint. Capped misses retained; solver-boundary overshoot charged.')
 if a.candidate:protocol['candidate_manifest']=json.loads((a.candidate.parent/'mixed-manifest.json').read_text())
 if a.audit_full:protocol['audit_full']=True
 pp=out/'protocol.json'
 if pp.exists():assert json.loads(pp.read_text())==protocol
 else:pp.write_text(json.dumps(protocol,indent=2))
 base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};cache={};rows=[]
 for j in jobs:
  scene,arm=j['scene'],j['arm'];stem=out/f'{scene}-{arm}-{j["rep"]}';rp=stem.with_suffix('.result.json')
  if rp.exists():rows.append(json.loads(rp.read_text()));continue
  if scene not in cache:cache[scene]=load_input(pathlib.Path('/workspace/bal')/(scene+'.txt'),'/workspace/prism-caspar-expanded/cpu-cache')
  dh,(dims,obs),initial=cache[scene];assert dh==protocol['scenes'][scene]['input_sha256'];assert sha(BINS[arm])==protocol['bins'][arm]
  nominal,cap=SCENES[scene];env=dict(base,**flags,OCA_TARGET_COST=str(nominal),OCA_MAX_SECONDS=str(cap));cmd=['flock','/tmp/prism_gpu.lock','timeout','240',str(BINS[arm]),'--problem','/workspace/bal/'+scene+'.txt','--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','7' if a.phase=='audit' and not a.audit_full else '100000','--csv',str(stem)+'.csv','--state_out',str(stem)+'.state']
  stem.with_suffix('.manifest.json').write_text(json.dumps(dict(command=cmd,flags={k:v for k,v in env.items() if k.startswith('OCA_')},binary_sha256=sha(BINS[arm]),input_sha256=dh),indent=2))
  print('RUN',stem.name,flush=True);start=time.monotonic()
  with stem.with_suffix('.log').open('x') as f,stem.with_suffix('.stderr').open('x') as e:r=subprocess.run(cmd,env=env,stdout=f,stderr=e)
  row=dict(j,returncode=r.returncode,process_wall=time.monotonic()-start,hit=False)
  if r.returncode==0:
   log=stem.with_suffix('.log').read_text();m=re.search(r'RESULT .*?final_cost=(\S+) solve_seconds=(\S+)',log);assert m
   cost=audit(stem.with_suffix('.state'),dims,obs);err=abs(cost-float(m[1]))/max(1,cost);assert math.isfinite(cost) and err<1e-7
   c=re.search(r'TARGET reached outer=(\d+) seconds=(\S+)',log);cross=float(c[2]) if c else None
   counts=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+) negcurv=(\d+)',log);assert counts
   checks=0
   for line in log.splitlines():
    if line.startswith('CAMERA_TR o='):
     v={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)}
     if v['accept']:assert v['rho']>=.1 and v['prediction']>0 and v['norm']<=v['radius']*(1+1e-8);checks+=1
   drift=[float(v) for v in re.findall(r'^TR_RECURRENCE .*?error=(\S+)',log,re.M)];assert all(v<=1e-7 for v in drift)
   row.update(cost=cost,audit_error=err,seconds=float(m[2]),crossing=cross,hit=cross is not None and cross<=cap and cost<=nominal*(1-1e-8),accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]),negcurv=int(counts[4]),accepted_checks=checks,curvature_checks=len(drift),max_curvature_error=max(drift,default=0),state_sha256=sha(stem.with_suffix('.state')))
  rp.write_text(json.dumps(row,indent=2));rows.append(row);(out/'results.json').write_text(json.dumps(rows,indent=2));print('DONE',json.dumps(row),flush=True)
 summary=[]
 for scene in a.scenes:
  d={'scene':scene}
  for arm in BINS:
   rr=[r for r in rows if r['scene']==scene and r['arm']==arm];hits=[r['crossing'] for r in rr if r['hit']]
   d[arm]=dict(hits=len(hits),runs=len(rr),median_crossing=statistics.median(hits) if len(hits)==len(rr) else None,median_endpoint=statistics.median(r['cost'] for r in rr if 'cost' in r))
  summary.append(d)
 (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
