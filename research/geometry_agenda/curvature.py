"""Analytic residual second derivative in the actual left-rotation BAL chart."""
import numpy as np
from geometry import project

def second_directional(s, obs, dc, dp):
    ci = obs[:, 0].astype(int); pi = obs[:, 1].astype(int)
    RX = np.einsum('nij,nj->ni', s.R[ci], s.X[pi])
    RdX = np.einsum('nij,nj->ni', s.R[ci], dp[pi])
    w = dc[ci, :3]
    q = RX+s.t[ci]
    qv = np.cross(w, RX)+RdX+dc[ci, 3:6]
    qvv = np.cross(w, np.cross(w, RX))+2*np.cross(w, RdX)
    z = q[:, 2, None]
    xy = -q[:, :2]/z
    x1 = -(qv[:, :2]+xy*qv[:, 2, None])/z
    x2 = -(qvv[:, :2]+xy*qvv[:, 2, None])/z-2*qv[:, 2, None]/z*x1
    f, k, k2 = s.intr[ci].T
    di = np.zeros((len(obs), 3)) if dc.shape[1] == 6 else dc[ci, 6:9]
    df, dk, dk2 = di.T
    rr = np.sum(xy*xy, axis=1)
    r1 = 2*np.sum(xy*x1, axis=1)
    r2 = 2*np.sum(x1*x1+xy*x2, axis=1)
    d = 1+k*rr+k2*rr*rr
    d1 = dk*rr+k*r1+dk2*rr*rr+2*k2*rr*r1
    d2 = 2*dk*r1+k*r2+4*dk2*rr*r1+2*k2*(r1*r1+rr*r2)
    return (f*d)[:, None]*x2+2*(df*d+f*d1)[:, None]*x1+(2*df*d1+f*d2)[:, None]*xy

def metric_norm(dc, dp, radius):
    return float(np.sqrt(np.sum(dc[:, :3]**2)+(np.sum(dc[:, 3:6]**2)+np.sum(dp**2))/radius**2))
