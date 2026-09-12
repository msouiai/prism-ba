"""Independent vectorized FP64 observation reference; CPU research only."""
import numpy as np

STAGES = (0., .25, .5, .75, .9, 1.)


def projection(y, intrinsics, initial_depth, stage):
    y, intrinsics = np.asarray(y), np.asarray(intrinsics)
    d = y[..., 2] if stage == 1 else (np.asarray(initial_depth) if stage == 0 else
                                    stage*y[..., 2]+(1-stage)*initial_depth)
    with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
        q = -y[..., :2]/d[..., None]
        r2 = np.sum(q*q, axis=-1)
        f, k1, k2 = np.moveaxis(intrinsics, -1, 0)
        h = 1+k1*r2+k2*r2*r2
        pix = (f*h)[..., None]*q
        a = f[..., None, None]*(h[..., None, None]*np.eye(2) +
             (2*(k1+2*k2*r2))[..., None, None]*q[..., :, None]*q[..., None, :])
        dq = np.zeros(q.shape[:-1]+(2, 3), dtype=np.float64)
        dq[..., 0, 0] = dq[..., 1, 1] = -1/d
        dq[..., :, 2] = -stage*q/d[..., None]
        ji = q[..., :, None]*np.stack((h, f*r2, f*r2*r2), axis=-1)[..., None, :]
    return pix, a@dq, ji


def residual_jacobian(r, t, x, intrinsics, observed, initial_depth, stage):
    q = np.einsum('...ij,...j->...i', r, x)
    pix, jy, ji = projection(q+t, intrinsics, initial_depth, stage)
    skew = np.zeros(q.shape[:-1]+(3, 3), dtype=np.float64)
    skew[..., 0, 1], skew[..., 0, 2] = -q[..., 2], q[..., 1]
    skew[..., 1, 0], skew[..., 1, 2] = q[..., 2], -q[..., 0]
    skew[..., 2, 0], skew[..., 2, 1] = -q[..., 1], q[..., 0]
    jc = np.concatenate((-jy@skew, jy, ji), axis=-1)
    jc[..., 8] = 0.  # Original SIMPLE_RADIAL objective: k2 is fixed.
    return pix-observed, jc, jy@r


def prediction(residual, jc, jp, dc, dp):
    jd = np.einsum('...ij,...j->...i', jc, dc)+np.einsum('...ij,...j->...i', jp, dp)
    return float(-np.sum(residual*jd)-.5*np.sum(jd*jd))
