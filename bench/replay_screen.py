#!/usr/bin/env python3
"""Bounded same-checkpoint controller ablation; preserve raw logs and failures."""
import argparse,csv,json,os,pathlib,re,subprocess
from profile_iterations import COMMON,sha
from novelty_ablation import EXEC

def main():
 p=argparse.ArgumentParser();p.add_argument('--binary',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);p.add_argument('--scenes',nargs='+',default=['ladybug-1197','dubrovnik-173']);a=p.parse_args()
 a.out.mkdir(parents=True,exist_ok=True);binary=str(a.binary.resolve());binary_sha=sha(binary)
 base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','COLMAP_MFREE','MF_DEBUG'))};base.update(COMMON);base.update(EXEC);base.update(OCA_NSHIFTS='5',OCA_MENU_BACKTRACK='8')
 for scene in a.scenes:
  checkpoint=a.out/(scene+'.checkpoint');data=pathlib.Path('/workspace/bal')/(scene+'.txt');data_sha=sha(data)
  def run(name,flags,logged=False):
   stem=a.out/(scene+'-'+name);manifest=stem.with_suffix('.manifest.json')
   if manifest.exists():raise RuntimeError('Use a fresh output directory; retained runs are never overwritten')
   env=dict(base,**flags)
   if logged:env['OCA_LEARN_LOG']=str(stem.with_suffix('.jsonl'))
   command=['flock','/tmp/prism_gpu.lock','timeout','60',binary,'--problem',str(data),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','100','--csv',str(stem.with_suffix('.csv'))]
   assert sha(binary)==binary_sha
   m=dict(command=command,binary_sha256=binary_sha,data_sha256=data_sha,flags={k:v for k,v in env.items() if k.startswith('OCA_')},logged=logged)
   if 'OCA_REPLAY_LOAD' in flags:m['checkpoint_sha256']=sha(checkpoint)
   manifest.write_text(json.dumps(m,indent=2)+'\n');print('RUN',scene,name,flush=True)
   with stem.with_suffix('.log').open('w') as f,stem.with_suffix('.stderr').open('w') as e:r=subprocess.run(command,env=env,stdout=f,stderr=e)
   result=dict(scene=scene,arm=name,returncode=r.returncode,status='failed')
   if r.returncode==0:
    log=stem.with_suffix('.log').read_text()
    match=re.search(r'RESULT .*?iters=(\d+) final_cost=([\d.e+-]+) solve_seconds=([\d.e+-]+)',log);assert match
    replay=re.search(r'REPLAY (?:load|save) (.*)',log);assert replay,'confirmation checkpoint did not activate'
    header={k:float(v) for k,v in re.findall(r'(\w+)=([\d.e+-]+)',replay[1])}
    counts=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+).*?cand_evals=(\d+)',log);assert counts
    scored=re.search(r'\[scoring\].*?total_scored=(\d+)',log)
    rescue=re.search(r'\[menu-backtrack\].*?rescues=(\d+)',log)
    with stem.with_suffix('.csv').open() as f:trace=list(csv.DictReader(x for x in f if not x.startswith('#')))
    result.update(status='ok',iters=int(match[1]),cost=float(match[2]),seconds=float(match[3]),checkpoint=header,
      rollout_accepts=int(counts[1])-header['accepts'],rollout_rejects=int(counts[2])-header['rejects'],
      rollout_matvecs=int(counts[3])-header['matvecs'],rollout_scored=int(scored[1])-header['scored'],
      rollout_rescues=int(rescue[1])-header['rescues'],rearms=log.count('rearmed after meaningful'),trace=trace)
   stem.with_suffix('.result.json').write_text(json.dumps(result,indent=2)+'\n')
   print('DONE',scene,name,{k:v for k,v in result.items() if k not in ['trace','checkpoint']},flush=True)
   assert r.returncode==0
   return result
  capture=run('capture',dict(OCA_REPLAY_SAVE=str(checkpoint),OCA_REPLAY_AT='confirm',OCA_REPLAY_STEPS='6'),True)
  assert checkpoint.exists()
  replay=run('replay-check',dict(OCA_REPLAY_LOAD=str(checkpoint),OCA_REPLAY_STEPS='6'),True)
  # Restoring exact input/controller state does not promise deterministic CUDA
  # atomic accumulation. Keep the original continuation and the replay both.
  check=dict(endpoint_relative_difference=abs(replay['cost']-capture['cost'])/capture['cost'],
             capture=capture['cost'],replay=replay['cost'],checkpoint_sha256=sha(checkpoint))
  (a.out/(scene+'-continuation-check.json')).write_text(json.dumps(check,indent=2)+'\n')
  for rep in [1,2]:
   for arm in (['original','rearm'] if rep==1 else ['rearm','original']):
    flags=dict(OCA_REPLAY_LOAD=str(checkpoint),OCA_REPLAY_STEPS='20')
    if arm=='rearm':flags['OCA_BACKTRACK_REARM']='1'
    run(arm+'-'+str(rep),flags)
  run('rearm-trace',dict(OCA_REPLAY_LOAD=str(checkpoint),OCA_REPLAY_STEPS='20',OCA_BACKTRACK_REARM='1'),True)
if __name__=='__main__':main()
