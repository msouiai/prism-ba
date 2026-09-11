"""Finite similarity and its exact tangent on unique camera/point clusters."""
import time
import numpy as np
from geometry import State, exp_so3, skew, project, retract, dot
from reference_ba import valid_cost
from experiment import solve_t2

def transform(s, cam_group, point_group, u):
    out = s.copy()
    for group in range(1, len(u)//7+1):
        z = u[(group-1)*7:group*7]
        Q = exp_so3(z[:3]); scale = np.exp(z[6]); shift = z[3:6]
        cm = cam_group == group; pm = point_group == group
        C = -np.einsum('nji,nj->ni', s.R[cm], s.t[cm])
        out.X[pm] = scale*s.X[pm]@Q.T+shift
        Cnew = scale*C@Q.T+shift
        out.R[cm] = s.R[cm]@Q.T
        out.t[cm] = -np.einsum('nij,nj->ni', out.R[cm], Cnew)
    return out

def basis(s, cam_group, point_group):
    rank = int(max(cam_group.max(), point_group.max()))*7
    bc = np.zeros((len(s.R), 6, rank)); bp = np.zeros((len(s.X), 3, rank))
    for group in range(1, rank//7+1):
        j = (group-1)*7; cm = cam_group == group; pm = point_group == group
        bc[cm, :3, j:j+3] = -s.R[cm]
        bc[cm, 3:6, j+3:j+6] = -s.R[cm]
        bc[cm, 3:6, j+6] = s.t[cm]
        bp[pm, :, j:j+3] = -skew(s.X[pm])
        bp[pm, :, j+3:j+6] = np.eye(3)
        bp[pm, :, j+6] = s.X[pm]
    return bc, bp

def coarse_linearization(s, obs, cam_group, point_group):
    r, q, jc, jp, _, _ = project(s, obs, 6, True)
    bc, bp = basis(s, cam_group, point_group)
    ci = obs[:, 0].astype(int); pi = obs[:, 1].astype(int)
    K = (jc@bc[ci]+jp@bp[pi]).reshape(len(obs)*2, -1)
    return r, q, K, bc, bp

def fixed_metric(s, cam_group, point_group):
    bc, bp = basis(s, cam_group, point_group)
    radius = np.sqrt(np.mean(np.sum((s.X-s.X.mean(axis=0))**2, axis=1)))
    B = np.concatenate([bc[:, :3].reshape(-1, bc.shape[-1]),
                        bc[:, 3:].reshape(-1, bc.shape[-1])/radius,
                        bp.reshape(-1, bp.shape[-1])/radius])
    return B.T@B

def generalized_spectrum(K, M):
    L = np.linalg.cholesky(M)
    W = np.linalg.solve(L, K.T).T
    return np.linalg.eigvalsh(W.T@W)

def clustered(seed, bridges=4, cameras=4, points=60, corrupt='none'):
    rng = np.random.default_rng(seed)
    cg = np.repeat(np.arange(3), cameras); pg = np.repeat(np.arange(3), points)
    centers = np.vstack([np.column_stack([np.linspace(-.8, .8, cameras)+g*2,
                        rng.uniform(-.4, .4, cameras), rng.uniform(-.1, .1, cameras)]) for g in range(3)])
    X = np.vstack([rng.uniform([-1+g*2, -.8, -8], [1+g*2, .8, -4], (points, 3)) for g in range(3)])
    truth = State(np.tile(np.eye(3), (len(cg), 1, 1)), -centers, X, np.tile([500., 0., 0.], (len(cg), 1)))
    entries = [[c, p, 0., 0.] for p in range(len(pg)) for c in np.flatnonzero(cg == pg[p])]
    for g in range(2):
        for owner, viewer in [(g, g+1), (g+1, g)]:
            for p in rng.choice(np.flatnonzero(pg == owner), size=min(bridges, points), replace=False):
                for c in rng.choice(np.flatnonzero(cg == viewer), size=2, replace=False): entries.append([c, p, 0., 0.])
    obs = np.array(entries)
    obs[:, 2:] = project(truth, obs, 6)[0]+rng.normal(0, .15, (len(obs), 2))
    bridge = cg[obs[:, 0].astype(int)] != pg[obs[:, 1].astype(int)]
    false = np.zeros(len(obs), dtype=bool)
    if corrupt != 'none':
        ids = np.flatnonzero(bridge)
        if corrupt == 'mixed': ids = ids[::2]
        elif corrupt != 'all': raise ValueError(corrupt)
        false[ids] = True
        obs[ids, 2:] += rng.uniform(-80, 80, (len(ids), 2))
    initial = truth.copy()
    initial.X += rng.normal(0, .003, initial.X.shape)
    initial.R = exp_so3(rng.normal(0, .001, (len(cg), 3)))@initial.R
    initial.t += rng.normal(0, .003, initial.t.shape)
    initial.R[0] = truth.R[0]; initial.t[0] = truth.t[0]; initial.X[0, 2] = truth.X[0, 2]
    u = rng.uniform(-1, 1, (2, 7))*np.array([.15]*3+[.4]*3+[.2])
    initial = transform(initial, cg, pg, u.ravel())
    assert np.isfinite(valid_cost(initial, obs))
    return truth, initial, obs, cg, pg, bridge, false

def coarse_solve(initial, obs, cg, pg, nonlinear=True, steps=8, target=-1., deadline=None):
    start = time.perf_counter(); s = initial.copy(); F = valid_cost(s, obs)
    lam = 1e-3; trace = []; records = []; M = fixed_metric(initial, cg, pg)
    for iteration in range(steps):
        if F <= target or (deadline is not None and time.perf_counter() >= deadline): break
        r, q, K, bc, bp = coarse_linearization(s, obs, cg, pg)
        eig = generalized_spectrum(K, M)
        if np.linalg.norm(K) < 1e-8:
            records.append({'iteration': iteration, 'unobservable': True, 'eigenvalues': eig.tolist()}); break
        H = K.T@K; g = K.T@r.ravel()
        D = np.maximum(np.diag(H), max(1e-12, np.trace(H)/len(H)*1e-3))
        u = np.linalg.solve(H+lam*np.diag(D), -g)
        options = []
        for alpha in [1., .5, .25]:
            scaled = alpha*u
            if nonlinear: trial = transform(s, cg, pg, scaled)
            else: trial = retract(s, (bc@scaled).reshape(len(s.R), 6), (bp@scaled).reshape(len(s.X), 3))
            cost = valid_cost(trial, obs)
            records.append({'iteration': iteration, 'alpha': alpha, 'cost': cost if np.isfinite(cost) else None,
                            'parent_cost': F, 'lambda': lam, 'eigenvalues': eig.tolist()})
            if cost < F: options.append((cost, trial))
        if options:
            F, s = min(options, key=lambda v: v[0]); lam = max(1e-8, lam*.5)
            trace.append({'seconds': time.perf_counter()-start, 'cost': F, 'kind': 'coarse'})
        else: lam = min(1e8, 4*lam)
    return s, {'seconds': time.perf_counter()-start, 'trace': trace, 'candidates': records, 'cost': F}

def solve_t4(initial, obs, cg, pg, arm, target, cap=2.):
    start = time.perf_counter(); trace = [{'seconds': 0., 'cost': valid_cost(initial, obs)}]
    s = initial.copy(); coarse = None
    if arm != 'fine':
        s, coarse = coarse_solve(s, obs, cg, pg, nonlinear=arm == 'nonlinear', target=target, deadline=start+cap)
        trace += coarse['trace']
    offset = time.perf_counter()-start
    final, fine = solve_t2(s, obs, 'lm', target, cap=max(0, cap-offset))
    trace += [{**row, 'seconds': row['seconds']+offset} for row in fine['trace'][1:]]
    elapsed = time.perf_counter()-start
    return final, {'hit': fine['hit'], 'cost': fine['cost'], 'seconds': elapsed,
                   'coarse_seconds': coarse['seconds'] if coarse else 0., 'coarse': coarse, 'fine': fine, 'trace': trace}
