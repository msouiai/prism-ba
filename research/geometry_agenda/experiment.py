"""Bounded CPU mechanism experiments; no GPU or production speed claims."""
import time
import numpy as np
from geometry import project, retract, dot
from reference_ba import Linearization, valid_cost
from curvature import second_directional, metric_norm

def alignment_error(s, truth):
    # Exactly one global similarity, shared by every camera and point.
    A, B = s.X, truth.X
    am, bm = A.mean(axis=0), B.mean(axis=0)
    U, singular, Vt = np.linalg.svd((A-am).T@(B-bm))
    flip = np.ones(3); flip[-1] = np.linalg.det(U@Vt)
    Q = U@np.diag(flip)@Vt
    scale = float(np.sum(singular*flip)/np.sum((A-am)**2))
    radius = np.sqrt(np.mean(np.sum((B-bm)**2, axis=1)))
    C = -np.einsum('nji,nj->ni', s.R, s.t)
    Ct = -np.einsum('nji,nj->ni', truth.R, truth.t)
    aligned = scale*(A-am)@Q+bm
    ca = scale*(C-am)@Q+bm
    ra = s.R@Q
    angles = np.arccos(np.clip((np.trace(ra@truth.R.transpose(0, 2, 1), axis1=1, axis2=2)-1)/2, -1, 1))
    return {'point_nrmse': float(np.sqrt(np.mean(np.sum((aligned-B)**2, axis=1)))/radius),
            'camera_nrmse': float(np.sqrt(np.mean(np.sum((ca-Ct)**2, axis=1)))/radius),
            'rotation_median_deg': float(np.median(angles)*180/np.pi), 'global_scale': scale}

class Work:
    def __init__(self):
        self.counts = {}; self.seconds = {}
    def call(self, name, fn, *args, **kwargs):
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            self.counts[name] = self.counts.get(name, 0)+1
            self.seconds[name] = self.seconds.get(name, 0.)+time.perf_counter()-start

def solve_t2(initial, obs, arm, target, cap=2., max_attempts=80):
    work = Work(); start = time.perf_counter(); state = initial.copy()
    F = work.call('cost', valid_cost, state, obs)
    radius = float(np.sqrt(np.mean(np.sum((initial.X-initial.X.mean(axis=0))**2, axis=1))))
    lam = .1; lin = None; accepts = rejects = 0; records = []; trace = [{'seconds': 0., 'cost': F}]
    for attempt in range(max_attempts):
        if F <= target or time.perf_counter()-start >= cap: break
        if lin is None: lin = work.call('linearization', Linearization, state, obs)
        factors = work.call('factor', lin.factor, lam)
        v = work.call('rhs_solve', factors.solve)
        candidates = []
        def evaluate(dc, dp, kind, used_lam=lam):
            trial = retract(state, dc, dp)
            cost = work.call('cost', valid_cost, trial, obs)
            jd = lin.jd(dc, dp)
            prediction = -dot(lin.r, jd)-.5*dot(jd, jd)
            rho = (F-cost)/prediction if prediction > 0 else -np.inf
            accepted = np.isfinite(cost) and prediction > 0 and rho > .1
            record = {'attempt': attempt, 'kind': kind, 'lambda': used_lam,
                      'cost': cost if np.isfinite(cost) else None, 'parent_cost': F,
                      'prediction': prediction, 'rho': rho if np.isfinite(rho) else None,
                      'eligible': bool(accepted)}
            records.append(record)
            if accepted: candidates.append((cost, trial, rho, used_lam, kind))
            return trial, jd
        full, jv = evaluate(*v, 'lm')
        action = arm
        if arm == 'hybrid':
            tr = work.call('defect_feature', project, full, obs, 6)[0]
            defect = np.linalg.norm(tr-lin.r-jv)/(np.linalg.norm(jv)+np.finfo(float).eps*max(1., np.linalg.norm(lin.r)))
            action = 'geo' if not np.isfinite(defect) or defect > .25 else 'oca'
        if action == 'geo':
            rvv = work.call('second_derivative', second_directional, state, obs, *v)
            ga = work.call('curvature_rhs', lin.jt, rvv)
            a = work.call('rhs_solve', factors.solve, *ga)
            ratio = metric_norm(*a, radius)/(metric_norm(*v, radius)+np.finfo(float).eps)
            for t in [1., .5]:
                if t*ratio <= .75:
                    evaluate(t*v[0]+.5*t*t*a[0], t*v[1]+.5*t*t*a[1], 'geo'+str(t))
                else:
                    records.append({'attempt': attempt, 'kind': 'geo'+str(t), 'skipped_ratio': ratio, 'eligible': False})
        elif action == 'oca':
            u = work.call('rhs_solve', factors.solve, lin.gc-lam*lin.Dc*v[0], lin.gp-lam*lin.Dp*v[1])
            evaluate(*u, 'oca1')
        elif action == 'lambda':
            alternative = max(1e-8, lam/3)
            f2 = work.call('factor', lin.factor, alternative)
            evaluate(*work.call('rhs_solve', f2.solve), 'lambda', alternative)
        if candidates:
            F, state, rho, lam, kind = min(candidates, key=lambda c: c[0])
            accepts += 1; lin = None
            lam = min(1e8, max(1e-8, lam*(.5 if rho > .75 else 2. if rho < .25 else 1.)))
            trace.append({'seconds': time.perf_counter()-start, 'cost': F, 'kind': kind})
        else:
            rejects += 1; lam = min(1e8, lam*4.)
    elapsed = time.perf_counter()-start
    return state, {'hit': bool(F <= target), 'seconds': elapsed, 'target_seconds': elapsed if F <= target else None,
                   'cost': F, 'accepted': accepts, 'rejected_attempts': rejects,
                   'cap_hit': bool(F > target and (elapsed >= cap or accepts+rejects == max_attempts)),
                   'counts': work.counts, 'work_seconds': work.seconds, 'trace': trace, 'candidates': records}
