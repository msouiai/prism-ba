"""Fresh rotated pairs: a fixed PRISM configuration and frozen Caspar FP32."""
import argparse
import json
import math
import os
import pathlib
import re
import struct
import subprocess
import time
from solver_novelty_ablation import flags, SCENES
from cached_benchmark_input import load_input
from audit_prism_state import audit
from build_tr_candidate import sha


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=pathlib.Path, required=True)
    ap.add_argument('--arm', default='tr_no_projection')
    ap.add_argument('--binary', type=pathlib.Path, default=pathlib.Path('/tmp/prism-lm-point-rescue/build/prism-tr'))
    ap.add_argument('--scenes', nargs='+', default=['trafalgar-126', 'final-1936', 'final-4585', 'final-13682'])
    ap.add_argument('--reps', type=int, default=3)
    a = ap.parse_args()
    a.output.mkdir()
    caspar = pathlib.Path('/workspace/prism-caspar-current/caspar32')
    assert sha(caspar) == 'de038488e929a8fad674d1096c5f61619f3039e6409a81670dab0df7dffe0919'
    protocol = dict(arm=a.arm, reps=a.reps, scenes=a.scenes, flags=flags(a.arm),
                    binary_sha256=sha(a.binary), caspar_sha256=sha(caspar),
                    inputs={s:sha('/workspace/bal/'+s+'.txt') for s in a.scenes},
                    scope='Rotated native time to common independently audited original-double objective. Caspar FP32 stops at .1% tighter native target to allow for rounding; this empirical margin is not a certificate. PRISM includes solver-local setup; Caspar excludes graph setup. Both exclude loading. Frozen standalone Caspar backend, not full COLMAP pipeline. Caps include all timed rescue and scoring work. No per-scene selection.')
    (a.output/'protocol.json').write_text(json.dumps(protocol, indent=2))
    rows=[]
    for rep in range(a.reps):
        for si,scene in enumerate(a.scenes):
            dh,(dims,obs),initial=load_input(pathlib.Path('/workspace/bal')/(scene+'.txt'),'/workspace/prism-caspar-expanded/cpu-cache')
            assert dh==protocol['inputs'][scene]
            nominal,cap=SCENES[scene];target=nominal*(1-1e-8)
            arms=[a.arm,'caspar32'][::(-1 if (rep+si)%2 else 1)]
            for arm in arms:
                stem=a.output/f'{scene}-{arm}-{rep+1}'
                env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}
                if arm=='caspar32':
                    env.update(CASPAR_TARGET_COST=str(target*.999),CASPAR_MAX_SECONDS=str(cap),CASPAR_STATE_OUT=str(stem)+'.state')
                    binary=caspar;cmd=[str(binary),'/workspace/bal/'+scene+'.txt','100000','default']
                else:
                    env.update(flags(arm),OCA_TARGET_COST=str(nominal),OCA_MAX_SECONDS=str(cap));binary=a.binary
                    cmd=[str(binary),'--problem','/workspace/bal/'+scene+'.txt','--algo','mfree_shifted_cg','--dof9','--zero_k2','--mf-no-alpha','--max_iter','100000','--state_out',str(stem)+'.state']
                    if '_low' in arm:cmd+=['--lam0','1e-4']
                cmd=['flock','/tmp/prism_gpu.lock','timeout','240']+cmd
                stem.with_suffix('.manifest.json').write_text(json.dumps(dict(command=cmd,flags={k:v for k,v in env.items() if k.startswith(('OCA_','CASPAR_'))},binary_sha256=sha(binary),input_sha256=dh),indent=2))
                print('RUN',stem.name,flush=True);start=time.monotonic()
                with stem.with_suffix('.log').open('x') as out,stem.with_suffix('.stderr').open('x') as err:
                    p=subprocess.run(cmd,env=env,stdout=out,stderr=err)
                row=dict(scene=scene,arm=arm,rep=rep+1,returncode=p.returncode,process_wall=time.monotonic()-start,target=target,cap=cap,hit=False)
                if p.returncode==0:
                    log=stem.with_suffix('.log').read_text();cost=audit(stem.with_suffix('.state'),dims,obs)
                    if arm=='caspar32':
                        reported=float(re.search(r'CHECK final_score=(\S+)',log)[1]);seconds=float(re.search(r'RESULT .*?runtime=(\S+)',log)[1])
                        nt=struct.unpack('f',struct.pack('f',target*.999))[0]
                        crossing=min((float(t) for c,t in re.findall(r'TRACE iter=\d+ cost=(\S+) seconds=(\S+)',log) if float(c)<=nt),default=None)
                    else:
                        m=re.search(r'RESULT .*?final_cost=(\S+) solve_seconds=(\S+)',log);reported=float(m[1]);seconds=float(m[2])
                        c=re.search(r'TARGET reached outer=\d+ seconds=(\S+)',log);crossing=float(c[1]) if c else None
                    error=abs(cost-reported)/max(1,cost);assert math.isfinite(cost) and error<1e-7
                    row.update(cost=cost,seconds=seconds,crossing=crossing,hit=crossing is not None and crossing<=cap and cost<=target,audit_error=error,state_sha256=sha(stem.with_suffix('.state')))
                stem.with_suffix('.result.json').write_text(json.dumps(row,indent=2));rows.append(row)
                (a.output/'results.json').write_text(json.dumps(rows,indent=2));print('DONE',json.dumps(row),flush=True)


if __name__=='__main__':main()
