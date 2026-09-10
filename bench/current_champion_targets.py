#!/usr/bin/env python3
"""Frozen, rotated equal-quality pairs with original-observation endpoint audits."""
import argparse
import hashlib
import json
import math
import os
import pathlib
import re
import socket
import statistics
import subprocess
import time

from audit_prism_state import audit, observations

ROOT = pathlib.Path('/workspace')
SCENES = {
    'ladybug-1723': (448194.125, 8),
    'final-1936': (5074937.9725361075, 8),
    'trafalgar-126': (104534.24152926281, 4),
    'final-4585': (7488277.5282109585, 12),
}
HASHES = {
    'champion': '24645b91408f7790a19ed67c6e42a183962df51719fcd69639447f022e34bb76',
    'caspar32': 'de038488e929a8fad674d1096c5f61619f3039e6409a81670dab0df7dffe0919',
    'caspar64': '6ca81c85112005b024df4972b0ec16c3819838999a876513e148c58ed8f35eb2',
}


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=pathlib.Path, required=True)
    p.add_argument('--champion', type=pathlib.Path, default=pathlib.Path('/tmp/prism-model-followup/build/prism-tr'))
    p.add_argument('--candidate', type=pathlib.Path)
    p.add_argument('--candidate-env', default='{}', help='JSON of candidate-only OCA variables')
    p.add_argument('--arms', nargs='+', default=['champion', 'caspar32', 'caspar64'])
    p.add_argument('--scenes', nargs='+', default=['ladybug-1723', 'final-1936', 'trafalgar-126'])
    p.add_argument('--reps', type=int, default=3)
    p.add_argument('--quality-multiplier', type=float, choices=[1.005, 1.01, 1.02], default=1.01)
    p.add_argument('--profile', action='store_true', help='Diagnostic timings only; changes synchronization')
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    binaries = dict(champion=a.champion, caspar32=ROOT/'prism-caspar-current/caspar32',
                    caspar64=ROOT/'prism-caspar-current/caspar64', candidate=a.candidate)
    for arm in a.arms:
        assert binaries[arm] and binaries[arm].is_file()
        if arm in HASHES:
            assert sha(binaries[arm]) == HASHES[arm], arm
    flags = json.loads((ROOT/'prism-controller-attribution/selected_candidate.json').read_text())
    candidate_env = json.loads(a.candidate_env)
    assert all(k.startswith('OCA_') for k in candidate_env)
    protocol = dict(host=socket.gethostname(), quality_multiplier=a.quality_multiplier, scenes={s:dict(anchor=SCENES[s][0], target=a.quality_multiplier*SCENES[s][0], cap=SCENES[s][1], input_sha256=sha(ROOT/'bal'/f'{s}.txt')) for s in a.scenes},
        arms=a.arms, reps=a.reps, binary_sha256={arm:sha(binaries[arm]) for arm in a.arms},
        champion=flags, candidate_env=candidate_env, profiling=a.profile,
        scope='Fixed historical quality anchors times the recorded quality_multiplier, not a fraction of initial cost. Anchors: Ladybug retained Caspar FP64 endpoint; Final/Trafalgar prior fixed benchmark targets. Native solve clocks exclude loading; Prism includes solver-local setup, Caspar graph setup is also reported separately. Original FP64 input objective audited at every exported endpoint. FP32 native stop uses 0.1% empirical safety margin below common target. All arms max 600 accepted outers; capped misses retained, never assigned artificial speedups. Rotated serial arms, three repeats for performance conclusions. Profiling runs excluded from headline timing.')
    (a.output/'protocol.json').write_text(json.dumps(protocol, indent=2)+'\n')
    rows = []
    cache = {}
    for rep in range(a.reps):
        for si, scene in enumerate(a.scenes):
            if scene not in cache:
                cache[scene] = observations(ROOT/'bal'/f'{scene}.txt')
            dims, obs = cache[scene]
            offset = (rep + si) % len(a.arms)
            for arm in a.arms[offset:] + a.arms[:offset]:
                spec = protocol['scenes'][scene]
                target, cap = spec['target'], spec['cap']
                stem = a.output/f'{scene}-{arm}-{rep+1}'
                env = {k:v for k,v in os.environ.items() if not k.startswith(('OCA_', 'CASPAR_', 'COLMAP_MFREE', 'MF_DEBUG'))}
                if arm.startswith('caspar'):
                    env.update(CASPAR_TARGET_COST=str(target*(.999 if arm=='caspar32' else 1)), CASPAR_MAX_SECONDS=str(cap), CASPAR_STATE_OUT=str(stem)+'.state')
                    cmd = [str(binaries[arm]), str(ROOT/'bal'/f'{scene}.txt'), '600', 'default']
                else:
                    env.update(flags['flags'], OCA_TARGET_COST=str(target), OCA_MAX_SECONDS=str(cap))
                    if arm == 'candidate':
                        env.update(candidate_env)
                    if a.profile:
                        env['OCA_PROFILE'] = '1'
                    cmd = [str(binaries[arm]), '--problem', str(ROOT/'bal'/f'{scene}.txt'), '--algo', 'mfree_shifted_cg', '--dof9', '--zero_k2', '--mf-no-alpha', '--lam0', str(flags['initial_lambda']), '--max_iter', '600', '--state_out', str(stem)+'.state', '--mf-json', str(stem)+'.jsonl']
                cmd = ['flock', '/tmp/prism_gpu.lock', 'timeout', '180'] + cmd
                manifest = dict(command=cmd, flags={k:v for k,v in env.items() if k.startswith(('OCA_', 'CASPAR_'))}, binary_sha256=protocol['binary_sha256'][arm], input_sha256=spec['input_sha256'])
                stem.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
                print('RUN', stem.name, flush=True)
                start = time.monotonic()
                with stem.with_suffix('.log').open('x') as out, stem.with_suffix('.stderr').open('x') as err:
                    proc = subprocess.run(cmd, env=env, stdout=out, stderr=err)
                row = dict(scene=scene, arm=arm, rep=rep+1, returncode=proc.returncode, process_wall=time.monotonic()-start, target=target, cap=cap, hit=False)
                if proc.returncode == 0:
                    log = stem.with_suffix('.log').read_text()
                    cost = audit(stem.with_suffix('.state'), dims, obs)
                    if arm.startswith('caspar'):
                        reported = float(re.search(r'CHECK final_score=(\S+)', log)[1])
                        seconds = float(re.search(r'RESULT .*?runtime=(\S+)', log)[1])
                        trace = re.findall(r'TRACE iter=(\d+) cost=(\S+) seconds=(\S+) accepted=(\d+) pcg=(\d+)', log)
                        # Endpoint is independently checked; time is the completed native run.
                        # Do not use an unaudited earlier float crossing as the headline.
                        crossing = seconds if cost <= target else None
                        row.update(accepts=sum(int(t[3]) for t in trace), rejects=sum(1-int(t[3]) for t in trace), inner_iters=sum(int(t[4]) for t in trace), outers=len(trace), setup_seconds=float(re.search(r'setup_seconds=(\S+)', log)[1]))
                    else:
                        result = re.search(r'RESULT .*?final_cost=(\S+) solve_seconds=(\S+)', log)
                        reported, seconds = map(float, result.groups())
                        reached = re.search(r'TARGET reached outer=(\d+) seconds=(\S+)', log)
                        crossing = float(reached[2]) if reached else None
                        counts = re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+) negcurv=(\d+)', log)
                        repair = re.search(r'NUMERIC_REPAIR summary rebuilds=(\d+)', log)
                        checks = 0
                        for line in log.splitlines():
                            if line.startswith(('CLASSICAL_LM o=', 'ATTR_RADIUS o=')):
                                values = {k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)', line)}
                                if values['accept']:
                                    assert values['rho'] > .1
                                    if line.startswith('ATTR_RADIUS'):
                                        assert values['norm'] <= values['radius']*(1+1e-8)
                                    else:
                                        assert values['prediction'] > 0
                                    checks += 1
                        row.update(accepts=int(counts[1]), rejects=int(counts[2]), matvecs=int(counts[3]), negcurv=int(counts[4]), numeric_rebuilds=int(repair[1]) if repair else 0, accepted_checks=checks, outers=int(counts[1])+int(counts[2]))
                    error = abs(cost-reported)/max(1, cost)
                    assert math.isfinite(cost) and error < 1e-7, (scene, arm, error)
                    row.update(cost=cost, seconds=seconds, crossing=crossing, hit=crossing is not None and crossing<=cap and cost<=target, audit_error=error, state_sha256=sha(stem.with_suffix('.state')), cap_hit=seconds>=cap or row['outers']>=600)
                stem.with_suffix('.result.json').write_text(json.dumps(row, indent=2)+'\n')
                rows.append(row)
                (a.output/'results.json').write_text(json.dumps(rows, indent=2)+'\n')
                print('DONE', json.dumps(row), flush=True)
                if proc.returncode != 0:
                    raise RuntimeError(f'Failed arm {stem}; inspect log and stderr')
    summary = []
    for scene in a.scenes:
        for arm in a.arms:
            rr = [r for r in rows if r['scene']==scene and r['arm']==arm]
            tt = [r['crossing'] for r in rr if r['hit']]
            summary.append(dict(scene=scene, arm=arm, hits=len(tt), runs=len(rr), median=statistics.median(tt) if len(tt)==len(rr) else None, range=[min(tt), max(tt)] if tt else None, costs=[min(r['cost'] for r in rr), max(r['cost'] for r in rr)]))
    (a.output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
