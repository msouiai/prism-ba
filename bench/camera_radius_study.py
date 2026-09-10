#!/usr/bin/env python3
"""Four bounded owner runs, twelve matched-state radius captures; no rollout claim."""
import pathlib,os,json,re,subprocess,time,shutil
from profile_iterations import COMMON,sha
from novelty_ablation import EXEC
ROOT=pathlib.Path('/workspace/prism-camera-radius')
def main():
 flags=dict(COMMON,**EXEC,OCA_MENU_BACKTRACK='8',OCA_BACKTRACK_REARM='1',OCA_COMPACT_FRAGMENTS='2',OCA_POINT_SAFEGUARD='1',OCA_DEMAND_MENU='0',OCA_SWITCH_RESTART='0',OCA_CAMERA_TR='1',OCA_TARGET_COST='1e-100',OCA_MAX_SECONDS='15')
 jobs=[dict(scene=s,width=w) for s in ['trafalgar-126','dubrovnik-88'] for w in [1,5]]
 protocol=dict(jobs=jobs,flags=flags,iterations=7,captures=[0,3,6],basis_depth=64,radius_multipliers=[.5,1,2],binary_sha256=sha(ROOT/'prism-radius'),source_sha256=sha(ROOT/'source-radius.cu'),data_sha256={s:sha(pathlib.Path('/workspace/bal')/(s+'.txt')) for s in ['trafalgar-126','dubrovnik-88']},selection='Current first; if rejected try half. If accepted with rho>.75 and norm>=.8 radius, try double. Choose double only if acceptable and lower cost. Accept iff actual>0,pred>0,rho>=.1,norm<=R*(1+1e-8). At most two trials.',limitations='Instrumented owner runs, diagnostic candidates never committed. All three scored; policy replay and work estimate are counterfactual. One-radius reference uses exactly the same 64-vector basis. First captures overlap across owners; two scenes only. Full-space KKT accuracy reported, not assumed.',tooling_sha256={})
 for p in [pathlib.Path(__file__),pathlib.Path(__file__).with_name('build_camera_radius.py')]+list((ROOT/'tooling').iterdir()):protocol['tooling_sha256'][str(p)]=sha(p)
 dest=ROOT/'protocol.json';assert not dest.exists();dest.write_text(json.dumps(protocol,indent=2))
 for name in ['camera_radius_study.py','build_camera_radius.py','test_projected_radius.cc']:shutil.copy2(pathlib.Path(__file__).with_name(name),ROOT/'tooling'/name)
 base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}
 for j in jobs:
  stem=ROOT/(j['scene']+'-tr'+str(j['width']));env=dict(base,**flags,OCA_NSHIFTS=str(j['width']),OCA_RADIUS_CAPTURE=str(stem))
  cmd=['flock','/tmp/prism_gpu.lock','timeout','45',str(ROOT/'prism-radius'),'--problem','/workspace/bal/'+j['scene']+'.txt','--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','7','--csv',str(stem.with_suffix('.csv')),'--state_out',str(stem.with_suffix('.state'))]
  stem.with_suffix('.manifest.json').write_text(json.dumps(dict(job=j,command=cmd,flags={k:v for k,v in env.items() if k.startswith('OCA_')}),indent=2))
  print('RUN',stem.name,flush=True);t=time.monotonic()
  with stem.with_suffix('.log').open('x') as f,stem.with_suffix('.stderr').open('x') as e:q=subprocess.run(cmd,env=env,stdout=f,stderr=e)
  stem.with_suffix('.process.json').write_text(json.dumps(dict(returncode=q.returncode,wall=time.monotonic()-t)))
  assert q.returncode==0
  lines=[l for l in stem.with_suffix('.log').read_text().splitlines() if l.startswith('RADIUS_CAPTURE')];assert len(lines)==9
  print('DONE',stem.name,'9 candidates',flush=True)
if __name__=='__main__':main()
