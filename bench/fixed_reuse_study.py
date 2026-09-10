#!/usr/bin/env python3
"""Collect first stratified expansions and benchmark their unchanged operators."""
import argparse,json,os,pathlib,re,subprocess
from profile_iterations import COMMON,sha
from novelty_ablation import EXEC
p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=pathlib.Path('/workspace/prism-fixed-reuse'));a=p.parse_args();root=a.root
base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};base.update(COMMON);base.update(EXEC);base.update(OCA_NSHIFTS='5',OCA_MENU_BACKTRACK='8',OCA_BACKTRACK_REARM='1',OCA_COMPACT_FRAGMENTS='2',OCA_DEMAND_MENU='2',OCA_KRYLOV_REUSE='3',OCA_REUSE_FIXED_STUDY='1',OCA_MAX_SECONDS='60')
keys='snapshot outer source_depth bucket rep method narrow projection wide decision fallback calls seconds diagnostic_verify charged capture residual tolerance valid'.split()
pattern='FIXED_REUSE '+r'\s+'.join(k+r'=(\S+)' for k in keys)
all_rows=[];summaries=[]
for scene in ['ladybug-49','ladybug-1197','dubrovnik-173']:
 if scene=='dubrovnik-173' and len({(r['scene'],r['snapshot']) for r in all_rows})>=6:break
 directory=root/'cases'/scene;directory.mkdir(parents=True,exist_ok=True);stem=root/scene
 env=dict(base,OCA_REUSE_FIXED_DIR=str(directory));data=pathlib.Path('/workspace/bal')/(scene+'.txt')
 cmd=['flock','/tmp/prism_gpu.lock','timeout','90',str(root/'prism-frozen'),'--problem',str(data),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','80']
 assert not stem.with_suffix('.log').exists()
 stem.with_suffix('.manifest.json').write_text(json.dumps(dict(command=cmd,flags={k:v for k,v in env.items() if k.startswith('OCA_')},binary_sha256=sha(root/'prism-frozen'),data_sha256=sha(data)),indent=2)+'\n')
 print('RUN',scene,flush=True)
 with stem.with_suffix('.log').open('w') as f:r=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT)
 assert r.returncode==0,(scene,r.returncode)
 log=stem.with_suffix('.log').read_text();rows=[]
 for m in re.findall(pattern,log):
  row=dict(scene=scene,**dict(zip(keys,map(float,m))));rows.append(row)
 assert len(rows)==log.count('FIXED_REUSE snapshot=') and len(rows)%9==0
 for case in {r['snapshot'] for r in rows}:assert len([r for r in rows if r['snapshot']==case])==9
 all_rows+=rows;summaries.append(dict(scene=scene,cases=len(rows)//9,quota_complete='FIXED_DONE ' in log))
 (root/'results.json').write_text(json.dumps(all_rows,indent=2)+'\n');(root/'collection.json').write_text(json.dumps(summaries,indent=2)+'\n')
 print('DONE',summaries[-1],flush=True)
assert 6<=sum(s['cases'] for s in summaries)<=10
