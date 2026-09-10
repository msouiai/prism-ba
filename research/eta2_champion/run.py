#!/usr/bin/env python3
"""Launch the frozen champion explicitly; original solver defaults are untouched."""
import argparse
import json
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--problem', type=pathlib.Path, required=True)
    ap.add_argument('--target', type=float)
    ap.add_argument('--seconds', type=float)
    ap.add_argument('--state-out', type=pathlib.Path)
    ap.add_argument('--max-iter', type=int, default=600)
    ap.add_argument('--binary', type=pathlib.Path, default=ROOT/'build/prism-eta2')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    import math
    if args.max_iter <= 0 or any(v is not None and (not math.isfinite(v) or v<=0) for v in [args.target,args.seconds]):
        ap.error('Iteration count, target and time cap must be positive and finite')
    config = json.loads((ROOT/'champion.json').read_text())
    flags = config['flags'].copy()
    if args.target is not None:
        flags['OCA_TARGET_COST'] = str(args.target)
    if args.seconds is not None:
        flags['OCA_MAX_SECONDS'] = str(args.seconds)
    cli = config['cli'].copy()
    cli[cli.index('--max_iter')+1] = str(args.max_iter)
    command = [str(args.binary.resolve()), '--problem', str(args.problem.resolve()), *cli]
    if args.state_out:
        command += ['--state_out', str(args.state_out.resolve())]
    if args.dry_run:
        print(json.dumps(dict(command=command,flags=flags),indent=2))
        return
    env = {k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}
    env.update(flags)
    subprocess.run(command,env=env,check=True)

if __name__ == '__main__':
    main()
