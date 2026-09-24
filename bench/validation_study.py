#!/usr/bin/env python3
"""Compact CPU-audited policy selection and frozen wall-budget comparison."""
import argparse,csv,json,math,os,pathlib,re,statistics,subprocess,time
from profile_iterations import COMMON,sha,score_initial
from novelty_ablation import EXEC
from audit_prism_state import observations,audit

ARMS={
 'multi':{},
 'progressive':{'OCA_PROGRESSIVE_DEPTH':'1'},
 'rearm':{'OCA_BACKTRACK_REARM':'1'},
 'combined':{'OCA_PROGRESSIVE_DEPTH':'1','OCA_BACKTRACK_REARM':'1'},
}
SCENES={'ladybug-1197':[1,6],'dubrovnik-173':[1,6],'final-3068':[2,8],'final-4585':[4,15]}

def med(rows,key):return statistics.median(r[key] for r in rows)
def read_rows(root):return [json.loads(p.read_text()) for p in root.glob('*.result.json')]
def freeze(path,value):
 if path.exists():assert json.loads(path.read_text())==value,('Protocol changed',path)
 else:path.write_text(json.dumps(value,indent=2)+'\n')

def select(root):
 rows=read_rows(root/'ablation');assert len(rows)==24 and all(r['status']=='ok' for r in rows)
 scenes=['ladybug-1197','dubrovnik-173'];summary={};best={}
 for scene in scenes:
  summary[scene]={}
  for arm in ARMS:
   rr=[r for r in rows if r['scene']==scene and r['arm']==arm];assert len(rr)==3
   summary[scene][arm]={k:med(rr,k) for k in ['seconds','cost','rejects','matvecs','total_scored','rearms']}
  best[scene]=min(r['cost'] for r in summary[scene].values())
 eligible=[arm for arm in ARMS if all(summary[s][arm]['cost']<=1.03*best[s] for s in scenes)]
 speed={arm:math.exp(sum(math.log(summary[s][arm]['seconds']/summary[s]['multi']['seconds']) for s in scenes)/len(scenes)) for arm in eligible}
 fastest=min(speed.values());near=[arm for arm in eligible if speed[arm]<=1.03*fastest]
 selected=min(near,key=lambda arm:(len(ARMS[arm]),list(ARMS).index(arm)))
 result=dict(selected=selected,flags=ARMS[selected],eligible=eligible,normalized_geomean_runtime=speed,near_tie=near,medians=summary,rule='within 3% best median cost on both scenes, minimum geomean runtime; 3% runtime tie favors simpler')
 freeze(root/'selection.json',result);print(json.dumps(result,indent=2));return result

def main():
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['ablation','select','budgets']);p.add_argument('--root',type=pathlib.Path,default=pathlib.Path('/workspace/prism-validation'));p.add_argument('--binary',type=pathlib.Path);p.add_argument('--caspar',type=pathlib.Path);p.add_argument('--scenes',nargs='+');p.add_argument('--reps',type=int,default=3);p.add_argument('--budget-seconds',type=float);p.add_argument('--timeout',type=int,default=60);p.add_argument('--keep-going',action='store_true');a=p.parse_args();root=a.root;root.mkdir(parents=True,exist_ok=True)
 if a.reps<1 or a.timeout<1 or (a.budget_seconds is not None and (not math.isfinite(a.budget_seconds) or a.budget_seconds<=0)):p.error('reps, timeout and budget must be positive and finite')
 if a.phase!='budgets' and (a.reps!=3 or a.budget_seconds is not None):p.error('custom repeats/budgets are only supported in the budget phase')
 if a.phase=='select':select(root);return
 binary=str(a.binary.resolve());binary_hash=sha(binary)
 caspar=str(a.caspar.resolve()) if a.caspar else None;caspar_hash=sha(caspar) if caspar else None
 stage=root/a.phase;stage.mkdir(exist_ok=True)
 selected=json.loads((root/'selection.json').read_text()) if a.phase=='budgets' else None
 scenes=a.scenes or (list(SCENES) if selected else ['ladybug-1197','dubrovnik-173'])
 budgets={scene:([a.budget_seconds] if a.budget_seconds is not None else SCENES[scene]) for scene in scenes} if selected else SCENES
 plan=dict(phase=a.phase,binary=binary,binary_sha256=binary_hash,caspar=caspar,caspar_sha256=caspar_hash,selected=selected['selected'] if selected else None,scenes=scenes,reps=a.reps,common=COMMON,execution=EXEC,arms=ARMS,budgets=budgets,outer_cap=100000 if selected else 60,timeout=a.timeout)
 manifest=stage/('plan-'+('-'.join(scenes))+'.json');freeze(manifest,plan)
 base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};base.update(COMMON);base.update(EXEC);base.update(OCA_NSHIFTS='5',OCA_MENU_BACKTRACK='8')
 for scene in scenes:
  data=pathlib.Path('/workspace/bal')/(scene+'.txt');data_hash=sha(data);initial=score_initial(data);dims,obs=observations(data)
  for rep in range(1,a.reps+1):
   cells=[(arm,None) for arm in ARMS] if not selected else [(arm,budget) for budget in budgets[scene] for arm in ['selected','single','caspar32']]
   shift=(rep-1)%len(cells);cells=cells[shift:]+cells[:shift]
   if rep==2:cells=cells[::-1]
   for arm,budget in cells:
    label=arm+(f'-{budget:g}s' if budget else '');stem=stage/f'{scene}-{label}-{rep}';jp=stem.with_suffix('.result.json')
    if jp.exists():continue
    env=dict(base);state=stem.with_suffix('.state');is_caspar=arm=='caspar32'
    if is_caspar:
     env={k:v for k,v in env.items() if not k.startswith('OCA_')};env['CASPAR_MAX_SECONDS']=str(budget)
     assert sha(caspar)==caspar_hash
     cmd=['flock','/tmp/prism_gpu.lock','timeout',str(a.timeout),caspar,str(data),'100000','default']
    else:
     assert sha(binary)==binary_hash
     if selected:
      if arm=='selected':env.update(selected['flags'])
      else:env['OCA_NSHIFTS']='1'
     else:env.update(ARMS[arm])
     if budget:env['OCA_MAX_SECONDS']=str(budget)
     cmd=['flock','/tmp/prism_gpu.lock','timeout',str(a.timeout),binary,'--problem',str(data),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','100000' if budget else '60','--csv',str(stem.with_suffix('.csv')),'--state_out',str(state)]
    m=dict(command=cmd,flags={k:v for k,v in env.items() if k.startswith(('OCA_','CASPAR_'))},data_sha256=data_hash,binary_sha256=caspar_hash if is_caspar else binary_hash)
    freeze(stem.with_suffix('.manifest.json'),m)
    if stem.with_suffix('.log').exists():raise RuntimeError('Incomplete retained run; inspect before retrying: '+str(stem))
    print('RUN',scene,label,rep,flush=True);start=time.monotonic()
    with stem.with_suffix('.log').open('w') as f,stem.with_suffix('.stderr').open('w') as e:proc=subprocess.run(cmd,env=env,stdout=f,stderr=e)
    row=dict(scene=scene,arm=arm,budget=budget,rep=rep,status='failed',returncode=proc.returncode,process_seconds=time.monotonic()-start,data_sha256=data_hash)
    if proc.returncode==0:
     log=stem.with_suffix('.log').read_text()
     if is_caspar:
      res=re.search(r'RESULT exit=(\d+) iters=(\d+) final_score=(\S+) runtime=(\S+)',log);check=re.search(r'CHECK final_score=(\S+)',log);ini=re.search(r'CHECK_INITIAL score=(\S+)',log);setup=re.search(r'setup_seconds=(\S+)',log);assert res and check and ini
      row.update(status='ok',iters=int(res[2]),native_cost=float(res[3]),seconds=float(res[4]),cost=float(check[1]),setup_seconds=float(setup[1]),checked_initial=float(ini[1]),exit_reason=int(res[1]))
      row['initial_quantization_relerr']=abs(row['checked_initial']-initial)/max(1,initial)
      row['native_final_relerr']=abs(row['cost']-row['native_cost'])/max(1,row['cost'])
      row['trace_native']=[dict(iter=int(i),cost=float(c),wall_s=float(t)) for i,c,t in re.findall(r'TRACE iter=(\d+) cost=(\S+) seconds=(\S+)',log)]
     else:
      res=re.search(r'RESULT .*?iters=(\d+) final_cost=([\d.e+-]+) solve_seconds=([\d.e+-]+)',log);assert res
      cost=audit(state,dims,obs);reported=float(res[2]);error=abs(cost-reported)/max(1,abs(cost))
      counts=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+).*?cand_evals=(\d+)',log);assert counts
      scoring=re.search(r'\[scoring\].*?total_scored=(\d+)',log);rescue=re.search(r'\[menu-backtrack\].*?rescues=(\d+)',log)
      with stem.with_suffix('.csv').open() as f:trace=list(csv.DictReader(t for t in f if not t.startswith('#')))
      init_error=abs(float(trace[0]['cost'])-initial)/max(1,initial)
      row.update(status='ok' if error<1e-7 and init_error<1e-6 else 'audit_failed',iters=int(res[1]),cost=cost,reported_cost=reported,audit_relerr=error,initial_relerr=init_error,seconds=float(res[3]),accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]),menu_evals=int(counts[4]),total_scored=int(scoring[1]),rescues=int(rescue[1]),rearms=log.count('rearmed after meaningful'),progressive_stops=len(re.findall(r'PROGRESSIVE .*?stopped=1',log)),state_sha256=sha(state),trace=trace)
     row['budget_guard_fired']='BUDGET stop=' in log
     if budget:row['overshoot_seconds']=max(0,row['seconds']-budget)
     if not math.isfinite(row['cost']):row['status']='nonfinite'
    jp.write_text(json.dumps(row,indent=2)+'\n');print('DONE',scene,label,rep,{k:row.get(k) for k in ['status','cost','seconds','rejects','rearms','audit_relerr']},flush=True)
    if row['status']!='ok' and not a.keep_going:raise RuntimeError('Failed cell retained: '+str(jp))
if __name__=='__main__':main()
