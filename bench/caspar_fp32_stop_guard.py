#!/usr/bin/env python3
"""Separate stopping-margin follow-up after one uncertified native FP32 hit."""
import pathlib,json,os,re,subprocess,time,shutil
from fresh_tr_caspar import ROOT,BINS,write
from profile_iterations import sha
from cached_benchmark_input import load_input
from audit_prism_state import audit
OUT=ROOT/'fp32-stop-guard'
def main():
 OUT.mkdir(exist_ok=True);primary=json.loads((ROOT/'protocol.json').read_text());j=next(j for j in primary['jobs'] if j['scene']=='final-13682' and j['arm']=='caspar32')
 target=j['target'];native_goal=target*(1-1e-3);data=pathlib.Path('/workspace/bal/final-13682.txt');binary=BINS['caspar32']
 protocol=dict(scene=j['scene'],target=target,native_goal=native_goal,margin=1e-3,cap=20,repeats=3,binary_sha256=sha(binary),data_sha256=primary['data_sha256'][j['scene']],harness_sha256=sha(__file__),reason='One of three original FP32 native hits returned audited cost0.0314% above target. Test a single conservative0.1% native stopping margin, frozen before these runs. Same original certification target, same executable/settings except score exit threshold. Preserve original comparison; no reruns replace it. Margin is not a mathematical error bound or a globally validated setting.',timing='Supplementary FP32-only runs, not a new paired comparison. Native/process/audit scopes identical to primary study.')
 pp=OUT/'protocol.json';assert not pp.exists();write(pp,protocol);shutil.copy2(__file__,OUT/'harness.py')
 print('LOAD GUARD INPUT',flush=True);dh,(dims,obs),initial=load_input(data,'/workspace/prism-caspar-expanded/cpu-cache');assert dh==protocol['data_sha256']
 base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};rows=[]
 for rep in range(1,4):
  stem=OUT/f'final-13682-caspar32-guard-{rep}';env=dict(base,CASPAR_TARGET_COST=str(native_goal),CASPAR_MAX_SECONDS='20',CASPAR_STATE_OUT=str(stem.with_suffix('.state')))
  cmd=['flock','/tmp/prism_gpu.lock','timeout','240',str(binary),str(data),'100000','default']
  write(stem.with_suffix('.manifest.json'),dict(command=cmd,flags={k:v for k,v in env.items() if k.startswith('CASPAR_')},binary_sha256=sha(binary),data_sha256=dh,rep=rep,target=target,native_goal=native_goal))
  print('GUARD RUN',rep,flush=True);t=time.monotonic()
  with stem.with_suffix('.log').open('x') as f,stem.with_suffix('.stderr').open('x') as e:q=subprocess.run(cmd,env=env,stdout=f,stderr=e)
  wall=time.monotonic()-t;write(stem.with_suffix('.process.json'),dict(returncode=q.returncode,wall=wall));assert q.returncode==0
  log=stem.with_suffix('.log').read_text();m=re.search(r'RESULT exit=(\d+) iters=(\d+) final_score=(\S+) runtime=(\S+)',log);check=re.search(r'CHECK final_score=(\S+)',log);ci=re.search(r'CHECK_INITIAL score=(\S+) precision=(\S+)',log);assert m and check and ci and ci[2]=='f32'
  cost=audit(stem.with_suffix('.state'),dims,obs);error=abs(cost-float(check[1]))/max(1,cost);assert error<1e-7
  trace=[dict(iter=int(i),cost=float(c),seconds=float(t)) for i,c,t in re.findall(r'TRACE iter=(\d+) cost=(\S+) seconds=(\S+)',log)]
  crossing=min((x['seconds'] for x in trace if x['cost']<=native_goal),default=None)
  row=dict(rep=rep,cost=cost,native_cost=float(m[3]),native_seconds=float(m[4]),process_wall=wall,crossing=crossing,hit=crossing is not None and crossing<=20 and cost<=target,audit_error=error,native_cpu_gap=abs(cost-float(m[3]))/cost,over_target_fraction=cost/target-1,state_sha256=sha(stem.with_suffix('.state')),trace=trace)
  rows.append(row);write(stem.with_suffix('.result.json'),row);write(OUT/'results.json',rows);print('GUARD DONE',rep,'hit',row['hit'],'seconds',crossing,'cost',cost,flush=True)
if __name__=='__main__':main()
