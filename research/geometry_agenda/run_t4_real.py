import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'; os.environ['OMP_NUM_THREADS'] = '1'
import json
import pathlib
import time
import numpy as np
from geometry import State, read_capture, read_observations, project
from collective import solve_t4
from partition import automatic_partition
from reference_ba import valid_cost
from experiment import solve_t2

ROOT = pathlib.Path(__file__).resolve().parent
def sampled(scene):
    path = pathlib.Path('/tmp/prism-geometry-agenda')/f't1-{scene}-capture/captures/candidate-0'
    full, _, _, _ = read_capture(path)
    _, obs = read_observations(pathlib.Path('/workspace/bal')/(scene+'.txt'))
    ci = obs[:, 0].astype(int); pi = obs[:, 1].astype(int)
    visibility = [set(pi[ci == c]) for c in range(len(full.R))]
    cams = [0]; seen = visibility[0].copy()
    while len(cams) < min(24, len(full.R)):
        available = [c for c in range(len(full.R)) if c not in cams]
        best = max(available, key=lambda c: len(visibility[c]&seen))
        cams.append(best); seen |= visibility[best]
    mask = np.isin(ci, cams)
    count = np.bincount(pi[mask], minlength=len(full.X))
    residual, q = project(full, obs[mask], 6)
    bad = np.bincount(pi[mask], weights=(q[:, 2] >= -1e-8) | (~np.isfinite(residual).all(axis=1)), minlength=len(full.X)) > 0
    eligible = np.flatnonzero((count >= 3) & ~bad)
    pts = np.sort(np.random.default_rng(51).choice(eligible, min(300, len(eligible)), replace=False))
    mask &= np.isin(pi, pts)
    chosen = obs[mask].copy()
    cams = np.array([c for c in cams if np.any(ci[mask] == c)], dtype=int)
    cmap = np.full(len(full.R), -1); pmap = np.full(len(full.X), -1)
    cmap[cams] = np.arange(len(cams)); pmap[pts] = np.arange(len(pts))
    chosen[:, 0] = cmap[ci[mask]]; chosen[:, 1] = pmap[pi[mask]]
    state = State(full.R[cams].copy(), full.t[cams].copy(), full.X[pts].copy(), full.intr[cams].copy())
    assert np.isfinite(valid_cost(state, chosen))
    data = ROOT/'evidence'/f't4-sampled-{scene}.npz'
    np.savez_compressed(data, R=state.R, t=state.t, X=state.X, intr=state.intr, observations=chosen,
                        original_cameras=cams, original_points=pts, original_observations=np.flatnonzero(mask))
    return state, chosen, {'cameras': len(cams), 'points': len(pts), 'observations': len(chosen),
                           'invalid_points_excluded': int(np.sum((count >= 3) & bad)), 'input': str(data.relative_to(ROOT))}

cases = []; references = []
for scene in ['ladybug-49', 'dubrovnik-88', 'venice-52']:
    state, obs, info = sampled(scene)
    _, ref = solve_t2(state, obs, 'lm', 0., cap=3., max_attempts=120)
    F0 = valid_cost(state, obs); target = ref['cost']+1e-3*(F0-ref['cost'])
    references.append({'scene': scene, 'initial_cost': F0, 'reference': ref, 'target': target, **info})
    cases.append((scene, state, obs, target))
(ROOT/'t4_real_targets.json').write_text(json.dumps(references, indent=2, allow_nan=False)+'\n')
print('targets frozen before comparisons', flush=True)
rows = []; arms = ['fine', 'linear', 'nonlinear']
for scene, initial, obs, target in cases:
    for rep in range(3):
        for arm in arms[rep:]+arms[:rep]:
            start = time.perf_counter(); cg = pg = None
            if arm != 'fine': cg, pg = automatic_partition(initial, obs, confidence=True)
            setup = time.perf_counter()-start
            final, result = solve_t4(initial, obs, cg, pg, arm, target, cap=max(0., 2-setup))
            result['seconds'] += setup
            result['trace'] = [{**r, 'seconds': r['seconds']+setup} for r in result['trace']]
            rows.append({'scene': scene, 'rep': rep, 'arm': arm, 'target': target, 'setup_seconds': setup,
                         **result, 'invalid_final_depths': int(np.count_nonzero(project(final, obs, 6)[1][:, 2] >= -1e-8))})
    print(scene, 'done', flush=True)
(ROOT/'t4_real.json').write_text(json.dumps({'rows': rows}, indent=2, allow_nan=False)+'\n')
summary = {}
for scene, _, _, _ in cases:
    summary[scene] = {}
    base = [r for r in rows if r['scene'] == scene and r['arm'] == 'fine']
    for arm in arms:
        r = [r for r in rows if r['scene'] == scene and r['arm'] == arm]
        summary[scene][arm] = {'hits': sum(x['hit'] for x in r), 'cost': float(np.median([x['cost'] for x in r])),
                               'seconds': float(np.median([x['seconds'] for x in r])),
                               'speedup_vs_fine': float(np.median([x['seconds'] for x in base])/np.median([x['seconds'] for x in r])) if all(x['hit'] for x in r+base) else None}
(ROOT/'t4_real_summary.json').write_text(json.dumps(summary, indent=2)+'\n'); print(json.dumps(summary, indent=2))
