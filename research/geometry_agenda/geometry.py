"""BAL local geometry for audited fixed states and tiny mechanism experiments."""
from dataclasses import dataclass
import pathlib
import struct
import numpy as np

def skew(v):
    out = np.zeros(v.shape[:-1]+(3, 3))
    out[..., 0, 1] = -v[..., 2]; out[..., 0, 2] = v[..., 1]
    out[..., 1, 0] = v[..., 2]; out[..., 1, 2] = -v[..., 0]
    out[..., 2, 0] = -v[..., 1]; out[..., 2, 1] = v[..., 0]
    return out

def exp_so3(w):
    theta = np.linalg.norm(w, axis=-1)
    K = skew(w)
    return np.eye(3)+np.sinc(theta/np.pi)[..., None, None]*K + (.5*np.sinc(theta/(2*np.pi))**2)[..., None, None]*(K@K)

def dot(a, b):
    return float(np.sum(a*b, dtype=np.longdouble))

@dataclass
class State:
    R: np.ndarray
    t: np.ndarray
    X: np.ndarray
    intr: np.ndarray  # nc x 3, f/k1/k2

    def copy(self):
        return State(*(v.copy() for v in [self.R, self.t, self.X, self.intr]))

def read_capture(stem):
    stem = pathlib.Path(stem)
    with stem.with_suffix('.state').open('rb') as f:
        assert f.read(8) == b'PRISMS01'
        nc, np_, no = struct.unpack('<QQQ', f.read(24))
        R = np.fromfile(f, '<f8', 9*nc).reshape(nc, 3, 3)
        t = np.fromfile(f, '<f8', 3*nc).reshape(nc, 3)
        X = np.fromfile(f, '<f8', 3*np_).reshape(np_, 3)
        intr = np.fromfile(f, '<f8', 3*nc).reshape(3, nc).T.copy()
        assert not f.read(1)
    d = np.fromfile(stem.with_suffix('.step'), '<f8')
    assert len(d) == 9*nc+3*np_
    assert np.all(intr[:, 2] == 0)
    return State(R, t, X, intr), d[:9*nc].reshape(nc, 9), d[9*nc:].reshape(np_, 3), no

def read_observations(path):
    with pathlib.Path(path).open() as f:
        dims = tuple(map(int, f.readline().split()))
        obs = np.loadtxt(f, max_rows=dims[2])
    return dims, obs

def retract(s, dc, dp, alpha=1.):
    intr = s.intr.copy()
    if dc.shape[1] == 9:
        intr += alpha*dc[:, 6:9]
    return State(exp_so3(alpha*dc[:, :3])@s.R, s.t+alpha*dc[:, 3:6], s.X+alpha*dp, intr)

def radial(xy, intr):
    rr = np.sum(xy*xy, axis=1)
    dist = 1+intr[:, 1]*rr+intr[:, 2]*rr*rr
    return xy*(intr[:, 0]*dist)[:, None]

def project(s, obs, cd=9, jacobian=False):
    ci = obs[:, 0].astype(int); pi = obs[:, 1].astype(int)
    RX = np.einsum('nij,nj->ni', s.R[ci], s.X[pi])
    q = RX+s.t[ci]
    with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
        xy = -q[:, :2]/q[:, 2, None]
        intr = s.intr[ci]
        r = radial(xy, intr)-obs[:, 2:4]
        if not jacobian:
            return r, q
        no = len(obs)
        P = np.zeros((no, 2, 3))
        P[:, 0, 0] = -1/q[:, 2]; P[:, 1, 1] = -1/q[:, 2]
        P[:, :, 2] = -xy/q[:, 2, None]
        rr = np.sum(xy*xy, axis=1)
        dist = 1+intr[:, 1]*rr+intr[:, 2]*rr*rr
        W = intr[:, 0, None, None]*(dist[:, None, None]*np.eye(2)
            +(2*intr[:, 1]+4*intr[:, 2]*rr)[:, None, None]*xy[:, :, None]*xy[:, None, :])
        Jq = W@P
        Jc = np.zeros((no, 2, cd))
        Jc[:, :, :3] = Jq@(-skew(RX))
        Jc[:, :, 3:6] = Jq
        if cd == 9:
            Jc[:, :, 6] = xy*dist[:, None]
            Jc[:, :, 7] = xy*(intr[:, 0]*rr)[:, None]
            # The registered experiments freeze k2, including this column.
            Jc[:, :, 8] = 0
        Jp = Jq@s.R[ci]
    return r, q, Jc, Jp, P, W

def diagnostics(s, dc, dp, obs):
    r, q, Jc, Jp, P, W = project(s, obs, dc.shape[1], True)
    trial = retract(s, dc, dp)
    rt, qt = project(trial, obs, dc.shape[1])
    ci = obs[:, 0].astype(int); pi = obs[:, 1].astype(int)
    Jd = np.einsum('nij,nj->ni', Jc, dc[ci])+np.einsum('nij,nj->ni', Jp, dp[pi])
    RX = q-s.t[ci]
    dq_lin = np.cross(dc[ci, :3], RX)+dc[ci, 3:6]+np.einsum('nij,nj->ni', s.R[ci], dp[pi])
    dq = qt-q
    F, Ft = .5*dot(r, r), .5*dot(rt, rt)
    e = rt-r-Jd
    pred = -dot(r, Jd)-.5*dot(Jd, Jd)
    jnorm = np.sqrt(dot(Jd, Jd)); enorm = np.sqrt(dot(e, e))
    epsilon = np.finfo(float).eps*max(1., np.sqrt(2*F))
    finite = bool(np.isfinite(rt).all() and np.isfinite(Jd).all() and np.all(q[:, 2] != 0))
    result = {'cost': F, 'trial_cost': Ft if np.isfinite(Ft) else None, 'prediction': pred if np.isfinite(pred) else None,
              'model_defect_numerator': enorm if np.isfinite(enorm) else None,
              'model_defect_denominator': jnorm if np.isfinite(jnorm) else None, 'model_defect_epsilon': epsilon,
              'model_defect': enorm/(jnorm+epsilon) if finite else None, 'finite': finite,
              'rho': (F-Ft)/pred if finite and pred > 0 else None,
              'failed_cost': not (np.isfinite(Ft) and Ft < F),
              'failed_strict_model': not (finite and pred > 0 and (F-Ft)/pred > .1),
              'parent_wrong_depths': int(np.count_nonzero(q[:, 2] >= 0)),
              'trial_wrong_depths': int(np.count_nonzero(qt[:, 2] >= 0)),
              'depth_sign_changes': int(np.count_nonzero(np.signbit(q[:, 2]) != np.signbit(qt[:, 2]))),
              'parent_zero_depths': int(np.count_nonzero(q[:, 2] == 0)),
              'trial_zero_depths': int(np.count_nonzero(qt[:, 2] == 0)),
              'min_parent_abs_depth': float(np.min(np.abs(q[:, 2]))),
              'min_trial_abs_depth': float(np.min(np.abs(qt[:, 2]))),
              'step_euclidean_norm': float(np.sqrt(dot(dc, dc)+dot(dp, dp)))}
    with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
        gamma = dq[:, 2]/q[:, 2]; gamma_lin = dq_lin[:, 2]/q[:, 2]
        for name, values in [('exact', gamma), ('prospective', gamma_lin)]:
            valid = values[np.isfinite(values)]
            result[name+'_undefined'] = int(len(values)-len(valid))
            result[name+'_signed_quantiles'] = np.percentile(valid, [0, 1, 5, 50, 95, 99, 100]).tolist() if len(valid) else None
            result[name+'_abs_quantiles'] = np.percentile(np.abs(valid), [50, 90, 95, 99, 100]).tolist() if len(valid) else None
        if finite and np.all(qt[:, 2] != 0):
            xy = -q[:, :2]/q[:, 2, None]; xyt = -qt[:, :2]/qt[:, 2, None]
            Pexact = np.einsum('nij,nj->ni', P, dq)
            persp = xyt-xy-Pexact
            coordinate = np.einsum('nij,nj->ni', P, dq-dq_lin)
            identity = xyt-xy-Pexact/(1+gamma[:, None])
            radial_error = radial(xyt, s.intr[ci])-radial(xy, s.intr[ci])-np.einsum('nij,nj->ni', W, xyt-xy)
            if dc.shape[1] == 9:
                intr_linear = np.einsum('nij,nj->ni', Jc[:, :, 6:9], dc[ci, 6:9])
            else:
                intr_linear = np.zeros_like(r)
            intr_error = radial(xyt, trial.intr[ci])-radial(xyt, s.intr[ci])-intr_linear
            terms = [np.einsum('nij,nj->ni', W, persp), np.einsum('nij,nj->ni', W, coordinate), radial_error, intr_error]
            result['identity_relative_error'] = float(np.linalg.norm(identity)/max(1., np.linalg.norm(xyt-xy)))
            result['decomposition_relative_error'] = float(np.linalg.norm(e-sum(terms))/max(1., np.linalg.norm(e)))
            for name, term in zip(['perspective', 'coordinate', 'radial', 'intrinsics'], terms):
                result[name+'_defect_norm'] = float(np.linalg.norm(term))
        # Full GN residual is not the numerical residual of the damped solve.
        def jt(v):
            gc = np.zeros((len(s.R), dc.shape[1])); gp = np.zeros_like(s.X)
            np.add.at(gc, ci, np.einsum('nij,ni->nj', Jc, v))
            np.add.at(gp, pi, np.einsum('nij,ni->nj', Jp, v))
            return np.r_[gc.ravel(), gp.ravel()]
        g, filter_residual = jt(r), jt(r+Jd)
        value = np.linalg.norm(filter_residual)/max(epsilon, np.linalg.norm(g))
        result['full_GN_residual_relative_raw_coordinates'] = float(value) if np.isfinite(value) else None
    return result
