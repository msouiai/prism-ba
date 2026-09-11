import time
import numpy as np
from geometry import project, retract, dot
from reference_ba import Linearization
from collective import coarse_linearization, fixed_metric
from experiment import Work

def robust_value(s, obs, sigma=1.):
    r, q = project(s, obs, 6)
    if not np.isfinite(r).all() or not np.all(q[:, 2] < -1e-8): return float('inf')
    return float(.5*sigma*sigma*np.sum(np.log1p(np.sum(r*r, axis=1)/(sigma*sigma))))

def information_loss(s, obs, cg, pg, M, sigma, proposed):
    r, _, K, _, _ = coarse_linearization(s, obs, cg, pg)
    rr = np.sum(r*r, axis=1)
    w = np.repeat(1/(1+rr/sigma**2), 2); wn = np.repeat(1/(1+rr/proposed**2), 2)
    L = np.linalg.cholesky(M); Z = np.linalg.solve(L, K.T).T
    H = Z.T@(w[:, None]*Z); Hnext = Z.T@(wn[:, None]*Z)
    eigen, V = np.linalg.eigh(H)
    if eigen[-1] < 1e-12: return {'unobservable': True, 'min_information_ratio': None, 'eigenvalues': eigen.tolist()}
    ids = np.flatnonzero(eigen > max(1e-12, eigen[-1]*1e-10))[:3]
    U = V[:, ids]
    ratios = np.einsum('ij,ij->j', U, Hnext@U)/eigen[ids]
    return {'unobservable': False, 'min_information_ratio': float(np.min(ratios)), 'eigenvalues': eigen.tolist()}

def solve_t5(initial, obs, cg, pg, arm, target, cap=2., attempts=60):
    start = time.perf_counter(); work = Work(); s = initial.copy(); lam = .1
    scales = [32., 8., 2., 1.]; stage = 3 if arm == 'fixed' else 0
    stage_age = delays = accepted = rejects = 0; hit_time = None; trace = []; decisions = []
    M = work.call('metric_setup', fixed_metric, initial, cg, pg) if arm == 'information' else None
    for attempt in range(attempts):
        if time.perf_counter()-start >= cap: break
        if attempt >= 24: stage = 3
        if stage < 3 and stage_age >= 4:
            delay = False
            if arm == 'residual':
                value = work.call('residual_feature', lambda: float(np.percentile(np.linalg.norm(project(s, obs, 6)[0], axis=1), 95)))
                delay = value > 2*scales[stage+1]
                decisions.append({'attempt': attempt, 'residual_p95': value, 'requested_delay': bool(delay)})
            elif arm == 'information':
                result = work.call('information_feature', information_loss, s, obs, cg, pg, M, scales[stage], scales[stage+1])
                delay = not result['unobservable'] and result['min_information_ratio'] < .25
                decisions.append({'attempt': attempt, **result, 'requested_delay': bool(delay)})
            if not delay or stage_age >= 12:
                stage += 1; stage_age = 0
            else: delays += 1
        sigma = scales[stage]
        r, _ = work.call('projection', project, s, obs, 6)
        weights = 1/(1+np.sum(r*r, axis=1)/sigma**2)
        lin = work.call('linearization', Linearization, s, obs, weights)
        f = work.call('factor', lin.factor, lam)
        dc, dp = work.call('rhs_solve', f.solve)
        parent_cost = work.call('stage_cost', robust_value, s, obs, sigma)
        trial = retract(s, dc, dp)
        trial_cost = work.call('stage_cost', robust_value, trial, obs, sigma)
        jd = lin.jd(dc, dp)
        pred = -dot(lin.r*weights[:, None], jd)-.5*dot(jd*weights[:, None], jd)
        rho = (parent_cost-trial_cost)/pred if pred > 0 else -np.inf
        if np.isfinite(trial_cost) and pred > 0 and rho > .1:
            s = trial; accepted += 1
            lam = np.clip(lam*(.5 if rho > .75 else 2. if rho < .25 else 1.), 1e-8, 1e8)
        else: rejects += 1; lam = min(1e8, 4*lam)
        stage_age += 1
        F = work.call('final_objective', robust_value, s, obs)
        now = time.perf_counter()-start
        if stage == 3 and F <= target and hit_time is None: hit_time = now
        trace.append({'attempt': attempt, 'seconds': now, 'cost': F, 'sigma': sigma})
    elapsed = time.perf_counter()-start
    return s, {'cost': robust_value(s, obs), 'seconds': elapsed, 'target_seconds': hit_time, 'hit': hit_time is not None,
               'accepted': accepted, 'rejected_attempts': rejects, 'delays': delays, 'final_sigma': scales[stage],
               'counts': work.counts, 'work_seconds': work.seconds, 'trace': trace, 'decisions': decisions}
