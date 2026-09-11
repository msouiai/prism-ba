import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'; os.environ['OMP_NUM_THREADS'] = '1'
import hashlib
import json
import pathlib
import numpy as np
from paths import ROOT
from geometry import State, read_capture, read_observations, project
from reference_ba import valid_cost
from experiment import solve_t2

rows = []
for scene in ['ladybug-49', 'dubrovnik-88', 'venice-52']:
    full, *_ = read_capture(pathlib.Path('/tmp/prism-geometry-agenda')/f't1-{scene}-capture/captures/candidate-0')
    source = pathlib.Path('/workspace/bal')/(scene+'.txt')
    dims, obs = read_observations(source); source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    ci = obs[:, 0].astype(int); pi = obs[:, 1].astype(int)
    r, q = project(full, obs, 6)
    bad = np.bincount(pi, weights=(q[:, 2] >= -1e-8) | ~np.isfinite(r).all(axis=1), minlength=len(full.X)) > 0
    counts = np.bincount(pi, minlength=len(full.X))
    eligible = (counts >= 2) & ~bad
    for seed in [60, 61, 62]:
        rng = np.random.default_rng(seed); chosen = set()
        for c in range(len(full.R)):
            candidates = np.unique(pi[(ci == c) & eligible[pi]])
            assert len(candidates) >= 12
            chosen.update(rng.choice(candidates, 12, replace=False).tolist())
        remain = np.setdiff1d(np.flatnonzero(eligible), np.array(sorted(chosen), dtype=int))
        chosen.update(rng.choice(remain, max(0, min(1200-len(chosen), len(remain))), replace=False).tolist())
        pts = np.array(sorted(chosen), dtype=int)
        mask = np.isin(pi, pts); selected = obs[mask].copy()
        pmap = np.full(len(full.X), -1); pmap[pts] = np.arange(len(pts)); selected[:, 1] = pmap[pi[mask]]
        s = State(full.R.copy(), full.t.copy(), full.X[pts].copy(), full.intr.copy())
        F0 = valid_cost(s, selected); assert np.isfinite(F0)
        file = ROOT/'evidence'/f'{scene}-{seed}.npz'
        np.savez_compressed(file, R=s.R, t=s.t, X=s.X, intr=s.intr, observations=selected,
                            original_points=pts, original_cameras=np.arange(len(s.R)),
                            original_observations=np.flatnonzero(mask))
        _, reference = solve_t2(s, selected, 'lm', -1., cap=8., max_attempts=120)
        target = reference['cost']+1e-3*(F0-reference['cost'])
        rows.append({'scene': scene, 'seed': seed, 'path': str(file.relative_to(ROOT)),
                     'packed_sha256': hashlib.sha256(file.read_bytes()).hexdigest(), 'original_sha256': source_hash,
                     'original_dimensions': dims, 'cameras': len(s.R), 'points': len(s.X), 'observations': len(selected),
                     'invalid_original_observations': int(np.sum(q[:, 2] >= -1e-8)), 'excluded_invalid_points': int(bad.sum()),
                     'min_tracks_per_camera': int(np.bincount(selected[:, 0].astype(int)).min()),
                     'initial_cost': F0, 'reference': reference, 'target': target})
        print(scene, seed, 'reference', reference['cost'], 'target', target, flush=True)
(ROOT/'frozen_cases.json').write_text(json.dumps({'cases': rows}, indent=2, allow_nan=False)+'\n')
print('All inputs and targets frozen; no comparative arms have run.')
