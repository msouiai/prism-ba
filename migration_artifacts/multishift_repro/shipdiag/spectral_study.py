#!/usr/bin/env python3
"""Spectral headroom study for MFREE ideas 1/2/3 on real Schur complements.

Builds S = B - E (V+D_p)^-1 E^T at the BAL starting point (9-DOF Snavely,
k2=0, D_p = tau*diag(V) with tau=3e-3), Jacobi-equilibrates it like the
solver, then measures on the REAL spectrum:
  - plain CG iterations per menu shift (lam*10^(l-2), l=0..4)
  - tail-deflated CG (k lowest exact eigenvectors -- headroom upper bound;
    shift-invariant, so ONE basis serves the whole menu)
  - Nystrom rank-r preconditioned CG per shift (FTU formula)
  - shift-and-invert conditioning analysis (from eigenvalues directly)
Approximations vs the CUDA solver (noted, not hidden): FD Jacobians, no
absolute-intrinsics damping, plain Jacobi equilibration. Spectrum-level
conclusions are insensitive to these.
"""
import numpy as np, json, sys, time

def rodrigues(w):
    th = np.linalg.norm(w, axis=1, keepdims=True)
    k = np.where(th > 1e-12, w / np.maximum(th, 1e-12), 0*w)
    K = np.zeros((len(w), 3, 3))
    K[:,0,1], K[:,0,2] = -k[:,2], k[:,1]
    K[:,1,0], K[:,1,2] = k[:,2], -k[:,0]
    K[:,2,0], K[:,2,1] = -k[:,1], k[:,0]
    c, s = np.cos(th)[:,:,None], np.sin(th)[:,:,None]
    return c*np.eye(3) + s*K + (1-c)*np.einsum('ni,nj->nij', k, k)

def residuals(cam, X, cams_i, pts_i, uv):
    R = rodrigues(cam[:,:3])
    P = np.einsum('nij,nj->ni', R[cams_i], X[pts_i]) + cam[cams_i,3:6]
    proj = -P[:,:2] / P[:,2:3]
    r2 = (proj**2).sum(1, keepdims=True)
    f, k1 = cam[cams_i,6:7], cam[cams_i,7:8]
    return (f*(1 + k1*r2)*proj - uv).ravel()

def build_S(path, tau=3e-3, max_obs=None):
    with open(path) as fh:
        ncam, npt, nobs = map(int, fh.readline().split())
        ci = np.empty(nobs, np.int32); pi = np.empty(nobs, np.int32)
        uv = np.empty((nobs,2))
        for i in range(nobs):
            a,b,x,y = fh.readline().split()
            ci[i], pi[i], uv[i] = int(a), int(b), (float(x), float(y))
        prm = np.array([float(fh.readline()) for _ in range(9*ncam+3*npt)])
    cam = prm[:9*ncam].reshape(ncam,9).copy()
    cam = np.column_stack([cam[:,:6], cam[:,6], cam[:,7]])  # drop k2 (zeroed)
    X = prm[9*ncam:].reshape(npt,3)
    r0 = residuals(cam, X, ci, pi, uv)

    # FD Jacobians: 8 camera passes + 3 point passes, vectorized over all obs
    Jc = np.empty((2*nobs, 8)); Jp = np.empty((2*nobs, 3))
    for j in range(8):
        h = 1e-6*(1+np.abs(cam[:,j]))
        cp = cam.copy(); cp[:,j] += h
        Jc[:,j] = (residuals(cp,X,ci,pi,uv) - r0) / np.repeat(h[ci],2)
    for j in range(3):
        h = 1e-6*(1+np.abs(X[:,j]))
        Xp = X.copy(); Xp[:,j] += h
        Jp[:,j] = (residuals(cam,Xp,ci,pi,uv) - r0) / np.repeat(h[pi],2)

    d = 8   # 9-DOF minus frozen k2
    B = np.zeros((ncam,d,d)); V = np.zeros((npt,3,3));
    Jc2 = Jc.reshape(nobs,2,d); Jp2 = Jp.reshape(nobs,2,3)
    np.add.at(B, ci, np.einsum('nki,nkj->nij', Jc2, Jc2))
    np.add.at(V, pi, np.einsum('nki,nkj->nij', Jp2, Jp2))
    W = np.einsum('nki,nkj->nij', Jc2, Jp2)          # per-obs 8x3
    Vd = V + tau*np.eye(3)*np.maximum(V.diagonal(0,1,2),1e-12)[:,:,None]*0
    for p in range(npt):
        Vd[p] = V[p] + tau*np.diag(np.maximum(np.diag(V[p]),1e-12))
    Vinv = np.linalg.inv(Vd)
    n = ncam*d
    S = np.zeros((n,n))
    for c in range(ncam):
        S[c*d:(c+1)*d, c*d:(c+1)*d] = B[c]
    # E Vinv E^T accumulated per point over its observing cameras
    from collections import defaultdict
    obs_of_pt = defaultdict(list)
    for o in range(nobs): obs_of_pt[pi[o]].append(o)
    for p, obs in obs_of_pt.items():
        Ecs = [(ci[o], W[o]) for o in obs]
        Vi = Vinv[p]
        for a,(ca,Wa) in enumerate(Ecs):
            WaVi = Wa @ Vi
            for cb,Wb in Ecs:
                S[ca*d:(ca+1)*d, cb*d:(cb+1)*d] -= WaVi @ Wb.T
    D = np.sqrt(np.maximum(np.diag(S),1e-30))
    S = S / D[:,None] / D[None,:]
    return (S + S.T)/2

def cg_iters(A, b, tol, maxit=3000, prec=None):
    x = np.zeros_like(b); r = b.copy()
    z = prec(r) if prec else r
    p = z.copy(); rz = r@z; nb = np.linalg.norm(b)
    for it in range(1, maxit+1):
        Ap = A@p; alpha = rz/(p@Ap)
        x += alpha*p; r -= alpha*Ap
        if np.linalg.norm(r) < tol*nb: return it
        z = prec(r) if prec else r
        rz2 = r@z; p = z + (rz2/rz)*p; rz = rz2
    return maxit

def study(name, path):
    t0=time.time()
    S = build_S(path)
    n = len(S)
    evals, evecs = np.linalg.eigh(S)
    evals = np.maximum(evals, 1e-14)
    print(f"\n=== {name}: n={n}, build+eig {time.time()-t0:.0f}s")
    print(f"    spectrum: min={evals[0]:.3e} max={evals[-1]:.3e} kappa={evals[-1]/evals[0]:.2e}")
    rng = np.random.default_rng(0)
    b = rng.standard_normal(n); b /= np.linalg.norm(b)
    out = {"name":name,"n":n,"eig_min":evals[0],"eig_max":evals[-1]}
    for lam_c, phase in ((10.0,"opening"), (1e-3,"grind")):
        shifts = [lam_c*10**(l-2) for l in range(5)]
        plain  = [cg_iters(S+s*np.eye(n), b, 1e-4) for s in shifts]
        # deflation headroom: one shift-invariant basis for the WHOLE menu
        defl = {}
        for k in (8,16,32):
            U = evecs[:,:k]
            Pb = b - U@(U.T@b)
            its=[]
            for s in shifts:
                A = S+s*np.eye(n)
                its.append(cg_iters(A, Pb, 1e-4,
                    prec=lambda r,U=U: r - U@(U.T@r)))
            defl[k]=its
        # Nystrom rank-r per shift (exact top-r eigs = FTU upper bound)
        r_ny=50
        Ut, Lt = evecs[:,-r_ny:], evals[-r_ny:]
        ny=[]
        for s in shifts:
            A = S+s*np.eye(n); mu=Lt[0]+s
            pre=lambda v,U=Ut,L=Lt,s=s,mu=mu: mu*(U@((U.T@v)/(L+s))) + (v-U@(U.T@v))
            ny.append(cg_iters(A, b, 1e-4, prec=pre))
        print(f"    [{phase}] shifts={['%.0e'%s for s in shifts]}")
        print(f"      plain CG its/shift : {plain}  (menu cost = max = {max(plain)})")
        for k,its in defl.items():
            print(f"      deflate k={k:<3}      : {its}  (max {max(its)}, save {1-max(its)/max(plain):.0%})")
        print(f"      Nystrom r=50/shift : {ny}  (SUM = {sum(ny)} vs shared {max(plain)})")
        # shift-and-invert conditioning, tau = geometric mean of menu
        tau = float(np.sqrt(shifts[0]*shifts[-1]))
        g = (evals+min(shifts))/(evals+tau), (evals+max(shifts))/(evals+tau)
        kap = max(g[0].max()/g[0].min(), g[1].max()/g[1].min())
        kin = (evals[-1]+tau)/(evals[0]+tau)
        print(f"      shift-invert: worst outer kappa={kap:.2f} (~{int(np.ceil(np.sqrt(kap)*np.log(2/1e-4)/2))} outer its), inner kappa={kin:.2e}")
        out[phase]={"shifts":shifts,"plain":plain,"defl":{str(k):v for k,v in defl.items()},"nystrom":ny}
    return out

res=[]
for nm,p in [("venice-52","/workspace/bundle_adjustment/daba_cuda/venice-52.txt"),
             ("dubrovnik-88","/workspace/bundle_adjustment/daba_cuda/dubrovnik-88.txt"),
             ("ladybug-49","/workspace/bundle_adjustment/daba_cuda/ladybug-49.txt")]:
    res.append(study(nm,p))
json.dump(res, open("/tmp/agent/spectral_study.json","w"), default=float)
print("\nsaved /tmp/agent/spectral_study.json")
