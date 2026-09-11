"""Immutable action replay and small cost-sensitive computation scheduler."""
import time
import numpy as np
from geometry import project, retract, dot
from reference_ba import Linearization, valid_cost
from experiment import Work
from curvature import second_directional, metric_norm
from point_relaxation import polish
from partition import automatic_partition
from collective import coarse_solve

ACTIONS = ['fresh', 'oca', 'lambda', 'geo', 'point', 'coarse']
FEATURES = ['defect', 'depth_risk_p90', 'rho', 'base_eligible',
            'top10_energy', 'point_gradient_share', 'point_condition', 'log_rms']

def prepare(state, obs, lam, work):
    lin = work.call('linearization', Linearization, state, obs)
    F = .5*dot(lin.r, lin.r)
    factor = work.call('factor', lin.factor, lam)
    v = work.call('rhs_solve', factor.solve)
    trial = retract(state, *v)
    r, q = work.call('cost', project, trial, obs, 6)
    valid = np.isfinite(r).all() and np.all(q[:, 2] < -1e-8)
    cost = .5*dot(r, r) if valid else np.inf
    jd = lin.jd(*v); pred = -dot(lin.r, jd)-.5*dot(jd, jd)
    rho = (F-cost)/pred if pred > 0 else -np.inf
    base = {'state': trial, 'cost': cost, 'eligible': bool(valid and pred > 0 and rho > .1),
            'rho': rho, 'lambda': lam, 'kind': 'fresh'}
    return {'lin': lin, 'factor': factor, 'v': v, 'trial_r': r, 'trial_q': q,
            'jd': jd, 'F': F, 'base': base, 'lambda': lam}

def features(cache):
    lin = cache['lin']; jd = cache['jd']
    defect = np.linalg.norm(cache['trial_r']-lin.r-jd)/max(1e-12, np.linalg.norm(jd))
    risk = np.quantile(np.abs((cache['trial_q'][:, 2]-lin.q[:, 2])/lin.q[:, 2]), .9)
    energy = np.sum(lin.r*lin.r, axis=1)
    n = max(1, int(np.ceil(len(energy)*.1)))
    top = np.sum(np.partition(energy, len(energy)-n)[-n:])/max(1e-12, np.sum(energy))
    cg = np.sum(lin.gc**2/lin.Dc); pg = np.sum(lin.gp**2/lin.Dp)
    # Physical point information; point zero is excluded because of its gauge row.
    eigen = np.linalg.eigvalsh(lin.base_C[1:])
    condition = np.median(np.maximum(eigen[:, 0], 0)/np.maximum(eigen[:, -1], 1e-12))
    values = np.array([defect, risk, cache['base']['rho'], float(cache['base']['eligible']),
                       top, pg/max(1e-12, cg+pg), condition,
                       np.log1p(np.sqrt(np.mean(energy)))])
    return np.clip(np.nan_to_num(values, nan=1e6, posinf=1e6, neginf=-1e6), -1e6, 1e6)

def rule(x):
    if x[4] > .8 and x[7] > np.log(2.) and x[1] < .1: return 'coarse'
    if not x[3] and x[0] > .25: return 'geo'
    if x[3] and x[5] > .8: return 'point'
    if x[2] > .75: return 'oca'
    return 'fresh'

def predict(tree, x):
    while 'action' not in tree:
        tree = tree['left'] if x[tree['feature']] <= tree['threshold'] else tree['right']
    return tree['action']

def fit_tree(X, utility, depth=2):
    """Maximize mean normalized local utility, not noisy winner accuracy."""
    sums = utility.sum(axis=0); action = int(np.argmax(sums))
    result = {'action': ACTIONS[action], 'samples': len(X)}
    best = float(sums[action]); choice = None
    if depth == 0 or len(X) < 10: return result
    for feature in range(X.shape[1]):
        values = np.unique(X[:, feature])
        thresholds = (values[1:]+values[:-1])/2
        for threshold in thresholds:
            mask = X[:, feature] <= threshold
            if mask.sum() < 5 or (~mask).sum() < 5: continue
            score = float(utility[mask].sum(axis=0).max()+utility[~mask].sum(axis=0).max())
            if score > best+1e-10:
                best = score; choice = (feature, float(threshold), mask)
    if choice is None: return result
    feature, threshold, mask = choice
    return {'feature': feature, 'feature_name': FEATURES[feature], 'threshold': threshold,
            'left': fit_tree(X[mask], utility[mask], depth-1),
            'right': fit_tree(X[~mask], utility[~mask], depth-1)}

def perform(cache, action, work, target=-1., deadline=None):
    lin = cache['lin']; state = lin.state; F = cache['F']; lam = cache['lambda']
    candidates = [cache['base']]; details = []
    def evaluate(trial, kind, dc=None, dp=None, used_lam=lam):
        cost = work.call('cost', valid_cost, trial, lin.obs)
        rho = 1.
        eligible = bool(np.isfinite(cost) and cost < F)
        if dc is not None:
            jd = lin.jd(dc, dp); pred = -dot(lin.r, jd)-.5*dot(jd, jd)
            rho = (F-cost)/pred if pred > 0 else -np.inf
            eligible &= bool(pred > 0 and rho > .1)
        candidates.append({'state': trial, 'cost': cost, 'eligible': eligible,
                           'rho': rho, 'lambda': used_lam, 'kind': kind})
    v = cache['v']
    if action == 'oca':
        u = work.call('rhs_solve', cache['factor'].solve,
                      lin.gc-lam*lin.Dc*v[0], lin.gp-lam*lin.Dp*v[1])
        evaluate(retract(state, *u), action, *u)
    elif action == 'lambda':
        new_lam = max(1e-8, lam/3)
        factor = work.call('factor', lin.factor, new_lam)
        u = work.call('rhs_solve', factor.solve)
        evaluate(retract(state, *u), action, *u, used_lam=new_lam)
    elif action == 'geo':
        rvv = work.call('second_derivative', second_directional, state, lin.obs, *v)
        ga = work.call('curvature_rhs', lin.jt, rvv)
        a = work.call('rhs_solve', cache['factor'].solve, *ga)
        radius = float(np.sqrt(np.mean(np.sum((state.X-state.X.mean(axis=0))**2, axis=1))))
        ratio = metric_norm(*a, radius)/max(1e-12, metric_norm(*v, radius))
        for alpha in [1., .5]:
            if alpha*ratio <= .75:
                dc = alpha*v[0]+.5*alpha*alpha*a[0]; dp = alpha*v[1]+.5*alpha*alpha*a[1]
                evaluate(retract(state, dc, dp), action, dc, dp)
    elif action == 'point' and np.isfinite(cache['base']['cost']):
        trial = work.call('point_polish', polish, cache['base']['state'], lin.obs, 1)
        evaluate(trial, action)
    elif action == 'coarse':
        try:
            cg, pg = work.call('partition', automatic_partition, state, lin.obs, confidence=True)
            trial, info = work.call('coarse', coarse_solve, state, lin.obs, cg, pg,
                                    target=target, deadline=deadline)
            details = info['candidates']
            evaluate(trial, action)
        except np.linalg.LinAlgError as error:
            # A degenerate automatic coarse space is an action failure, not
            # permission to alter the metric or discard this parent from data.
            details = [{'numerical_failure': str(error)}]
    elif action not in ['fresh', 'point']:
        raise ValueError(action)
    good = [v for v in candidates if v['eligible']]
    winner = min(good, key=lambda v: v['cost']) if good else None
    outcomes = [{k: (float(v[k]) if np.isfinite(v[k]) else None) for k in ['cost', 'rho', 'lambda']}
                | {'kind': v['kind'], 'eligible': v['eligible']} for v in candidates]
    return winner, {'outcomes': outcomes, 'coarse_candidates': details}

def solve_t8(initial, obs, arm, target, tree=None, cap=2., max_attempts=80):
    work = Work(); start = time.perf_counter(); state = initial.copy()
    F = valid_cost(state, obs); lam = .1; accepted = rejected = 0
    trace = [{'seconds': 0., 'cost': F}]; decisions = []
    for attempt in range(max_attempts):
        if F <= target or time.perf_counter()-start >= cap: break
        cache = prepare(state, obs, lam, work)
        x = None
        if arm in ['rule', 'tree']:
            x = work.call('features', features, cache)
            action = work.call('inference', rule if arm == 'rule' else lambda x: predict(tree, x), x)
        else: action = arm
        winner, detail = perform(cache, action, work, target, deadline=start+cap)
        if winner is not None:
            state = winner['state']; F = winner['cost']; rho = winner['rho']; accepted += 1
            lam = min(1e8, max(1e-8, winner['lambda']*(.5 if rho > .75 else 2. if rho < .25 else 1.)))
            trace.append({'seconds': time.perf_counter()-start, 'cost': F, 'kind': winner['kind']})
        else:
            rejected += 1; lam = min(1e8, lam*4.)
        decisions.append({'attempt': attempt, 'action': action, 'features': x.tolist() if x is not None else None,
                          'winner': winner['kind'] if winner else None, **detail})
    elapsed = time.perf_counter()-start
    return state, {'cost': F, 'hit': bool(F <= target), 'seconds': elapsed,
                   'target_seconds': elapsed if F <= target else None, 'accepted': accepted,
                   'rejected_attempts': rejected, 'cap_hit': bool(F > target),
                   'trace': trace, 'decisions': decisions, 'counts': work.counts,
                   'work_seconds': work.seconds}
