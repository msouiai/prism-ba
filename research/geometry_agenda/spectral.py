"""Full-system OCA filter reference and RHS-seeded Lanczos pruning proxy."""
import time
import numpy as np
from geometry import retract, dot
from reference_ba import Linearization, valid_cost
from experiment import Work

GRID = [(m, k) for m in [.25, .5, 1., 2., 4.] for k in [0, 1, 3, 7]]

def response(h, lam, k):
    h = np.asarray(h); out = np.empty_like(h)
    zero = h == 0
    out[zero] = (k+1)/lam
    out[~zero] = -np.expm1(-(k+1)*np.log1p(h[~zero]/lam))/h[~zero]
    return out

def full_matrix(lin):
    nc, np_ = lin.nc, lin.np; n = 6*nc+3*np_
    H = np.zeros((n, n))
    for i in range(nc): H[i*6:i*6+6, i*6:i*6+6] = lin.B[i]
    for i in range(np_): H[6*nc+i*3:6*nc+i*3+3, 6*nc+i*3:6*nc+i*3+3] = lin.C[i]
    H[:6*nc, 6*nc:] = lin.E; H[6*nc:, :6*nc] = lin.E.T
    ids = np.delete(np.arange(6, n), 6*nc+2-6)
    M = np.r_[lin.Dc.ravel(), lin.Dp.ravel()][ids]
    b = -np.r_[lin.gc.ravel(), lin.gp.ravel()][ids]
    return H[np.ix_(ids, ids)], M, b, ids

def spectral_measure(lin, exact=False):
    H, M, b, _ = full_matrix(lin)
    root = np.sqrt(M); A = H/root[:, None]/root[None, :]; rhs = b/root
    if exact:
        values, V = np.linalg.eigh(A)
        return np.maximum(values, 0.), (V.T@rhs)**2
    norm = np.linalg.norm(rhs)
    if norm == 0: return np.array([0.]), np.array([0.])
    q = rhs/norm; Q = []; alpha = []; beta = []
    for step in range(min(12, len(rhs))):
        Q.append(q.copy()); z = A@q
        a = float(q@z); alpha.append(a)
        # Full reorthogonalization is charged. Small reference implementation.
        matrix = np.array(Q).T
        z -= matrix@(matrix.T@z)
        z -= matrix@(matrix.T@z)
        bnext = float(np.linalg.norm(z))
        if bnext < 1e-12 or step == min(12, len(rhs))-1: break
        beta.append(bnext); q = z/bnext
    T = np.diag(alpha)+np.diag(beta, 1)+np.diag(beta, -1)
    values, V = np.linalg.eigh(T)
    return np.maximum(values, 0.), norm*norm*V[0]**2

def representatives(nodes, weights, center, threshold):
    filters = np.array([response(nodes, center*m, k) for m, k in GRID])
    norms = np.sqrt(np.sum(weights*filters*filters, axis=1))
    distance = np.sqrt(np.sum(weights*(filters[:, None]-filters[None])**2, axis=2))/np.maximum(1e-300, np.maximum(norms[:, None], norms[None]))
    order = sorted(range(len(GRID)), key=lambda i: (GRID[i][1], abs(np.log(GRID[i][0])), GRID[i][0]))
    keep = []
    for i in order:
        if not keep or np.min(distance[i, keep]) > threshold: keep.append(i)
    return keep, distance

def candidates(lin, center, selected, work):
    selected = set(selected); out = {}
    for m in [.25, .5, 1., 2., 4.]:
        depths = [k for i, (mult, k) in enumerate(GRID) if i in selected and mult == m]
        if not depths: continue
        lam = center*m; factor = work.call('factor', lin.factor, lam)
        dc = np.zeros((lin.nc, 6)); dp = np.zeros((lin.np, 3))
        for k in range(max(depths)+1):
            dc, dp = work.call('rhs_solve', factor.solve, lin.gc-lam*lin.Dc*dc, lin.gp-lam*lin.Dp*dp)
            if k in depths:
                trial = retract(lin.state, dc, dp)
                cost = work.call('cost', valid_cost, trial, lin.obs)
                jd = lin.jd(dc, dp); pred = -dot(lin.r, jd)-.5*dot(jd, jd)
                F = .5*dot(lin.r, lin.r)
                eligible = bool(np.isfinite(cost) and pred > 0 and (F-cost)/pred > .1)
                out[GRID.index((m, k))] = {'cost': cost, 'state': trial, 'dc': dc.copy(), 'dp': dp.copy(),
                                           'eligible': eligible, 'lambda': lam}
    return out

def solve_t7(initial, obs, arm, target, threshold, cap=2.):
    start = time.perf_counter(); work = Work(); state = initial.copy(); F = valid_cost(state, obs)
    center = .1; accepted = rejected = 0; trace = [{'seconds': 0., 'cost': F}]; records = []
    for attempt in range(80):
        if F <= target or time.perf_counter()-start >= cap: break
        lin = work.call('linearization', Linearization, state, obs)
        if arm == 'full': selected = range(len(GRID))
        elif arm == 'manual5': selected = [i for i, (_, k) in enumerate(GRID) if k == 0]
        elif arm == 'manual4': selected = [i for i, (m, _) in enumerate(GRID) if m == 1]
        else:
            nodes, weights = work.call('spectral_feature', spectral_measure, lin)
            selected, _ = work.call('pruning', representatives, nodes, weights, center, threshold)
        options = candidates(lin, center, selected, work)
        good = [(i, v) for i, v in options.items() if v['eligible']]
        if good:
            winner, v = min(good, key=lambda item: item[1]['cost'])
            state, F = v['state'], v['cost']; center = max(1e-8, .5*v['lambda']); accepted += 1
            trace.append({'seconds': time.perf_counter()-start, 'cost': F, 'winner': winner})
        else: winner = None; rejected += 1; center = min(1e8, 4*center)
        records.append({'attempt': attempt, 'selected': list(selected), 'winner': winner,
                        'outcomes': {i: {'cost': v['cost'] if np.isfinite(v['cost']) else None, 'eligible': v['eligible']} for i, v in options.items()}})
    elapsed = time.perf_counter()-start
    return state, {'cost': F, 'hit': bool(F <= target), 'seconds': elapsed, 'target_seconds': elapsed if F <= target else None,
                   'accepted': accepted, 'rejected_attempts': rejected, 'trace': trace, 'menus': records,
                   'counts': work.counts, 'work_seconds': work.seconds}
