#!/usr/bin/env python3
"""Run the confirmed one-shift camera TR candidate with its frozen settings."""
import argparse,pathlib,os,subprocess,json
from profile_iterations import COMMON
from novelty_ablation import EXEC
from build_tr_candidate import sha

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--binary',type=pathlib.Path,default=pathlib.Path('/workspace/prism-tr-candidate/prism-tr'));ap.add_argument('--problem',type=pathlib.Path,required=True);ap.add_argument('--target',type=float,required=True);ap.add_argument('--seconds',type=float,default=4);ap.add_argument('--iterations',type=int,default=100000);ap.add_argument('--output',type=pathlib.Path,required=True);ap.add_argument('--audit-model',action='store_true');a=ap.parse_args()
 flags=dict(COMMON,**EXEC,OCA_MENU_BACKTRACK='8',OCA_BACKTRACK_REARM='1',OCA_COMPACT_FRAGMENTS='2',OCA_POINT_SAFEGUARD='1',OCA_DEMAND_MENU='0',OCA_SWITCH_RESTART='0',OCA_CAMERA_TR='1',OCA_NSHIFTS='1',OCA_TR_RECURRENCE='1',OCA_TARGET_COST=str(a.target),OCA_MAX_SECONDS=str(a.seconds))
 if a.audit_model:flags['OCA_TR_RECURRENCE_AUDIT']='1'
 env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};env.update(flags)
 a.output.parent.mkdir(parents=True,exist_ok=True)
 for suffix in ['.log','.stderr','.csv','.state','.manifest.json']:assert not a.output.with_suffix(suffix).exists(),'Refusing to overwrite run artifacts'
 cmd=['flock','/tmp/prism_gpu.lock','timeout',str(max(40,int(a.seconds)+20)),str(a.binary),'--problem',str(a.problem),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter',str(a.iterations),'--csv',str(a.output.with_suffix('.csv')),'--state_out',str(a.output.with_suffix('.state'))]
 a.output.with_suffix('.manifest.json').write_text(json.dumps(dict(command=cmd,flags=flags,binary_sha256=sha(a.binary),input_sha256=sha(a.problem)),indent=2))
 with a.output.with_suffix('.log').open('x') as f,a.output.with_suffix('.stderr').open('x') as e:r=subprocess.run(cmd,env=env,stdout=f,stderr=e)
 if r.returncode:raise SystemExit(r.returncode)
 print(a.output.with_suffix('.log'))
if __name__=='__main__':main()
