"""Bounded derivative/stage contract checks. No BAL grid and no GPU."""
import json
import ctypes
import hashlib
import subprocess
from pathlib import Path
import numpy as np
from reference import STAGES, projection, residual_jacobian, prediction


def rotation(a):
    th = np.linalg.norm(a)
    if th == 0:
        return np.eye(3)
    k = np.array([[0., -a[2], a[1]], [a[2], 0., -a[0]], [-a[1], a[0], 0.]])/th
    return np.eye(3)+np.sin(th)*k+(1-np.cos(th))*(k@k)


def run():
    here = Path(__file__).resolve().parent
    shared = here/'build/host_projection.so'
    shared.parent.mkdir(exist_ok=True)
    subprocess.run(['g++','-O2','-std=c++17','-shared','-fPIC',str(here/'host_shim.cc'),'-o',str(shared)],check=True)
    cpp = ctypes.CDLL(str(shared)).o2_eval
    cpp.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]
    cpp.restype = None
    worst_cpp = 0.
    rng = np.random.default_rng(20260912)
    rows = []
    for s in STAGES:
        worst = 0.
        for sign in [-1., 1.]:
            for _ in range(8):
                r = rotation(rng.normal(size=3)*.2)
                x = rng.normal(size=3);x[2] = 5*sign
                t = rng.normal(size=3)*.1
                intr = np.array([730., -.09, 0.])
                d0 = (r@x+t)[2]*(.9+.2*rng.random())
                observed = rng.normal(size=2)*30
                res, jc, jp = residual_jacobian(r, t, x, intr, observed, d0, s)
                analytic = np.concatenate((jc, jp), axis=1)
                inputs = np.r_[r.reshape(-1), t, x, intr, observed, d0, s].astype(np.float64)
                outputs = np.empty(26,dtype=np.float64)
                cpp(inputs.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),outputs.ctypes.data_as(ctypes.POINTER(ctypes.c_double)))
                cpp_err=np.linalg.norm(outputs[:24].reshape(2,12)-analytic)/max(np.linalg.norm(analytic),1.)
                worst_cpp=max(worst_cpp,cpp_err)
                assert cpp_err<1e-13 and np.allclose(outputs[24:],res,rtol=1e-13,atol=1e-10)
                fd = np.empty((2, 12))
                for j in range(12):
                    h = 2e-6*(730 if j == 6 else 1)
                    v = np.zeros(12);v[j] = h
                    if j == 8:  # Native k2 zero mask.
                        fd[:, j] = 0;continue
                    vals = []
                    for mult in [1, -1]:
                        w = mult*v
                        rr = rotation(w[:3])@r
                        yy = rr@(x+w[9:])+t+w[3:6]
                        vals.append(projection(yy, intr+w[6:9], d0, s)[0]-observed)
                    fd[:, j] = (vals[0]-vals[1])/(2*h)
                err = np.linalg.norm(analytic-fd)/max(np.linalg.norm(fd), 1.)
                worst = max(worst, err)
                assert err < 2e-8, (s, err)
                dc, dp = rng.normal(size=9)*.001, rng.normal(size=3)*.001
                dc[8] = 0
                h = 2e-5
                def actual(mult):
                    yy = rotation(mult*dc[:3])@r@(x+mult*dp)+t+mult*dc[3:6]
                    return projection(yy, intr+mult*dc[6:9], d0, s)[0]-observed
                directional = (actual(h)-actual(-h))/(2*h)
                assert np.linalg.norm(directional-(jc@dc+jp@dp)) < 3e-7
                pred = prediction(res, jc, jp, dc, dp)
                both = jc@dc+jp@dp
                assert abs(pred-(-res@both-.5*both@both)) < 1e-10
        rows.append({'stage': s, 'finite_difference_relative_max': worst, 'cases': 16})
    # Initial costs coincide, but gradients differ.
    y = np.array([.2, -.1, -3.]);intr = np.array([700., -.1, 0.])
    base = projection(y, intr, y[2], 1.)
    for s in STAGES:
        q = projection(y, intr, y[2], s)
        assert np.array_equal(q[0], base[0])
        assert np.allclose(q[1][:, 2], s*base[1][:, 2], atol=1e-14, rtol=1e-14)
    # Exact s=1 ignores arbitrary d0, including NaN; explicit branch is required.
    assert np.array_equal(projection(y, intr, np.nan, 1.)[0], base[0])
    pole = projection(np.array([.2, .1, 1.]), intr, -1., .5)[0]
    assert not np.isfinite(pole).all()
    x = .5;second = (1+3*x*x)**2+(x+x**3-10)*(6*x)
    assert second == -25.0625
    return {'passed': True, 'rows': rows, 'cpp_vs_numpy_relative_max':worst_cpp,
            'projection_header_sha256':hashlib.sha256((here/'projection.h').read_bytes()).hexdigest(),
            'nonconvex_second_derivative': second,
            'intermediate_pole_detected': True, 'initial_cost_equality_without_gradient_equality': True}


if __name__ == '__main__':
    result = run()
    path = Path(__file__).with_name('tests.json')
    path.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
