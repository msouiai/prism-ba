"""Small FP64 BA reference with explicit gauge and reusable Schur factors.

This is a mechanism reference, not a replacement for the GPU incumbent.
"""
import pathlib
import sys
import time
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent/'build/python'))
from scipy.linalg import cho_factor, cho_solve
from geometry import State, exp_so3, skew, project, retract, dot

def accumulate(ci, pi, jc, jp, nc, np_, weights=None):
    if weights is not None:
        jc = jc*np.sqrt(weights)[:, None, None]
        jp = jp*np.sqrt(weights)[:, None, None]
    B = np.zeros((nc, 6, 6)); C = np.zeros((np_, 3, 3))
    E = np.zeros((nc, np_, 6, 3))
    np.add.at(B, ci, np.einsum('nki,nkj->nij', jc, jc))
    np.add.at(C, pi, np.einsum('nki,nkj->nij', jp, jp))
    np.add.at(E, (ci, pi), np.einsum('nki,nkj->nij', jc, jp))
    return B, C, E.transpose(0, 2, 1, 3).reshape(nc*6, np_*3)

class Linearization:
    def __init__(self, state, obs, weights=None, depth_penalty=0.):
        self.state = state
        self.obs = obs
        self.nc, self.np = len(state.R), len(state.X)
        self.ci = obs[:, 0].astype(int); self.pi = obs[:, 1].astype(int)
        self.r, self.q, self.jc, self.jp, _, _ = project(state, obs, 6, True)
        assert np.isfinite(self.r).all() and np.all(self.q[:, 2] < -1e-8)
        self.jc[self.ci == 0] = 0
        self.jp[self.pi == 0, :, 2] = 0
        self.weights = np.ones(len(obs)) if weights is None else np.asarray(weights)
        assert np.all(self.weights >= 0)
        self.B, self.C, self.E = accumulate(self.ci, self.pi, self.jc, self.jp, self.nc, self.np, self.weights)
        # Record the original GN operator separately from a temporary step penalty.
        self.base_B, self.base_C, self.base_E = self.B.copy(), self.C.copy(), self.E.copy()
        self.gc, self.gp = self.jt(self.r)
        if depth_penalty:
            RX = self.q-state.t[self.ci]
            ac = np.zeros((len(obs), 1, 6))
            ac[:, 0, :3] = -skew(RX)[:, 2, :]/self.q[:, 2, None]
            ac[:, 0, 5] = 1/self.q[:, 2]
            ap = state.R[self.ci, 2, :][:, None, :]/self.q[:, 2, None, None]
            ac[self.ci == 0] = 0; ap[self.pi == 0, :, 2] = 0
            db, dc, de = accumulate(self.ci, self.pi, ac, ap, self.nc, self.np)
            # beta is dimensionless; all rows/weights remain fixed in this solve.
            self.depth_mu = depth_penalty*(np.trace(self.B, axis1=1, axis2=2).sum()+np.trace(self.C, axis1=1, axis2=2).sum())/(np.trace(db, axis1=1, axis2=2).sum()+np.trace(dc, axis1=1, axis2=2).sum())
            self.B += self.depth_mu*db; self.C += self.depth_mu*dc; self.E += self.depth_mu*de
        else:
            self.depth_mu = 0.
        # Scalar LM and depth-penalty arms share the same original GN scaling.
        self.Dc = np.maximum(np.diagonal(self.base_B, axis1=1, axis2=2), 1e-3*np.trace(self.base_B, axis1=1, axis2=2)[:, None]/6)
        self.Dp = np.maximum(np.diagonal(self.base_C, axis1=1, axis2=2), 1e-3*np.trace(self.base_C, axis1=1, axis2=2)[:, None]/3)
        self.Dc = np.maximum(self.Dc, 1e-12); self.Dp = np.maximum(self.Dp, 1e-12)

    def jt(self, residual):
        gc = np.zeros((self.nc, 6)); gp = np.zeros((self.np, 3))
        v = residual*self.weights[:, None]
        np.add.at(gc, self.ci, np.einsum('nki,nk->ni', self.jc, v))
        np.add.at(gp, self.pi, np.einsum('nki,nk->ni', self.jp, v))
        return gc, gp

    def jd(self, dc, dp):
        return np.einsum('nki,ni->nk', self.jc, dc[self.ci])+np.einsum('nki,ni->nk', self.jp, dp[self.pi])

    def factor(self, lam, point_multiplier=1.):
        return Factors(self, lam, point_multiplier)

class Factors:
    def __init__(self, lin, lam, point_multiplier):
        self.lin = lin
        self.lam = lam
        self.point_multiplier = point_multiplier
        B, C = lin.B.copy(), lin.C.copy()
        B[:, np.arange(6), np.arange(6)] += lam*lin.Dc
        C[:, np.arange(3), np.arange(3)] += lam*point_multiplier*lin.Dp
        C[0, 2, :] = 0; C[0, :, 2] = 0; C[0, 2, 2] = 1
        self.C = C
        self.point_factor = np.linalg.cholesky(C)
        self.E = lin.E[6:]
        self.CinvEt = self.point_solve(self.E.T.reshape(lin.np, 3, -1))
        S = np.zeros(((lin.nc-1)*6, (lin.nc-1)*6))
        for c in range(lin.nc-1):
            S[6*c:6*c+6, 6*c:6*c+6] = B[c+1]
        S -= self.E@self.CinvEt.reshape(3*lin.np, -1)
        self.S = .5*(S+S.T)
        self.factor = cho_factor(self.S, lower=True, check_finite=True)

    def point_solve(self, rhs):
        L = self.point_factor
        y = np.zeros_like(rhs); x = np.zeros_like(rhs)
        for i in range(3):
            y[:, i] = (rhs[:, i]-np.sum(L[:, i, :i, None]*y[:, :i], axis=1))/L[:, i, i, None]
        for i in range(2, -1, -1):
            x[:, i] = (y[:, i]-np.sum(L[:, i+1:, i, None]*x[:, i+1:], axis=1))/L[:, i, i, None]
        return x

    def solve(self, gc=None, gp=None):
        # Changing only this RHS reuses the fixed point and Schur matrices.
        lin = self.lin
        gc = lin.gc if gc is None else gc
        gp = lin.gp if gp is None else gp
        gp = gp.copy(); gp[0, 2] = 0
        cp = self.point_solve(gp[..., None])[..., 0]
        rhs = -gc[1:].ravel()+self.E@cp.ravel()
        dc = np.zeros((lin.nc, 6))
        dc[1:] = cho_solve(self.factor, rhs).reshape(lin.nc-1, 6)
        dp = -self.point_solve((gp+(self.E.T@dc[1:].ravel()).reshape(lin.np, 3))[..., None])[..., 0]
        assert np.all(dc[0] == 0) and dp[0, 2] == 0
        return dc, dp

def synthetic(seed, mode='depth', nc=6, np_=80):
    rng = np.random.default_rng(seed)
    centers = np.column_stack([np.linspace(-1, 1, nc), rng.normal(0, .08, nc), np.zeros(nc)])
    X = rng.uniform([-1.3, -.8, -8], [1.3, .8, -3], (np_, 3))
    truth = State(np.tile(np.eye(3), (nc, 1, 1)), -centers, X, np.tile([500., 0., 0.], (nc, 1)))
    obs = np.array([[c, p, 0., 0.] for p in range(np_) for c in sorted(rng.choice(nc, size=min(4, nc), replace=False))])
    obs[:, 2:] = project(truth, obs, 6)[0]+rng.normal(0, .25, (len(obs), 2))
    s = truth.copy()
    if mode == 'depth':
        s.X *= np.exp(rng.normal(0, .7, np_))[:, None]
        rot_sigma = .025
    elif mode == 'rotation':
        s.X += rng.normal(0, .03, s.X.shape)
        rot_sigma = .2
    else:
        raise ValueError(mode)
    s.R = exp_so3(rng.normal(0, rot_sigma, (nc, 3)))@s.R
    s.t += rng.normal(0, .03, s.t.shape)
    s.R[0] = truth.R[0]; s.t[0] = truth.t[0]; s.X[0, 2] = truth.X[0, 2]
    assert np.all(project(s, obs, 6)[1][:, 2] < -1e-8)
    return truth, s, obs

def valid_cost(state, obs):
    r, q = project(state, obs, 6)
    if not np.isfinite(r).all() or not np.all(q[:, 2] < -1e-8):
        return float('inf')
    return .5*dot(r, r)
