import time
import numpy as np
from geometry import project, retract, dot
from reference_ba import Linearization, valid_cost
from experiment import Work

def point_values(s, obs):
    r, q = project(s, obs, 6)
    pi = obs[:, 1].astype(int)
    out = np.bincount(pi, weights=.5*np.sum(r*r, axis=1), minlength=len(s.X))
    bad = np.bincount(pi, weights=(~np.isfinite(r).all(axis=1)) | (q[:, 2] >= -1e-8), minlength=len(s.X)) > 0
    out[bad] = np.inf
    return out

def polish(s, obs, steps=1, selected=None):
    state = s.copy(); pi = obs[:, 1].astype(int)
    selected = np.ones(len(s.X), dtype=bool) if selected is None else selected
    for _ in range(steps):
        r, q, _, jp, _, _ = project(state, obs, 6, True)
        if not np.isfinite(r).all() or not np.all(q[:, 2] < -1e-8): break
        jp[pi == 0, :, 2] = 0
        C = np.zeros((len(s.X), 3, 3)); g = np.zeros_like(s.X)
        np.add.at(C, pi, np.einsum('nki,nkj->nij', jp, jp))
        np.add.at(g, pi, np.einsum('nki,nk->ni', jp, r))
        diag = np.maximum(np.diagonal(C, axis1=1, axis2=2), 1e-3*np.trace(C, axis1=1, axis2=2)[:, None]/3)
        C[:, np.arange(3), np.arange(3)] += np.maximum(1e-12, 1e-4*diag)
        C[0, 2, :] = 0; C[0, :, 2] = 0; C[0, 2, 2] = 1; g[0, 2] = 0
        dp = np.zeros_like(g)
        dp[selected] = np.linalg.solve(C[selected], -g[selected, :, None])[..., 0]
        best = point_values(state, obs); chosen = state.X.copy()
        for alpha in [1., .5, .25]:
            candidate = state.copy(); candidate.X += alpha*dp
            cost = point_values(candidate, obs)
            good = cost < best
            chosen[good] = candidate.X[good]; best[good] = cost[good]
        state.X = chosen
    return state

def stationarity(s, obs):
    lin = Linearization(s, obs)
    return float(np.linalg.norm(lin.gp/np.sqrt(lin.Dp))/max(1., np.linalg.norm(lin.r)))

def solve_t3(initial, obs, arm, target, cap=2., max_attempts=80):
    start = time.perf_counter(); work = Work(); s = initial.copy()
    F = work.call('cost', valid_cost, s, obs); lam = .1
    accepts = rejects = changed = menus = 0; trace = [{'seconds': 0., 'cost': F}]; records = []
    for attempt in range(max_attempts):
        if F <= target or time.perf_counter()-start >= cap: break
        lin = work.call('linearization', Linearization, s, obs)
        raw = []; polished = []; candidates = []
        for scale in [.25, 1., 4.]:
            value = np.clip(lam*scale, 1e-8, 1e8)
            factor = work.call('factor', lin.factor, value)
            dc, dp = work.call('rhs_solve', factor.solve)
            trial = retract(s, dc, dp)
            cost = work.call('cost', valid_cost, trial, obs)
            raw.append(cost)
            if arm.startswith('pre') or arm == 'selective':
                if np.isfinite(cost):
                    selected = None
                    if arm == 'selective':
                        feature_start = time.perf_counter()
                        rt = project(trial, obs, 6)[0]; jd = lin.jd(dc, dp)
                        pi = obs[:, 1].astype(int)
                        numerator = np.bincount(pi, weights=np.sum((rt-lin.r-jd)**2, axis=1), minlength=len(s.X))
                        denominator = np.bincount(pi, weights=np.sum(jd*jd, axis=1), minlength=len(s.X))
                        score = numerator/(denominator+1e-12)
                        selected = score >= np.quantile(score, .75)
                        work.seconds['selection'] = work.seconds.get('selection', 0.)+time.perf_counter()-feature_start
                    trial = work.call('point_polish', polish, trial, obs, 3 if arm == 'pre3' else 1, selected)
                    cost = work.call('cost', valid_cost, trial, obs)
            polished.append(cost); candidates.append((cost, trial, value))
        winner = int(np.argmin(polished)); raw_winner = int(np.argmin(raw)); menus += 1
        changed += winner != raw_winner
        newF, trial, value = candidates[winner]
        accepted = bool(newF < F and np.isfinite(newF))
        if accepted:
            if arm.startswith('post'):
                trial = work.call('point_polish', polish, trial, obs, int(arm[-1]))
                newF = work.call('cost', valid_cost, trial, obs)
            s, F = trial, newF; accepts += 1; lam = max(1e-8, value*.5)
            trace.append({'seconds': time.perf_counter()-start, 'cost': F})
        else:
            rejects += 1; lam = min(1e8, lam*4)
        records.append({'attempt': attempt, 'raw_costs': [x if np.isfinite(x) else None for x in raw],
                        'ranked_costs': [x if np.isfinite(x) else None for x in polished], 'raw_winner': raw_winner,
                        'winner': winner, 'accepted': accepted,
                        'cost': F})
    elapsed = time.perf_counter()-start
    return s, {'cost': F, 'hit': bool(F <= target), 'seconds': elapsed, 'target_seconds': elapsed if F <= target else None,
               'accepted': accepts, 'rejected_attempts': rejects, 'changed_winners': int(changed), 'menus': menus,
               'counts': work.counts, 'work_seconds': work.seconds, 'trace': trace, 'menus_detail': records}
