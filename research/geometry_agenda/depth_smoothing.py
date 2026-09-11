import time
import numpy as np
from geometry import project, retract, dot
from reference_ba import Linearization, valid_cost, synthetic
from experiment import Work

def parallax_case(seed, baseline):
    truth, initial, obs = synthetic(seed, 'depth')
    noise = -project(truth, obs, 6)[0]
    old_t = truth.t.copy(); truth.t *= baseline
    initial.t += truth.t-old_t
    blank = obs.copy(); blank[:, 2:] = 0
    obs[:, 2:] = project(truth, blank, 6)[0]+noise
    return truth, initial, obs

def quadrature(initial, obs, kind, fraction):
    lin = Linearization(initial, obs)
    depth = np.full(len(initial.X), np.inf)
    np.minimum.at(depth, lin.pi, np.abs(lin.q[:, 2]))
    radius = fraction*depth
    if kind == 'depth':
        _, V = np.linalg.eigh(lin.C)
        # Point0's gauge column is excluded in lin.C; use a fresh physical
        # point block for the direction so gauge fixing cannot choose it.
        _, _, _, jp, _, _ = project(initial, obs, 6, True)
        C = np.zeros_like(lin.C); np.add.at(C, lin.pi, np.einsum('nki,nkj->nij', jp, jp))
        _, V = np.linalg.eigh(C)
        direction = V[:, :, 0]*radius[:, None]
        return np.array([-direction, np.zeros_like(direction), direction]), np.array([.25, .5, .25])
    offsets = [np.zeros_like(initial.X)]
    for j in range(3):
        d = np.zeros_like(initial.X); d[:, j] = radius
        offsets += [-d, d]
    return np.array(offsets), np.array([.5]+[1/12]*6)

def smooth_evaluation(s, obs, offsets, weights, scale, jacobian=False):
    if not jacobian:
        value = 0.
        for off, w in zip(offsets, weights):
            shifted = s.copy(); shifted.X += scale*off
            F = valid_cost(shifted, obs)
            if not np.isfinite(F): return float('inf')
            value += w*F
        return value
    rs = []; qs = []; jcs = []; jps = []
    for off in offsets:
        shifted = s.copy(); shifted.X += scale*off
        r, q, jc, jp, _, _ = project(shifted, obs, 6, True)
        rs.append(r); qs.append(q); jcs.append(jc); jps.append(jp)
    combined = np.tile(obs, (len(offsets), 1))
    evals = (np.concatenate(rs), np.concatenate(qs), np.concatenate(jcs), np.concatenate(jps), None, None)
    return Linearization(s, combined, np.repeat(weights, len(obs)), evaluation=evals)

def solve_single(initial, obs, arm, target, cap=1.):
    start = time.perf_counter(); work = Work(); s = initial.copy(); lam = .1
    if arm == 'ordinary': offsets = weights = None
    else:
        kind, fraction = arm.split(':')
        offsets, weights = work.call('quadrature_setup', quadrature, initial, obs, kind, float(fraction))
    trace = []; accepted = rejected = invalid = 0; hit_time = None
    for attempt in range(48):
        if time.perf_counter()-start >= cap: break
        scale = 1. if attempt < 6 else .5 if attempt < 12 else 0.
        if attempt == 12: lam = .1
        smooth = arm != 'ordinary' and scale > 0
        if smooth:
            lin = work.call('linearization', smooth_evaluation, s, obs, offsets, weights, scale, True)
            F = work.call('stage_cost', smooth_evaluation, s, obs, offsets, weights, scale)
        else:
            lin = work.call('linearization', Linearization, s, obs)
            F = work.call('stage_cost', valid_cost, s, obs)
        factor = work.call('factor', lin.factor, lam)
        dc, dp = work.call('rhs_solve', factor.solve)
        trial = retract(s, dc, dp)
        Ft = work.call('stage_cost', smooth_evaluation, trial, obs, offsets, weights, scale) if smooth else work.call('stage_cost', valid_cost, trial, obs)
        invalid += not np.isfinite(Ft)
        jd = lin.jd(dc, dp)
        pred = -dot(lin.r*lin.weights[:, None], jd)-.5*dot(jd*lin.weights[:, None], jd)
        rho = (F-Ft)/pred if pred > 0 else -np.inf
        if np.isfinite(Ft) and pred > 0 and rho > .1:
            s = trial; accepted += 1
            lam = np.clip(lam*(.5 if rho > .75 else 2. if rho < .25 else 1.), 1e-8, 1e8)
        else: rejected += 1; lam = min(1e8, 4*lam)
        original = work.call('original_cost', valid_cost, s, obs)
        now = time.perf_counter()-start
        if attempt >= 12 and original <= target and hit_time is None: hit_time = now
        trace.append({'attempt': attempt, 'seconds': now, 'cost': original, 'radius_scale': scale if smooth else 0.})
    return s, {'cost': valid_cost(s, obs), 'seconds': time.perf_counter()-start, 'hit': hit_time is not None,
               'target_seconds': hit_time, 'accepted': accepted, 'rejected_attempts': rejected, 'invalid_trials': int(invalid),
               'counts': work.counts, 'work_seconds': work.seconds, 'trace': trace, 'terminal_attempts': max(0, len(trace)-12)}

def solve_t6(initial, obs, arm, target, seed):
    if arm != 'multistart': return solve_single(initial, obs, arm, target)
    start = time.perf_counter(); first, r1 = solve_single(initial, obs, 'ordinary', target, .5)
    alt = initial.copy(); alt.X *= np.exp(np.random.default_rng(seed+1901).uniform(-.2, .2, len(initial.X)))[:, None]
    alt.X[0, 2] = initial.X[0, 2]; offset = time.perf_counter()-start
    if np.isfinite(valid_cost(alt, obs)):
        second, r2 = solve_single(alt, obs, 'ordinary', target, min(.5, max(0., 1-offset)))
    else:
        second, r2 = first, {'cost': float('inf'), 'hit': False, 'seconds': 0., 'trace': [], 'invalid_initial': True}
    state, winner = (first, r1) if r1['cost'] <= r2['cost'] else (second, r2)
    hit = r1['target_seconds'] if r1['hit'] else offset+r2['target_seconds'] if r2['hit'] else None
    return state, {**winner, 'seconds': time.perf_counter()-start, 'hit': hit is not None, 'target_seconds': hit,
                   'branches': [r1, {**r2, 'cost': r2['cost'] if np.isfinite(r2['cost']) else None}],
                   'trace': r1['trace']+[{**r, 'seconds': r['seconds']+offset, 'cost': min(r1['cost'], r['cost'])} for r in r2['trace']]}
