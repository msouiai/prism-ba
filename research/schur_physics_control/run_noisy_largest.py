#!/usr/bin/env python3
"""Bounded paired initialization stress; no changes to the measured binary."""
import argparse
import csv
import datetime
import fcntl
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import tempfile
import time
import numpy as np
from noisy_scene import Scene, SOURCE, digest

ROOT = pathlib.Path(__file__).resolve().parent
OUT = pathlib.Path(os.environ.get('PRISM_NOISE_OUT', '/tmp/prism-schur-physics-noise'))
TARGET = 27318392.631312046
CAP = 12

def put(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')

def run(binary, cfg, input_path, case, rank, base):
    stem = OUT/f"px{case['requested_sample_median_px']:g}-seed{case['seed']}-r{rank}"
    flags = cfg['flags'] | {'OCA_COARSE_RANK': str(rank), 'OCA_MAX_SECONDS': str(CAP),
                            'OCA_TARGET_COST': str(TARGET)}
    log_path, csv_path, json_path = [pathlib.Path(str(stem)+ext) for ext in ['.log', '.csv', '.json']]
    execution_path = pathlib.Path(str(stem)+'.execution.json')
    if json_path.exists():
        return json.loads(json_path.read_text())
    cmd = [str(binary), '--problem', str(input_path), *cfg['cli'], '--csv', str(csv_path)]
    if not log_path.exists():
        start = time.monotonic()
        print('RUN', stem.name, flush=True)
        with log_path.open('w') as f:
            try:
                rc = subprocess.run(cmd, env=base | flags, stdout=f, stderr=subprocess.STDOUT, timeout=120).returncode
            except subprocess.TimeoutExpired:
                rc = 124
        execution = {'returncode': rc, 'process_seconds': time.monotonic()-start, 'command': cmd}
        put(execution_path, execution)
    elif execution_path.exists():
        execution = json.loads(execution_path.read_text())
    else:
        # One original run completed before an interleaved stderr line broke the
        # parser. Preserve it; do not invent a return code or repeat its timing.
        with csv_path.open() as f:
            cmd[2] = f.readline().split(' problem=', 1)[1].strip()
        execution = {'returncode': None, 'process_seconds': None, 'command': cmd,
                     'execution_metadata_lost_after_parse_error': True}
    rc = execution['returncode']
    raw_text = log_path.read_text()
    text = re.sub(r'\[R9\] wrote [^\n]*\n', '', raw_text)
    row = {'case': case, 'rank': rank, 'flags': flags, **execution, 'target': TARGET,
           'target_event': False, 'hit_within_budget': False, 'log': log_path.name, 'csv': csv_path.name}
    m = re.search(r'RESULT algo=\S+ iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)', text)
    if m:
        row.update(outers=int(m[1]), final_cost=float(m[2]), native_seconds=float(m[3]))
    m = re.search(r'TARGET reached outer=(\d+) seconds=(\S+) cost=(\S+) threshold=(\S+)', text)
    if m:
        row.update(target_event=True, target_outer=int(m[1]), target_seconds=float(m[2]), target_cost=float(m[3]),
                   hit_within_budget=rc == 0 and float(m[2]) <= CAP and float(m[3]) <= TARGET)
    m = re.search(r'MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)', text)
    if m:
        row.update(accepts=int(m[1]), rejects=int(m[2]), matvecs=int(m[3]))
    preparations = [dict(x.split('=', 1) for x in line.split()[1:] if '=' in x)
                    for line in text.splitlines() if line.startswith('COARSE_PREP ')]
    assert all({'active', 'prior_depth'} <= p.keys() for p in preparations)
    row['coarse_active'] = sum(int(x['active']) for x in preparations)
    row['max_prior_depth'] = max((int(x['prior_depth']) for x in preparations), default=None)
    row['coarse_preparations'] = preparations
    row['stop_messages'] = [line for line in text.splitlines() if 'BUDGET' in line or 'converged (' in line]
    if csv_path.exists():
        with csv_path.open() as f:
            trace = list(csv.DictReader(line for line in f if not line.startswith('#')))
        if trace:
            row['initial_native_cost'] = float(trace[0]['cost'])
            row['initial_cpu_relative_error'] = abs(row['initial_native_cost']/case['initial_cost']-1)
            # A sensitive initialization is not silently accepted as loader parity.
            row['initial_cost_verified'] = row['initial_cpu_relative_error'] < 1e-6
    put(json_path, row)
    print(json.dumps({k: row.get(k) for k in ['rank', 'hit_within_budget', 'target_seconds', 'final_cost',
                                               'native_seconds', 'outers', 'rejects', 'coarse_active', 'max_prior_depth',
                                               'initial_cost_verified']}), flush=True)
    return row

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--resume', action='store_true')
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    existing = (OUT/'manifest.json').exists()
    if existing and not args.resume:
        raise SystemExit('Output cohort already exists; choose a fresh PRISM_NOISE_OUT.')
    binary = ROOT/'build/prism-coarse'
    build = json.loads((ROOT/'build/solver-manifest.json').read_text())
    assert digest(binary) == build['binary_sha256']
    cfg = json.loads((ROOT.parent/'eta2_champion/champion.json').read_text())
    assert digest(SOURCE) == '76ef34416fdca524b1ec6755b62ab33cba15c8b5b830b5ff38369c8cd609d736'
    if not existing:
        shutil.copy2(ROOT/'NOISE_PROTOCOL.md', OUT/'PROTOCOL.md')
        put(OUT/'manifest.json', {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'python': platform.python_version(), 'numpy': np.__version__, 'binary_sha256': digest(binary),
            'generator_sha256': digest(ROOT/'noisy_scene.py'), 'runner_sha256': digest(__file__),
            'protocol_sha256': digest(ROOT/'NOISE_PROTOCOL.md'), 'input_sha256': digest(SOURCE),
            'flags': cfg['flags'], 'cli': cfg['cli'], 'seeds': [17, 29, 43], 'levels_px': [.25, 1.],
            'target': TARGET, 'native_cap': CAP, 'timing_repeats_per_input': 1})
    else:
        registered = json.loads((OUT/'manifest.json').read_text())
        assert registered['generator_sha256'] == digest(ROOT/'noisy_scene.py')
        assert registered['binary_sha256'] == digest(binary)
        assert registered['flags'] == cfg['flags'] and registered['cli'] == cfg['cli']
        assert registered['target'] == TARGET and registered['native_cap'] == CAP
        assert registered['seeds'] == [17, 29, 43] and registered['levels_px'] == [.25, 1.]
        assert registered['protocol_sha256'] == digest(ROOT/'NOISE_PROTOCOL.md')
        put(OUT/'resume.json', {'reason': 'Recover parser interruption from interleaved R9 stderr, without rerunning completed solves.',
                               'runner_sha256': digest(__file__), 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()})
    print('REGISTERED; loading scene', flush=True)
    scene = Scene()
    assert scene.obs_sha == '89212219a95d8748c068769d8642dbd802c6f59e64833aaece44078a81a81e49'
    print('LOADED', scene.dims, flush=True)
    if not (OUT/'zero_roundtrip.json').exists():
        c = scene.c0.copy()
        c[:, 3:6] = -np.einsum('nij,nj->ni', scene.R0, scene.centers)
        zero = scene.inspect(c, scene.x0)
        zero['relative_cost_change'] = abs(zero['initial_cost']/zero['clean_initial_cost']-1)
        put(OUT/'zero_roundtrip.json', zero)
        print('ZERO ROUNDTRIP', json.dumps(zero), flush=True)
    zero = json.loads((OUT/'zero_roundtrip.json').read_text())
    assert zero['relative_cost_change'] < 1e-7
    base = {k: v for k, v in os.environ.items() if not k.startswith(('OCA_', 'CASPAR_', 'COLMAP_MFREE', 'MF_DEBUG'))}
    rows = json.loads((OUT/'runs.json').read_text()) if (OUT/'runs.json').exists() else []
    cases = json.loads((OUT/'cases.json').read_text()) if (OUT/'cases.json').exists() else []
    with tempfile.TemporaryDirectory(prefix='prism-noise-', dir='/dev/shm') as tmp:
        input_path = pathlib.Path(tmp)/'input.txt'
        with open('/tmp/prism_gpu.lock', 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            for si, seed in enumerate([17, 29, 43]):
                for li, pixels in enumerate([.25, 1.]):
                    done = [r for r in rows if r['case']['seed'] == seed and r['case']['requested_sample_median_px'] == pixels]
                    if len(done) == 2:
                        continue
                    c, x, case = scene.perturb(seed, pixels)
                    case.update(scene.inspect(c, x))
                    print('GEOMETRY', json.dumps(case), flush=True)
                    case['input_sha256'] = scene.write(input_path, c, x)
                    del c, x
                    case['readback_verified'] = True
                    old = next((c for c in cases if c['seed'] == seed and c['requested_sample_median_px'] == pixels), None)
                    if old:
                        assert case == old
                    else:
                        cases.append(case)
                    put(OUT/'cases.json', cases)
                    for rank in ([0, 16] if (si+li)%2 == 0 else [16, 0]):
                        if any(r['rank'] == rank for r in done):
                            continue
                        rows.append(run(binary, cfg, input_path, case, rank, base))
                        put(OUT/'runs.json', rows)
    put(OUT/'completion.json', {'complete': len(rows) == 12, 'runs': len(rows),
        'all_returncodes_zero': all(r['returncode'] == 0 for r in rows),
        'all_terminal_results_and_initial_costs_verified': all('final_cost' in r and r.get('initial_cost_verified') for r in rows),
        'native_seconds': sum(r.get('native_seconds', 0) for r in rows)})
    print('DONE', flush=True)

if __name__ == '__main__':
    main()
