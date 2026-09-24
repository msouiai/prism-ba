#!/usr/bin/env python3
"""24 paired seeded-initialization tests; original medium goals and frozen solvers."""
import hashlib,json,pathlib,shutil,subprocess,sys
import numpy as np
import expanded_caspar_screen as engine
ROOT=pathlib.Path('/workspace/prism-caspar-noise')
SCENES=['trafalgar-126','dubrovnik-88','final-1936','final-13682']
SEEDS=[17,29,43]

def read_parameters(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  header=f.readline();h.update(header);dims=tuple(map(int,header.split()))
  for _ in range(dims[2]):h.update(f.readline())
  values=np.loadtxt(f)
 return dims,h.hexdigest(),values

def verify_scene(scene):
 original=pathlib.Path('/workspace/bal')/(scene+'.txt');dims,oh,values=read_parameters(original);nc,np_,no=dims
 cameras=values[:9*nc].reshape(nc,9);points=values[9*nc:].reshape(np_,3)
 radius=float(np.median(np.linalg.norm(points-np.median(points,axis=0),axis=1)))
 verified=[]
 for seed in SEEDS:
  p=ROOT/'data'/f'{scene}-seed{seed}.txt';m=json.loads(p.with_suffix('.json').read_text());d,h,v=read_parameters(p)
  assert d==dims and h==oh,'observations changed'
  c=v[:9*nc].reshape(nc,9);x=v[9*nc:].reshape(np_,3)
  assert np.array_equal(c[:,6:9],cameras[:,6:9]),'intrinsics changed'
  rng=np.random.default_rng(seed);expected_c=cameras.copy();expected_x=points.copy()
  expected_c[:,:3]+=rng.normal(0,.001,(nc,3));expected_c[:,3:6]+=rng.normal(0,.001*radius,(nc,3));expected_x+=rng.normal(0,.001*radius,expected_x.shape)
  assert np.array_equal(c,expected_c) and np.array_equal(x,expected_x),'seed/roundtrip mismatch'
  assert np.isfinite(v).all() and not np.array_equal(v,values)
  assert m['source_sha256']==engine.sha(original) and m['data_sha256']==engine.sha(p) and m['point_radius']==radius
  verified.append(dict(scene=scene,seed=seed,data=str(p),data_sha256=m['data_sha256'],original_sha256=m['source_sha256'],observation_bytes_sha256=oh,dims=dims,radius=radius,rotation_sigma=.001,translation_point_sigma=.001*radius))
 return verified

def main():
 ROOT.mkdir(exist_ok=True);(ROOT/'data').mkdir(exist_ok=True)
 previous=json.loads(pathlib.Path('/workspace/prism-caspar-expanded/protocol.json').read_text());old=json.loads(pathlib.Path('/workspace/prism-caspar-expanded/measurement-plan.json').read_text())
 reference={s:next(j for j in old['jobs'] if j['scene']==s and j['level']=='medium') for s in SCENES}
 protocol=dict(scenes=SCENES,seeds=SEEDS,rotation_sigma=.001,translation_point_sigma='0.001 times median centered point radius',rotation_parameterization='additive angle-axis coordinates',observations='unchanged bytes',intrinsics='unchanged',targets={s:reference[s]['target'] for s in SCENES},caps={s:reference[s]['cap'] for s in SCENES},prism_sha256=engine.sha(engine.PRISM),caspar_sha256=engine.sha(engine.CASPAR),jobs=24,measurement_repeats_per_seed=1,process_timeout=180)
 assert protocol['prism_sha256']==previous['prism_sha256'] and protocol['caspar_sha256']==previous['caspar_sha256']
 if (ROOT/'protocol.json').exists():assert json.loads((ROOT/'protocol.json').read_text())==protocol
 else:engine.write(ROOT/'protocol.json',protocol)
 verified=[]
 for scene in SCENES:
  if not all((ROOT/'data'/f'{scene}-seed{k}.json').exists() for k in SEEDS):
   print('PREPARE',scene,flush=True)
   subprocess.run([sys.executable,str(pathlib.Path(__file__).with_name('perturb_bal.py')),'--data','/workspace/bal','--out',str(ROOT/'data'),'--scenes',scene],check=True)
  print('VERIFY INPUTS',scene,flush=True);verified.extend(verify_scene(scene));engine.write(ROOT/'verified-inputs.json',verified)
 jobs=[]
 for i,seed in enumerate(SEEDS):
  order=SCENES if i%2==0 else list(reversed(SCENES))
  for k,scene in enumerate(order):
   for arm in (['restart','caspar64'] if (i+k)%2==0 else ['caspar64','restart']):
    jobs.append(dict(scene=scene,seed=seed,rep=i+1,level='medium',target=reference[scene]['target'],cap=reference[scene]['cap'],data=str(ROOT/'data'/f'{scene}-seed{seed}.txt'),cpu_cache=str(ROOT/'cpu-cache'),process_timeout=180,arm=arm,name=f'{scene}-seed{seed}-{arm}'))
 plan=dict(jobs=jobs)
 if (ROOT/'plan.json').exists():assert json.loads((ROOT/'plan.json').read_text())==plan
 else:engine.write(ROOT/'plan.json',plan)
 tooling=ROOT/'tooling';tooling.mkdir(exist_ok=True)
 names=['noise_caspar_screen.py','expanded_caspar_screen.py','current_caspar_comparison.py','early_restart_screen.py','perturb_bal.py','cached_benchmark_input.py','audit_prism_state.py','profile_iterations.py','novelty_ablation.py']
 hashes={}
 for n in names:
  p=pathlib.Path(__file__).with_name(n);hashes[n]=engine.sha(p)
  if not (tooling/n).exists():shutil.copyfile(p,tooling/n)
  assert engine.sha(tooling/n)==hashes[n]
 engine.write(ROOT/'tooling-hashes.json',hashes)
 engine.ROOT=ROOT;rows=[]
 for j in jobs:
  assert engine.sha(engine.PRISM)==protocol['prism_sha256'] and engine.sha(engine.CASPAR)==protocol['caspar_sha256']
  rows.append(engine.run(j,'measurements'));engine.write(ROOT/'partial-results.json',rows)
 engine.write(ROOT/'results.json',rows);print('COMPLETE',len(rows),flush=True)
if __name__=='__main__':main()
