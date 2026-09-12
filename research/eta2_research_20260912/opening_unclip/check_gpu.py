#!/usr/bin/env python3
"""Bounded correctness/compatibility checks, not a performance grid."""
import argparse
import csv
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import statistics
import subprocess
import sys
import tempfile
import time

P = Path(__file__).resolve().parent
C = P.parent
F = C.parent / 'eta2_champion'
CHAMP = json.loads((F / 'champion.json').read_text())
sys.path.insert(0, str(F / 'bench'))
from audit_prism_state import audit, observations


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def run(cmd, env, folder):
    with open('/tmp/prism_gpu.lock', 'a') as lock:
        print('WAIT_GPU_LOCK', folder.name, flush=True)
        fcntl.flock(lock, fcntl.LOCK_EX)
        print('RUN', folder.name, flush=True)
        start = time.monotonic()
        with (folder / 'stdout.log').open('w') as out, (folder / 'stderr.log').open('w') as err:
            result = subprocess.run(cmd, env=env, stdout=out, stderr=err, timeout=180)
        seconds = time.monotonic() - start
    return result.returncode, seconds


def check_opening(output):
    active, accepted, opening, radii = False, 0, [], []
    handoff = False
    for line in output.splitlines():
        if line.startswith('OPEN_UNCLIP_ATTEMPT '):
            data = dict(part.split('=', 1) for part in line.split()[1:])
            assert int(data['accepts_before']) < 3
            assert int(data['accepts_before']) == accepted
            active = True
            opening.append(data)
        if line.startswith('OPEN_UNCLIP_HANDOFF '):
            data = dict(part.split('=', 1) for part in line.split()[1:])
            assert int(data['accepts']) == accepted == 3
            active = False
            handoff = True
        if line.startswith('ATTR_RADIUS '):
            data = {k: float(v) for k, v in (part.split('=', 1) for part in line.split()[1:])}
            data['opening_active'] = active
            if active:
                assert abs(data['raw_norm'] - data['norm']) <= 1e-8 * max(1, data['raw_norm'])
            if data['accept']:
                assert data['norm'] <= data['radius'] * (1 + 1e-8)
                accepted += 1
            radii.append(data)
    assert opening and 'OPEN_UNCLIP_CONFIG ' in output
    assert 'FRONTLOAD_' not in output
    assert 'MIXED_STORAGE fragments=fp32 arithmetic=fp64 state=fp64 acceptance=fp64' in output
    if accepted > 3:
        assert handoff
    return dict(opening_attempts=len(opening), opening_rows=opening,
                handoff_seen=handoff, accepted_radius_checks=True,
                opening_oversized_rejections=sum(row['opening_active'] and not row['accept'] and
                    row['norm'] > row['radius'] * (1 + 1e-8) for row in radii), radius_rows=radii)


def solver(scene, arm, rep, sanitizer=False):
    folder = P / 'results' / f'{scene}-{arm}-{rep}'
    folder.mkdir(parents=True, exist_ok=False)
    original = arm == 'original'
    manifest = json.loads((P / 'build_manifest.json').read_text())
    binary = Path('/tmp/prism-rl-actor/build/prism-tr') if original else P / 'build/prism-opening-unclip'
    expected = CHAMP['binary_sha256'] if original else manifest['binary_sha256']
    assert sha(binary) == expected
    if not original:
        assert manifest['local_headers'] == {name: sha(P / name) for name in manifest['local_headers']}
    problem = C / 'build/toy.txt' if scene == 'toy' else Path('/workspace/bal') / (scene + '.txt')
    flags = dict(CHAMP['flags'], OCA_MAX_SECONDS='60')
    if not original:
        flags.update(OCA_OPEN_UNCLIP='1' if arm == 'on' else '0', OCA_STCG_ATTEMPTS=str(folder / 'attempts.json'))
    cli = CHAMP['cli'].copy()
    if scene == 'toy':
        cli[cli.index('--max_iter') + 1] = '8'
    with tempfile.TemporaryDirectory(prefix='prism-unclip-check-', dir='/dev/shm') as temp:
        state = Path(temp) / 'endpoint.state'
        cmd = [str(binary), '--problem', str(problem), *cli,
               '--csv', str(folder / 'curve.csv'), '--state_out', str(state)]
        if sanitizer:
            cmd = ['/usr/local/cuda/bin/compute-sanitizer', '--tool', 'memcheck', '--error-exitcode', '91'] + cmd
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(('OCA_', 'CASPAR_', 'CERES_', 'COLMAP_MFREE', 'MF_DEBUG'))}
        env.update(flags)
        write(folder / 'manifest.json', dict(scene=scene, arm=arm, rep=rep, command=cmd, flags=flags,
              input_sha256=sha(problem), binary_sha256=expected,
              build_manifest=None if original else manifest, host=socket.gethostname(),
              scope='Correctness only, no speed verdict; endpoint preserved compressed'))
        rc, seconds = run(cmd, env, folder)
        output = (folder / 'stdout.log').read_text()
        err = (folder / 'stderr.log').read_text()
        match = re.search(r'RESULT .*?iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)', output)
        counts = re.search(r'MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)', output)
        if rc or not match or not counts:
            write(folder / 'result.json', dict(passed=False, returncode=rc, process_seconds=seconds))
            raise RuntimeError(output + err)
        dims, obs = observations(problem)
        cost = audit(state, dims, obs)
        rel = abs(cost - float(match[2])) / max(1, cost)
        initial = list(csv.DictReader(line for line in (folder / 'curve.csv').read_text().splitlines()
                                     if not line.startswith('#')))[0]
        answer = dict(scene=scene, arm=arm, rep=rep, returncode=rc, process_seconds=seconds,
                      native_seconds=float(match[3]), outers=int(match[1]), cost=cost,
                      score_init=float(initial['cost']), accepts=int(counts[1]), rejects=int(counts[2]),
                      matvecs=int(counts[3]), cpu_cost_relative_error=rel, state_sha256=sha(state),
                      sanitizer=sanitizer, passed=rel < 1e-8)
        with state.open('rb') as src, gzip.open(folder / 'endpoint.state.gz', 'wb', compresslevel=1) as dst:
            while block := src.read(1024 * 1024):
                dst.write(block)
        answer['compressed_state_sha256'] = sha(folder / 'endpoint.state.gz')
    if sanitizer:
        answer['sanitizer_zero_errors'] = 'ERROR SUMMARY: 0 errors' in output + err
        answer['passed'] &= answer['sanitizer_zero_errors']
    if not original:
        trace = json.loads((folder / 'attempts.json').read_text())
        answer['attempt_totals'] = trace['totals']
        answer['trace_counts_match'] = (trace['totals']['accepted'] == answer['accepts'] and
                                       trace['totals']['matvecs'] == answer['matvecs'])
        answer['passed'] &= answer['trace_counts_match']
    if arm == 'on':
        answer.update(check_opening(output))
    elif arm == 'off':
        assert 'OPEN_UNCLIP_' not in output
    write(folder / 'result.json', answer)
    assert answer['passed'], answer
    print('DONE', scene, arm, rep, 'cost', cost, 'outers', answer['outers'], flush=True)
    return answer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['toy', 'compatibility'])
    args = parser.parse_args()
    subprocess.run(['python3', str(F / 'build.py'), '--check-only'], check=True)
    if args.stage == 'toy':
        rows = [solver('toy', arm, 0, True) for arm in ('off', 'on')]
        write(P / 'results/toy-summary.json', rows)
        return
    rows = []
    for rep in range(3):
        for arm in (('original', 'off') if rep % 2 == 0 else ('off', 'original')):
            rows.append(solver('dubrovnik-88', arm, rep))
    original = [row['cost'] for row in rows if row['arm'] == 'original']
    derived = [row['cost'] for row in rows if row['arm'] == 'off']
    delta = 100 * (statistics.median(derived) / statistics.median(original) - 1)
    report = dict(rows=rows, median_cost_delta_percent=delta, passed=abs(delta) < .15,
                  scope='Source-off compatibility, N3; no timing or bit identity claim')
    write(P / 'results/compatibility-summary.json', report)
    assert report['passed']
    print('COMPATIBILITY', delta, flush=True)


if __name__ == '__main__':
    main()
