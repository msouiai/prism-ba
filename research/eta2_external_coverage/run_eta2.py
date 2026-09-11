#!/usr/bin/env python3
"""Unchanged Eta2 binary, fixed targets, independent endpoint checks."""
import argparse
import csv
from contextlib import contextmanager
import fcntl
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time

P = Path(__file__).resolve().parent
CHAMP = json.loads((P.parent / 'eta2_champion/champion.json').read_text())
BINARY = Path('/tmp/prism-rl-actor/build/prism-tr')
sys.path.insert(0, str(P.parent / 'eta2_champion/bench'))
from audit_prism_state import audit, observations
BATCH_LOCKED = False


@contextmanager
def measurement_lock():
    if BATCH_LOCKED:
        yield
    else:
        with open('/tmp/prism_gpu.lock', 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def run(scene, arm, rep, stage, target, expected_input, initial):
    folder = P / 'evidence' / stage / f'{scene}-{arm}-{rep}'
    folder.mkdir(parents=True, exist_ok=True)
    result = folder / 'result.json'
    if result.exists():
        row = json.loads(result.read_text())
        assert row['target'] == target
        return row
    assert sha(BINARY) == CHAMP['binary_sha256']
    iterations = 10000 if arm == 'stop_disabled' else 600
    flags = dict(CHAMP['flags'], OCA_TARGET_COST=str(target), OCA_MAX_SECONDS='60')
    if arm == 'stop_disabled':
        flags['OCA_FTOL'] = '0'
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('OCA_', 'CASPAR_', 'CERES_', 'COLMAP_MFREE', 'MF_DEBUG'))}
    env.update(flags)
    problem = Path('/workspace/bal') / (scene + '.txt')
    state = folder / 'endpoint.state'
    cmd = [str(BINARY), '--problem', str(problem), '--algo', 'mfree_shifted_cg',
           '--dof9', '--zero_k2', '--lam0', '0.1', '--max_iter', str(iterations),
           '--csv', str(folder / 'curve.csv'), '--state_out', str(state)]
    write(folder / 'manifest.json', dict(command=cmd, flags=flags, target=target,
          cap=60, max_iter=iterations, binary_sha256=sha(BINARY),
          input_sha256=expected_input, protocol_sha256=sha(P / 'PROTOCOL.md')))
    print('QUEUED', stage, scene, arm, rep, flush=True)
    with measurement_lock():
        assert sha(problem) == expected_input
        dims, obs = observations(problem)
        print('RUN', stage, scene, arm, rep, flush=True)
        with (folder / 'stdout.log').open('w') as out, (folder / 'stderr.log').open('w') as err:
            start = time.monotonic()
            try:
                proc = subprocess.run(cmd, env=env, stdout=out, stderr=err, timeout=180)
                returncode = proc.returncode
            except subprocess.TimeoutExpired:
                returncode = 124
            process_seconds = time.monotonic() - start
        row = dict(scene=scene, arm=arm, rep=rep, stage=stage, target=target,
                   cap=60, iterations_cap=iterations, returncode=returncode,
                   process_seconds=process_seconds, valid=False, hit=False,
                   source=str(folder.relative_to(P)))
        try:
            assert returncode == 0, returncode
            text = (folder / 'stdout.log').read_text()
            m = re.search(r'RESULT .*?iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)', text)
            assert m, 'Missing RESULT'
            reached = re.search(r'TARGET reached outer=(\d+) seconds=(\S+) cost=(\S+)', text)
            counts = re.search(r'MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)', text)
            assert counts
            with (folder / 'curve.csv').open() as f:
                curve = list(csv.DictReader(line for line in f if not line.startswith('#')))
            costs = [float(v['cost']) for v in curve]
            assert abs(costs[0] - initial) / max(1, initial) < 1e-6
            assert all(math.isfinite(c) for c in costs)
            assert all(b <= a + 1e-8 * max(1, abs(a)) for a, b in zip(costs, costs[1:]))
            cost = audit(state, dims, obs)
            native_cost = float(m[2])
            error = abs(cost - native_cost) / max(1, abs(cost))
            assert math.isfinite(cost) and error < 1e-6, error
            crossing = float(reached[2]) if reached else None
            seconds = float(m[3])
            stop = 'target' if reached else 'budget' if 'BUDGET stop=' in text else 'ftol' if 'converged (OCA_FTOL' in text else 'outer_cap' if int(m[1]) >= iterations else 'other'
            row.update(valid=True, hit=crossing is not None and crossing <= 60 and cost <= target,
                       cost=cost, native_cost=native_cost, audit_relative_error=error,
                       target_seconds=crossing, native_seconds=seconds, outers=int(m[1]),
                       accepts=int(counts[1]), rejects=int(counts[2]), matvecs=int(counts[3]),
                       stop_reason=stop, target_gap=cost / target - 1,
                       state_sha256=sha(state), cap_hit=stop in ['budget', 'outer_cap'])
        except Exception as exc:
            row['error'] = str(exc)
        if state.exists():
            gz = Path(str(state) + '.gz')
            with state.open('rb') as f, gzip.open(gz, 'wb', compresslevel=1) as out:
                shutil.copyfileobj(f, out)
            with gzip.open(gz, 'rb') as f:
                assert hashlib.file_digest(f, 'sha256').hexdigest() == sha(state)
            row['compressed_state_sha256'] = sha(gz)
            state.unlink()  # Only this run's generated raw file, after verified lossless preservation.
        del obs
        write(result, row)
    print('DONE', scene, arm, rep, 'valid', row['valid'], 'hit', row['hit'],
          'cost', row.get('cost'), 'seconds', row.get('target_seconds'),
          'stop', row.get('stop_reason'), 'error', row.get('error'), flush=True)
    return row


def main():
    global BATCH_LOCKED
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['venice', 'storm'])
    ap.add_argument('--batch-lock', action='store_true')
    args = ap.parse_args()
    batch_lock = None
    if args.batch_lock:
        print('Waiting for the current solve to finish; holding one lock for the entire requested stage.', flush=True)
        batch_lock = open('/tmp/prism_gpu.lock', 'w')
        fcntl.flock(batch_lock, fcntl.LOCK_EX)
        BATCH_LOCKED = True
    assert sha(BINARY) == CHAMP['binary_sha256']
    rows = []
    if args.stage == 'venice':
        ref = json.loads((P / 'provenance/venice-52-ceres-lm-10000-600-1.json').read_text())
        for rep in range(10):
            arms = ['champion', 'stop_disabled']
            for arm in arms[rep % 2:] + arms[:rep % 2]:
                rows.append(run('venice-52', arm, rep, 'venice', 243740.27,
                                ref['data_sha256'], ref['independent_score_init']))
    else:
        targets_path = P / 'storm-targets.json'
        if targets_path.exists():
            registered = json.loads(targets_path.read_text())
        else:
            registered = {}
            for scene in ['final-3068', 'final-4585']:
                groups = {}
                for profile in ['lm-10000', 'dogleg-10000']:
                    rr = [json.loads(f.read_text()) for f in sorted((P / 'evidence/ceres-storm').glob(f'{scene}-ceres-{profile}-600-*.json'))]
                    assert len(rr) == 3 and all(r['status'] == 'ok' for r in rr), (scene, profile, 'Incomplete Ceres baseline')
                    groups[profile] = dict(median=statistics.median(r['cost'] for r in rr), rows=rr)
                reference = min(groups, key=lambda k: groups[k]['median'])
                first = groups[reference]['rows'][0]
                registered[scene] = dict(target=1.01 * groups[reference]['median'],
                    reference_profile=reference, groups=groups, input_sha256=first['data_sha256'],
                    initial=first['independent_score_init'])
            write(targets_path, registered)
        for scene, ref in registered.items():
            for rep in range(10):
                rows.append(run(scene, 'champion', rep, 'storm', ref['target'], ref['input_sha256'], ref['initial']))
    write(P / (args.stage + '-results.json'), rows)
    if batch_lock is not None:
        batch_lock.close()


if __name__ == '__main__':
    main()
