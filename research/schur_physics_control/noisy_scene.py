"""Reproducible BAL initialization noise; observations and intrinsics stay fixed."""
import hashlib
import pathlib
import numpy as np

SOURCE = pathlib.Path('/workspace/bal/final-13682.txt')
CHUNK = 250_000

def rotation(v):
    theta = np.linalg.norm(v, axis=1)
    K = np.zeros((len(v), 3, 3))
    K[:, 0, 1] = -v[:, 2]; K[:, 0, 2] = v[:, 1]
    K[:, 1, 0] = v[:, 2]; K[:, 1, 2] = -v[:, 0]
    K[:, 2, 0] = -v[:, 1]; K[:, 2, 1] = v[:, 0]
    a = np.sinc(theta/np.pi)
    b = .5*np.sinc(theta/(2*np.pi))**2
    return np.eye(3)[None] + a[:, None, None]*K + b[:, None, None]*(K@K)

def digest(path):
    with pathlib.Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

class Scene:
    def __init__(self, path=SOURCE):
        self.path = pathlib.Path(path)
        with self.path.open('rb') as f:
            self.header = f.readline()
            self.dims = tuple(map(int, self.header.split()))
            nc, np_, no = self.dims
            self.raw = b''.join(f.readline() for _ in range(no))
            values = np.loadtxt(f)
        assert values.size == 9*nc + 3*np_
        self.obs = np.fromstring(self.raw.decode(), sep=' ').reshape(no, 4)
        self.c0 = values[:9*nc].reshape(nc, 9)
        self.x0 = values[9*nc:].reshape(np_, 3)
        self.R0 = rotation(self.c0[:, :3])
        self.centers = -np.einsum('nji,nj->ni', self.R0, self.c0[:, 3:6])
        self.radius = float(np.median(np.linalg.norm(self.x0-np.median(self.x0, axis=0), axis=1)))
        # Sampling is fixed before any solver runs and shared by all seeds.
        idx = np.random.default_rng(1907).choice(no, size=min(200_000, no), replace=False)
        self.sample = self.obs[np.sort(idx)]
        self.sample_uv, _ = self.project(self.c0, self.x0, self.sample)
        self.obs_sha = hashlib.sha256(self.raw).hexdigest()

    @staticmethod
    def project(c, x, obs):
        ci = obs[:, 0].astype(np.int64)
        pi = obs[:, 1].astype(np.int64)
        R = rotation(c[:, :3])
        q = np.einsum('nij,nj->ni', R[ci], x[pi]) + c[ci, 3:6]
        with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
            uv = -q[:, :2] / q[:, 2, None]
            r2 = np.sum(uv*uv, axis=1)
            uv *= (c[ci, 6]*(1+c[ci, 7]*r2))[:, None]  # --zero_k2
        return uv, q[:, 2]

    def perturb(self, seed, pixels):
        rng = np.random.default_rng(seed)
        dr = rng.normal(0, .001, (self.dims[0], 3))
        dc = rng.normal(0, .001*self.radius, self.centers.shape)
        dx = rng.normal(0, .001*self.radius, self.x0.shape)
        def state(a):
            c = self.c0.copy()
            c[:, :3] += a*dr
            R = rotation(c[:, :3])
            c[:, 3:6] = -np.einsum('nij,nj->ni', R, self.centers+a*dc)
            return c, self.x0+a*dx
        lo, hi = 0., 1.
        while True:
            c, x = state(hi)
            uv, _ = self.project(c, x, self.sample)
            if np.median(np.linalg.norm(uv-self.sample_uv, axis=1)) >= pixels:
                break
            hi *= 2
            assert hi <= 64
        for _ in range(25):
            a = .5*(lo+hi)
            c, x = state(a)
            uv, _ = self.project(c, x, self.sample)
            if np.median(np.linalg.norm(uv-self.sample_uv, axis=1)) >= pixels:
                hi = a
            else:
                lo = a
        a = .5*(lo+hi)
        c, x = state(a)
        assert np.array_equal(c[:, 6:], self.c0[:, 6:])
        assert np.isfinite(c).all() and np.isfinite(x).all()
        return c, x, {'seed': seed, 'requested_sample_median_px': pixels,
                      'amplitude': a, 'rotation_component_sigma_rad': a*.001,
                      'center_point_component_sigma_world': a*.001*self.radius}

    def inspect(self, c, x):
        displacement = np.empty(self.dims[2])
        cost, clean_cost = np.longdouble(0), np.longdouble(0)
        sign_changes = 0
        for start in range(0, self.dims[2], CHUNK):
            o = self.obs[start:start+CHUNK]
            uv0, z0 = self.project(self.c0, self.x0, o)
            uv, z = self.project(c, x, o)
            displacement[start:start+len(o)] = np.linalg.norm(uv-uv0, axis=1)
            cost += .5*np.sum((uv-o[:, 2:4])**2, dtype=np.longdouble)
            clean_cost += .5*np.sum((uv0-o[:, 2:4])**2, dtype=np.longdouble)
            sign_changes += int(np.count_nonzero(np.signbit(z) != np.signbit(z0)))
        assert np.isfinite(cost) and np.isfinite(displacement).all()
        return {'initial_cost': float(cost), 'clean_initial_cost': float(clean_cost),
                'projection_displacement_px_p50_p95_max': np.percentile(displacement, [50, 95, 100]).tolist(),
                'depth_sign_changes': sign_changes, 'observations': self.dims[2],
                'observation_sha256': self.obs_sha, 'point_radius': self.radius}

    def write(self, destination, c, x):
        destination = pathlib.Path(destination)
        with destination.open('wb') as f:
            f.write(self.header)
            f.write(self.raw)
            np.savetxt(f, c.ravel(), fmt='%.17g')
            np.savetxt(f, x.ravel(), fmt='%.17g')
        # Read back every parameter and independently hash the observation prefix.
        h = hashlib.sha256()
        with destination.open('rb') as f:
            assert f.readline() == self.header
            for _ in range(self.dims[2]):
                h.update(f.readline())
            values = np.loadtxt(f)
        assert h.hexdigest() == self.obs_sha
        assert np.array_equal(values[:c.size], c.ravel())
        assert np.array_equal(values[c.size:], x.ravel())
        return digest(destination)

if __name__ == '__main__':
    import json
    s = Scene()
    print('LOADED', s.dims, flush=True)
    c, x, meta = s.perturb(17, 1.)
    meta.update(s.inspect(c, x))
    print(json.dumps(meta, indent=2), flush=True)
