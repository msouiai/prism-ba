#!/usr/bin/env python3
import pathlib,json,os,subprocess,re,time,argparse,statistics,math
from build_tr_candidate import sha
from cached_benchmark_input import load_input
from audit_prism_state import audit
R=pathlib.Path('/tmp/prism-controller-attribution');BIN=R/'build/prism-tr';FROZEN=pathlib.Path('/workspace/prism-tr-preconditioner/pcg-v2/prism-tr')
SCENES={'trafalgar-126':(104534.24152926281,4),'dubrovnik-88':(359003.9111293723,4),'final-1936':(5074937.9725361075,12),'final-13682':(27318392.631312046,20),'final-4585':(7488277.5282109585,20)}
def flags(arm):
 d=json.loads(pathlib.Path('/workspace/prism-tr-preconditioner/recommended_candidate.json').read_text())['flags'];d.pop('OCA_TARGET_COST');d.pop('OCA_MAX_SECONDS')
 if arm=='tr_no_safe':d['OCA_POINT_SAFEGUARD']='0'
 if arm=='tr_no_projection':d['OCA_CG_STOP']='0'
 if arm.startswith('lm'):
  for k in ['OCA_TAU_LAM','OCA_TAU_LAM_RATCHET','OCA_ALPHA_RHO','OCA_BACKTRACK_REARM']:d.pop(k,None)
  d.update(OCA_CLASSICAL_LM='1',OCA_CAMERA_TR='0',OCA_TR_RECURRENCE='0',OCA_CG_STOP='0',OCA_POINT_SAFEGUARD='0',OCA_MENU_BACKTRACK='0')
 if '_safe' in arm and arm.startswith('lm'):d['OCA_LM_POINT_RESCUE']='1'
 if '_refine' in arm and arm.startswith('lm'):d['OCA_LM_POINT_RESCUE']='2'
 if '_matched' in arm:
  d.update(OCA_ATTR_RESCUE='1',OCA_MENU_BACKTRACK='8',OCA_BACKTRACK_REARM='1',OCA_POINT_SAFEGUARD='1')
 if '_split' in arm:d.update(OCA_ATTR_SPLIT='1',OCA_TAU_LAM='1',OCA_TAU_LAM_RATCHET='1')
 if '_trscale' in arm:d['OCA_TAU_LAM']='100'
 if '_strict' in arm:d['OCA_ATTR_STRICT']='1'
 if '_radius' in arm:d['OCA_ATTR_RADIUS']='1'
 return d

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--binary',type=pathlib.Path,default=BIN);ap.add_argument('--output',required=True,type=pathlib.Path);ap.add_argument('--scenes',nargs='+',default=['trafalgar-126','dubrovnik-88','final-1936']);ap.add_argument('--arms',nargs='+',default=['tr','lm','tr_no_safe','tr_no_projection']);ap.add_argument('--reps',type=int,default=3);ap.add_argument('--iterations',type=int,default=100000);a=ap.parse_args();a.output.mkdir();jobs=[]
 for rep in range(a.reps):
  for si,scene in enumerate(a.scenes):
   arms=a.arms[(rep+si)%len(a.arms):]+a.arms[:(rep+si)%len(a.arms)]
   for arm in arms:jobs.append(dict(scene=scene,arm=arm,rep=rep+1))
 protocol=dict(jobs=jobs,flags={arm:flags(arm) for arm in a.arms},binary_sha256=sha(a.binary),frozen_sha256=sha(FROZEN),inputs={s:sha('/workspace/bal/'+s+'.txt') for s in a.scenes},iterations=a.iterations,scope='Attribution: matched=original backtracking+point safeguard; split=max(retry point floor, running-minimum lambda); strict=rho>.1; radius=clipped terminal camera direction in same Hcc coordinates plus radius-to-lambda controller. Split formula, radius feasibility and controller transitions independently checked. Same optimized kernels, FP64 arithmetic/state/model acceptance with FP32 fragment storage, Hcc block PCG. TR-no-safe removes only per-point safeguard. TR-no-projection removes projected z-basis and its FW stopping path but retains legacy TR candidate bank/controller/safeguard. Classical LM uses coupled lambda damping, Hcc diagonal camera scaling, Nielsen updates, terminal PCG step only, no line search or per-point safeguard. Numerical point damping floors retained; fused diagonal work retained even where unused. Initial lambda10 except lm_low=1e-4 sensitivity arm, EW maximum.5 and PCG checkpoint cap. Solver-native capped time to nominal*(1-1e-8), independently audited on original-double observations. Misses retained. No Caspar runs in this internal ablation. Optional lm_safe/lm_refine suffixes use isolated failed-step point rescue 1/2; all _low arms start lambda1e-4. _trstart uses initial camera lambda .1, _trscale uses point floor100 times running-minimum camera lambda; this matches TR initial normalized shift/point ratio, not its different Schur metric.')
 (a.output/'protocol.json').write_text(json.dumps(protocol,indent=2));rows=[];cache={}
 for j in jobs:
  scene,arm=j['scene'],j['arm'];nominal,cap=SCENES[scene];stem=a.output/f'{scene}-{arm}-{j["rep"]}';binary=FROZEN if arm=='frozen' else a.binary
  if scene not in cache:cache[scene]=load_input(pathlib.Path('/workspace/bal')/(scene+'.txt'),'/workspace/prism-caspar-expanded/cpu-cache')
  dh,(dims,obs),initial=cache[scene];assert dh==protocol['inputs'][scene];env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};env.update(flags(arm),OCA_TARGET_COST=str(nominal),OCA_MAX_SECONDS=str(cap));cmd=['flock','/tmp/prism_gpu.lock','timeout','240',str(binary),'--problem','/workspace/bal/'+scene+'.txt','--algo','mfree_shifted_cg','--dof9','--zero_k2','--mf-no-alpha','--max_iter',str(a.iterations),'--state_out',str(stem)+'.state'];
  if '_low' in arm:cmd+=['--lam0','1e-4']
  if '_trstart' in arm:cmd+=['--lam0','.1']
  stem.with_suffix('.manifest.json').write_text(json.dumps(dict(command=cmd,flags={k:v for k,v in env.items() if k.startswith('OCA_')},binary_sha256=sha(binary),input_sha256=dh),indent=2));print('RUN',stem.name,flush=True);start=time.monotonic()
  with stem.with_suffix('.log').open('x') as f,stem.with_suffix('.stderr').open('x') as e:p=subprocess.run(cmd,env=env,stdout=f,stderr=e)
  row=dict(j,returncode=p.returncode,process_wall=time.monotonic()-start,hit=False)
  if p.returncode==0:
   log=stem.with_suffix('.log').read_text();m=re.search(r'RESULT .*final_cost=(\S+) solve_seconds=(\S+)',log);assert m;cost=audit(stem.with_suffix('.state'),dims,obs);error=abs(cost-float(m[1]))/max(1,cost);assert math.isfinite(cost) and error<1e-7;c=re.search(r'TARGET reached outer=(\d+) seconds=(\S+)',log);cross=float(c[2]) if c else None;counts=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+) negcurv=(\d+)',log);assert counts;checks=0;lm=[]
   for line in log.splitlines():
    if line.startswith(('CAMERA_TR o=','CLASSICAL_LM o=')):
     v={k:float(x) for k,x in re.findall(r'(\w+)=([^ ]+)',line)}
     if v['accept']:
      assert v['prediction']>0 and v['rho']>(0 if arm.startswith('lm') else .1-1e-14)
      if not arm.startswith('lm'):assert v['norm']<=v['radius']*(1+1e-8)
      checks+=1
     if line.startswith('CLASSICAL_LM'):
      if '_split' not in arm:assert v['tau']==v['lambda']
      lm.append(v)
   for line in log.splitlines():
    if line.startswith('LM_RESCUE o='):
     v={k:float(x) for k,x in re.findall(r'(\w+)=([^ ]+)',line)}
     if v['won']:assert v['changed']>0 and v['slope']<0 and v['candidate']<v['current'] and v['candidate']<=v['current']+1e-4*v['slope']
   if arm.startswith('lm'):
    assert lm and 'CAMERA_TR o=' not in log and ('_matched' in arm or 'POINT_SAFE summary' not in log)
    nu=2
    for prev,nxt in ([] if '_radius' in arm else zip(lm,lm[1:])):
     expected=prev['lambda']*max(1/3,1-(2*prev['rho']-1)**3) if prev['accept'] else prev['lambda']*nu
     expected=max(1e-16,min(1e16,expected));assert abs(expected-nxt['lambda'])<=1e-10*max(1,expected),(prev,nxt,expected)
     nu=2 if prev['accept'] else min(1e8,nu*2)
   if '_split' in arm:
    floor=float('inf');streak=0
    for v in lm:
     floor=min(floor,(100 if '_trscale' in arm else 1)*v['lambda']);expected=max(1e-7*10**min(streak,12),floor)
     assert abs(v['tau']-expected)<=1e-10*max(1,expected),(v,expected)
     streak=0 if v['accept'] else streak+1
   if '_strict' in arm:
    assert all(not v['accept'] or v['rho']>.1 for v in lm)
   if '_radius' in arm:
    rad=[{k:float(x) for k,x in re.findall(r'(\w+)=([^ ]+)',line)} for line in log.splitlines() if line.startswith('ATTR_RADIUS o=')]
    assert len(rad)==len(lm)
    for i,v in enumerate(rad):
     if v['accept']:assert v['norm']<=v['radius']*(1+1e-8)
     nr=max(1e-14,.25*v['radius']) if not math.isfinite(v['rho']) or v['rho']<.25 else (min(1e16,2*v['radius']) if v['rho']>.75 and v['norm']>=.8*v['radius'] else v['radius'])
     if not v['accept'] and nr>=v['radius']:nr=max(1e-14,.25*v['radius'])
     assert abs(nr-v['next_radius'])<=1e-10*max(1,nr)
     expected=v['lambda']*(v['radius']/nr)**2
     if v['accept'] and v['norm']<.8*v['radius'] and v['rho']>=.25:expected=min(expected,.1*v['lambda'])
     expected=max(1e-16,min(1e16,expected));assert abs(expected-v['next_lambda'])<=1e-10*max(1,expected)
     if i+1<len(rad):assert abs(v['next_lambda']-rad[i+1]['lambda'])<=1e-10*max(1,v['next_lambda']) and rad[i+1]['radius']==v['next_radius']
   row.update(cost=cost,audit_error=error,seconds=float(m[2]),crossing=cross,hit=cross is not None and cross<=cap and cost<=nominal*(1-1e-8),accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]),negcurv=int(counts[4]),accepted_checks=checks,state_sha256=sha(stem.with_suffix('.state')))
  stem.with_suffix('.result.json').write_text(json.dumps(row,indent=2));rows.append(row);(a.output/'results.json').write_text(json.dumps(rows,indent=2));print('DONE',json.dumps(row),flush=True)
 summary=[]
 for scene in a.scenes:
  for arm in a.arms:
   rr=[r for r in rows if r['scene']==scene and r['arm']==arm];hits=[r['crossing'] for r in rr if r['hit']];summary.append(dict(scene=scene,arm=arm,hits=len(hits),runs=len(rr),median=statistics.median(hits) if len(hits)==len(rr) else None))
 (a.output/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
