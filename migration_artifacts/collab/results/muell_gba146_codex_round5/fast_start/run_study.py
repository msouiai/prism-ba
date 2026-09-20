#!/usr/bin/env python3
"""Pre-registered bounded fast-start study for the guarded Prism candidate."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time

ROOT = Path('/workspace/prism-fast-start')
BIN = ROOT / 'build' / 'prism-tr'
DATA_ROOT = Path('/workspace/bal')
REPO = Path('/workspace/prism-ba')
SELECTED = Path('/workspace/prism-model-followup/selected_candidate.json')
REPEATS = 3
MAX_ITER = 600
TIMEOUT = 180
SCENES = {
    'muell-gba146': {'target': 1946488.746262194, 'cap': 90.0},
    'ladybug-1723': {'target': 452676.06625000003, 'cap': 8.0},
    'final-1936': {'target': 5125687.352261469, 'cap': 8.0},
}
ARMS = {
    'guarded-control': {},
    # Fixed before measurements: Caspar’s fixed 20 PCG steps motivated depth
    # 16; three first outers bracket the measured coarse-error lead.  The
    # original ladder resumes afterwards, independent of endpoint quality.
    'fast-start-16x3': {'OCA_CKPT_OPEN': '16', 'OCA_CKPT_OPEN_OUTERS': '3'},
}
PHASE_LEVELS = (20.0, 10.0, 5.0, 3.0, 1.0, 0.0)

sys.path.insert(0, str(REPO / 'bench'))
from cached_benchmark_input import load_input  # noqa: E402
from audit_prism_state import audit  # noqa: E402


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def base_environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items()
            if not key.startswith(('OCA_', 'CASPAR_', 'COLMAP_MFREE_', 'MF_DEBUG'))}


def parse(log: str) -> dict[str, object]:
    result = re.search(r'^RESULT .*?iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)$', log, re.M)
    counts = re.search(r'^  MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+) negcurv=(\d+) cand_evals=(\d+)', log, re.M)
    target = re.search(r'^TARGET reached outer=(\d+) seconds=(\S+) cost=(\S+) threshold=(\S+)$', log, re.M)
    if not result or not counts:
        raise RuntimeError('missing RESULT or MFCG record')
    profiles = [
        {'assembly': float(a), 'pointfactor_rhs': float(b), 'krylov': float(c), 'candidates': float(d)}
        for a, b, c, d in re.findall(
            r'^  \[PROFILE\] assembly=(\S+)s pointfactor\+rhs=(\S+)s krylov=(\S+)s candidates=(\S+)s$', log, re.M)
    ]
    return {
        'outers': int(result.group(1)), 'native_cost': float(result.group(2)),
        'seconds': float(result.group(3)), 'accepts': int(counts.group(1)),
        'rejects': int(counts.group(2)), 'matvecs': int(counts.group(3)),
        'negcurv': int(counts.group(4)), 'candidate_evals': int(counts.group(5)),
        'crossing_outer': int(target.group(1)) if target else None,
        'crossing_seconds': float(target.group(2)) if target else None,
        'crossing_cost': float(target.group(3)) if target else None,
        'profiles': profiles,
    }


def trace_crossings(csv_path: Path, target: float) -> dict[str, float | None]:
    with csv_path.open() as file:
        rows = list(csv.DictReader(line for line in file if not line.startswith('#')))
    if not rows:
        raise RuntimeError('empty trace')
    costs = [float(row['cost']) for row in rows]
    if any(next_cost > cost * (1.0 + 1e-10) for cost, next_cost in zip(costs, costs[1:])):
        raise RuntimeError('accepted cost increased')
    result: dict[str, float | None] = {}
    for level in PHASE_LEVELS:
        threshold = target * (1.0 + level / 100.0)
        result[str(level)] = next((float(row['wall_s']) for row in rows if float(row['cost']) <= threshold), None)
    return result


def run_one(*, scene: str, arm: str, rep: int, phase: str, data_hash: str,
            dims: tuple[int, int, int], observations, initial_cost: float) -> dict[str, object]:
    name = f'{phase}-{scene}-{arm}-{rep}'
    stem = ROOT / ('profile' if phase == 'profile' else 'runs') / name
    result_path = stem.with_suffix('.result.json')
    if result_path.exists():
        saved = json.loads(result_path.read_text())
        if saved['binary_sha256'] != sha(BIN) or saved['data_sha256'] != data_hash:
            raise RuntimeError(f'provenance mismatch in {name}')
        return saved
    leftovers = [stem.with_suffix(suffix) for suffix in ('.log', '.stderr', '.csv', '.state', '.manifest.json', '.process.json')]
    if any(path.exists() for path in leftovers):
        raise RuntimeError(f'incomplete artifact retained for {name}')
    specification = SCENES[scene]
    flags = json.loads(SELECTED.read_text())['flags'] | ARMS[arm]
    environment = base_environment()
    environment.update({str(key): str(value) for key, value in flags.items()})
    environment.update({
        'OCA_TARGET_COST': repr(specification['target']),
        'OCA_MAX_SECONDS': repr(specification['cap']),
    })
    if phase == 'profile':
        environment['OCA_PROFILE'] = '1'
    command = [
        'flock', '/tmp/prism_gpu.lock', 'timeout', str(TIMEOUT), str(BIN),
        '--problem', str(DATA_ROOT / f'{scene}.txt'), '--algo', 'mfree_shifted_cg',
        '--dof9', '--zero_k2', '--lam0', '0.1', '--max_iter', str(MAX_ITER),
        '--csv', str(stem.with_suffix('.csv')), '--state_out', str(stem.with_suffix('.state')),
        '--mf-json', str(stem.with_suffix('.jsonl')),
    ]
    manifest = {
        'name': name, 'scene': scene, 'arm': arm, 'rep': rep, 'phase': phase,
        'command': command, 'flags': {key: environment[key] for key in sorted(environment) if key.startswith('OCA_')},
        'binary': str(BIN), 'binary_sha256': sha(BIN),
        'data_sha256': data_hash, 'dimensions': dims, 'initial_cpu_fp64_cost': initial_cost,
        'target': specification['target'], 'native_cap_seconds': specification['cap'],
        'audit': 'independent CPU FP64 SIMPLE_RADIAL cost on original observations',
    }
    write_json(stem.with_suffix('.manifest.json'), manifest)
    print('RUN', name, flush=True)
    start = time.monotonic()
    with stem.with_suffix('.log').open('x') as stdout, stem.with_suffix('.stderr').open('x') as stderr:
        process = subprocess.run(command, env=environment, stdout=stdout, stderr=stderr)
    wall = time.monotonic() - start
    write_json(stem.with_suffix('.process.json'), {'returncode': process.returncode, 'wall_seconds': wall})
    row: dict[str, object] = {
        'name': name, 'scene': scene, 'arm': arm, 'rep': rep, 'phase': phase,
        'status': 'ok', 'binary_sha256': sha(BIN), 'data_sha256': data_hash,
        'initial_cpu_fp64_cost': initial_cost, 'target': specification['target'],
        'process_returncode': process.returncode, 'process_wall_seconds': wall,
    }
    if process.returncode:
        row.update(status='process_failure', hit=False,
                   stderr_tail=stem.with_suffix('.stderr').read_text()[-4000:])
    else:
        try:
            row.update(parse(stem.with_suffix('.log').read_text()))
            row['phase_crossing_seconds'] = trace_crossings(stem.with_suffix('.csv'), specification['target'])
            endpoint = audit(stem.with_suffix('.state'), dims, observations)
            row['audit_cpu_fp64_cost'] = endpoint
            row['audit_error'] = abs(endpoint - float(row['native_cost'])) / max(1.0, abs(endpoint))
            if float(row['audit_error']) > 1e-7:
                raise RuntimeError(f"native/audit mismatch {row['audit_error']}")
            row['hit'] = bool(row['crossing_seconds'] is not None and endpoint <= specification['target'])
        except Exception as error:
            row.update(status='audit_or_parse_failure', hit=False, error=repr(error))
    write_json(result_path, row)
    print('DONE', name, row['status'], 'hit', row.get('hit'), 'cross', row.get('crossing_seconds'),
          'cost', row.get('audit_cpu_fp64_cost'), flush=True)
    return row


def median_range(values: list[float]) -> dict[str, float]:
    return {'median': statistics.median(values), 'min': min(values), 'max': max(values)}


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {'scenes': {}}
    measured = [row for row in rows if row['phase'] == 'measurement']
    for scene in SCENES:
        output['scenes'][scene] = {}
        for arm in ARMS:
            group = [row for row in measured if row['scene'] == scene and row['arm'] == arm]
            valid = [row for row in group if row['status'] == 'ok']
            hits = [row for row in valid if row.get('hit')]
            cell: dict[str, object] = {'runs': len(group), 'valid': len(valid), 'hits': len(hits), 'phase_seconds': {}}
            for key in ('audit_cpu_fp64_cost', 'crossing_seconds', 'seconds', 'outers', 'matvecs', 'candidate_evals', 'rejects'):
                values = [float(row[key]) for row in valid if key in row and row[key] is not None]
                if values:
                    cell[key] = median_range(values)
            for level in PHASE_LEVELS:
                values = [float(row['phase_crossing_seconds'][str(level)]) for row in valid
                          if row.get('phase_crossing_seconds', {}).get(str(level)) is not None]
                if len(values) == REPEATS:
                    cell['phase_seconds'][str(level)] = median_range(values)
            output['scenes'][scene][arm] = cell
    return output


def write_report(rows: list[dict[str, object]], summary: dict[str, object]) -> None:
    lines = [
        '# Fixed-window fast-start study', '',
        'The candidate caps the Krylov ladder at 16 only for outer indices 0–2, then restores the frozen guarded solver.',
        'The switch does not inspect a target or endpoint quality. All runs use original-observation FP64 endpoint audits.', '',
        '| scene | arm | target hits | target seconds, median [min,max] | matvecs, median | final audited cost, median |',
        '|---|---|---:|---:|---:|---:|',
    ]
    for scene, arms in summary['scenes'].items():
        for arm, cell in arms.items():
            def interval(key: str, digits: int) -> str:
                if key not in cell:
                    return '—'
                item = cell[key]
                return f"{item['median']:.{digits}f} [{item['min']:.{digits}f}, {item['max']:.{digits}f}]"
            lines.append(f"| {scene} | {arm} | {cell['hits']}/{REPEATS} | {interval('crossing_seconds', 3)} | {interval('matvecs', 0)} | {interval('audit_cpu_fp64_cost', 3)} |")
    lines.extend(['', 'Phase-crossing ladders and raw profile records are in `summary.json`, `results.json`, `runs/`, and `profile/`.'])
    (ROOT / 'RESULTS.md').write_text('\n'.join(lines) + '\n')


def main() -> None:
    if not BIN.is_file():
        raise SystemExit(f'missing binary: {BIN}')
    for directory in (ROOT / 'runs', ROOT / 'profile'):
        directory.mkdir(exist_ok=True)
    selected = json.loads(SELECTED.read_text())
    if selected['binary_sha256'] != sha(Path(selected['binary'])):
        raise RuntimeError('frozen selected candidate provenance mismatch')
    cache = {}
    for scene in SCENES:
        data = DATA_ROOT / f'{scene}.txt'
        cache[scene] = load_input(data, ROOT / 'cpu_cache')
    protocol = {
        'source_candidate': selected,
        'binary': str(BIN), 'binary_sha256': sha(BIN), 'source_sha256': sha(ROOT / 'build' / 'source.cu'),
        'scenes': SCENES, 'arms': ARMS, 'repeats': REPEATS, 'max_iter': MAX_ITER, 'timeout_seconds': TIMEOUT,
        'phase_levels_percent_above_target': PHASE_LEVELS,
        'rule': 'The only treatment is OCA_CKPT_OPEN=16 plus OCA_CKPT_OPEN_OUTERS=3. The latter restores ordinary full-depth guarded CG after outer index 2; no quality target participates in switching.',
        'audit': 'independent CPU FP64 SIMPLE_RADIAL cost on original observation set',
        'input': {scene: {'sha256': item[0], 'dimensions': item[1][0], 'initial_cpu_fp64_cost': item[2]} for scene, item in cache.items()},
    }
    protocol_path = ROOT / 'protocol.json'
    if protocol_path.exists() and json.loads(protocol_path.read_text()) != protocol:
        raise RuntimeError('existing protocol differs')
    write_json(protocol_path, protocol)

    rows: list[dict[str, object]] = []
    # Diagnostic only: synchronization from OCA_PROFILE changes timing and is
    # excluded from the N=3 measurements.
    for arm in ARMS:
        data_hash, (dims, observations), initial = cache['muell-gba146']
        rows.append(run_one(scene='muell-gba146', arm=arm, rep=1, phase='profile', data_hash=data_hash,
                            dims=dims, observations=observations, initial_cost=initial))
        write_json(ROOT / 'results.json', rows)
    for rep in range(1, REPEATS + 1):
        scene_order = list(SCENES) if rep % 2 else list(reversed(SCENES))
        for scene in scene_order:
            arm_order = list(ARMS) if (rep + list(SCENES).index(scene)) % 2 else list(reversed(ARMS))
            data_hash, (dims, observations), initial = cache[scene]
            for arm in arm_order:
                rows.append(run_one(scene=scene, arm=arm, rep=rep, phase='measurement', data_hash=data_hash,
                                    dims=dims, observations=observations, initial_cost=initial))
                write_json(ROOT / 'results.json', rows)
                write_json(ROOT / 'summary.json', summarize(rows))
    summary = summarize(rows)
    write_json(ROOT / 'results.json', rows)
    write_json(ROOT / 'summary.json', summary)
    write_json(ROOT / 'endpoint_state_sha256.json', {
        row['name']: sha((ROOT / ('profile' if row['phase'] == 'profile' else 'runs')) / f"{row['name']}.state")
        for row in rows if ((ROOT / ('profile' if row['phase'] == 'profile' else 'runs')) / f"{row['name']}.state").exists()
    })
    write_report(rows, summary)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
