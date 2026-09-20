#!/usr/bin/env python3
"""Run the frozen candidate from an extracted package, with explicit overrides."""
import argparse,json,os,pathlib,subprocess
root=pathlib.Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--problem',type=pathlib.Path);p.add_argument('--state-out',type=pathlib.Path,required=True);p.add_argument('--binary',default='./prism-tr');p.add_argument('--target',type=float);p.add_argument('--seconds',type=float);a=p.parse_args()
m=json.loads((root/'recommended_candidate.json').read_text());cmd=m['command'];cmd[4]=a.binary;cmd[cmd.index('--state_out')+1]=str(a.state_out.resolve())
if a.state_out.exists():p.error('State output already exists; choose a fresh path.')
if a.problem:cmd[cmd.index('--problem')+1]=str(a.problem.resolve())
env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};env.update(m['flags'])
if a.target is not None:env['OCA_TARGET_COST']=str(a.target)
if a.seconds is not None:env['OCA_MAX_SECONDS']=str(a.seconds)
raise SystemExit(subprocess.run(cmd,env=env,cwd=root).returncode)
