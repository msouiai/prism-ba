"""Exact finite cluster correction, evaluating only changing observations."""
import time
import numpy as np
from paths import ROOT
from geometry import project, dot
from collective import transform, coarse_linearization, fixed_metric, generalized_spectrum
from reference_ba import valid_cost

def masks(obs, cg, pg):
    return cg[obs[:, 0].astype(int)] != pg[obs[:, 1].astype(int)]

def selection_features(state, obs, cg, pg):
    bridge = masks(obs, cg, pg)
    r, _ = project(state, obs, 6)
    energy = np.sum(r*r, axis=1)
    cameras = np.bincount(cg, minlength=3); points = np.bincount(pg, minlength=3)
    fraction = float(np.mean(bridge)); share = float(energy[bridge].sum()/max(1e-300, energy.sum()))
    selected = fraction <= .25 and share >= .25 and cameras.min() >= 3 and points.min() >= 20
    return {'bridge_fraction': fraction, 'bridge_energy_share': share,
            'camera_sizes': cameras.tolist(), 'point_sizes': points.tolist(), 'selected': bool(selected)}

def solve_bridge(initial, obs, cg, pg, steps=8, target=-1., deadline=None):
    start = time.perf_counter(); state = initial.copy()
    bridge = masks(obs, cg, pg); reduced = obs[bridge]
    r, q = project(initial, obs, 6)
    assert np.isfinite(r).all() and np.all(q[:, 2] < -1e-8)
    Fint = .5*dot(r[~bridge], r[~bridge]); F0 = F = .5*dot(r, r)
    M = fixed_metric(initial, cg, pg); lam = 1e-3; trace = []; records = []
    ncalls = 1; nlinear = 0
    for iteration in range(steps):
        if F <= target or (deadline is not None and time.perf_counter() >= deadline): break
        if not len(reduced):
            records.append({'iteration': iteration, 'unobservable': True}); break
        rr, _, K, _, _ = coarse_linearization(state, reduced, cg, pg); nlinear += 1
        eig = generalized_spectrum(K, M)
        if np.linalg.norm(K) < 1e-8:
            records.append({'iteration': iteration, 'unobservable': True}); break
        H = K.T@K; g = K.T@rr.ravel()
        D = np.maximum(np.diag(H), max(1e-12, np.trace(H)/len(H)*1e-3))
        u = np.linalg.solve(H+lam*np.diag(D), -g)
        options = []
        for alpha in [1., .5, .25]:
            scaled = alpha*u
            if not np.isfinite(scaled).all() or np.max(np.abs(scaled[6::7])) > np.log(1e6):
                records.append({'iteration': iteration, 'alpha': alpha, 'invalid_scale': True}); continue
            trial = transform(state, cg, pg, scaled)
            changing_cost = valid_cost(trial, reduced); ncalls += 1
            cost = Fint+changing_cost
            records.append({'iteration': iteration, 'alpha': alpha, 'parent_cost': F,
                            'cost': cost if np.isfinite(cost) else None, 'eigenvalues': eig.tolist()})
            if cost < F: options.append((cost, trial))
        if options:
            F, state = min(options, key=lambda x: x[0]); lam = max(1e-8, lam*.5)
            trace.append({'seconds': time.perf_counter()-start, 'cost': F, 'kind': 'coarse-bridge'})
        else: lam = min(1e8, 4*lam)
    full = valid_cost(state, obs); ncalls += 1
    agreement = abs(full-F)/max(1., abs(full)) if np.isfinite(full) else None
    fallback = not (np.isfinite(full) and full <= F0 and agreement <= 1e-10)
    if fallback:
        state = initial.copy(); full = F0; trace = []
    else:
        trace.append({'seconds': time.perf_counter()-start, 'cost': full, 'kind': 'full-verification'})
    return state, {'cost': full, 'seconds': time.perf_counter()-start, 'trace': trace, 'candidates': records,
                   'bridge_observations': int(bridge.sum()), 'internal_observations': int((~bridge).sum()),
                   'internal_cost': Fint, 'full_cost_relative_disagreement': agreement,
                   'verification_fallback': fallback, 'linearizations': nlinear, 'cost_evaluations': ncalls}
