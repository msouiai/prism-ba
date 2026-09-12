#!/usr/bin/env python3
"""Seeded two-view Schur rounding experiment; no nonlinear solver comparison."""
from pathlib import Path
import hashlib,json,time
import numpy as np

def point_solve(J,lam,s):
    D=np.sum(J*J,axis=0);e=1/np.sqrt(D)
    B=J*e
    return e*np.linalg.solve(B.T@B+lam*np.eye(3),e*s)

def energy(Jc,Jp,lam,v):
    y=Jc@v;s=Jp.T@y;u=point_solve(Jp,lam,s);z=y-Jp@u
    D=np.sum(Jp*Jp,axis=0)
    sos=float(z@z+lam*np.sum(D*u*u)+lam*(v@v))
    Ap=Jc.T@z+lam*v
    return sos,float(v@Ap),u,y,D

def main():
    rng=np.random.default_rng(20260912);rows=[];start=time.monotonic()
    for i in range(3000):
        Jp=rng.normal(size=(4,3));depth=10**rng.uniform(-8,-5);Jp[:,2]*=depth
        Jc=np.zeros((4,18));Jc[:2,:9]=rng.normal(size=(2,9));Jc[2:,9:]=rng.normal(size=(2,9))
        Jc/=np.sqrt(np.sum(Jc*Jc,axis=0))
        lam=10**rng.uniform(-14,-9)
        U=Jc.T@Jc;W=Jc.T@Jp;W32=W.astype(np.float32).astype(np.float64)
        sol=np.column_stack([point_solve(Jp,lam,w) for w in W32])
        mixed=U-W32@sol+lam*np.eye(18)
        eigen,vectors=np.linalg.eigh((mixed+mixed.T)*.5);v=vectors[:,0]
        sos,dot,u,y,D=energy(Jc,Jp,lam,v)
        jc32=Jc.astype(np.float32).astype(np.float64);jp32=Jp.astype(np.float32).astype(np.float64)
        sos32,dot32,_,_,_=energy(jc32,jp32,lam,v)
        # Deliberately inaccurate point solve tests the omitted u^T e term.
        ua=u+1e-4*rng.normal(size=3)/np.sqrt(D)
        e=Jp.T@(y-Jp@ua)-lam*D*ua
        za=y-Jp@ua
        actual=float(v@(Jc.T@za+lam*v))
        approx_sos=float(za@za+lam*np.sum(D*ua*ua)+lam*(v@v))
        corrected=approx_sos+float(ua@e)
        err=abs(actual-corrected)/max(1,abs(actual),abs(corrected))
        assert err<2e-13,(i,err)
        assert np.isfinite(sos) and sos>=0 and np.isfinite(sos32) and sos32>=0
        rows.append(dict(trial=i,lambda_=lam,depth_scale=depth,mixed_min_eigenvalue=float(eigen[0]),
          fp64_sos=sos,fp64_product_dot=dot,fp32_consistent_sos=sos32,fp32_consistent_product_dot=dot32,
          approximate_solve_sos_gap=actual-approx_sos,approximate_identity_error=err))
    result=dict(seed=20260912,trials=len(rows),seconds=time.monotonic()-start,
      mixed_negative=sum(r['mixed_min_eigenvalue']<0 for r in rows),mixed_min=min(r['mixed_min_eigenvalue'] for r in rows),
      fp64_sos_negative=sum(r['fp64_sos']<0 for r in rows),fp32_consistent_sos_negative=sum(r['fp32_consistent_sos']<0 for r in rows),
      fp64_dot_negative=sum(r['fp64_product_dot']<0 for r in rows),fp32_consistent_dot_negative=sum(r['fp32_consistent_product_dot']<0 for r in rows),
      max_approximate_identity_error=max(r['approximate_identity_error'] for r in rows),
      max_approximate_sos_gap=max(abs(r['approximate_solve_sos_gap']) for r in rows),
      source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      scope='Seeded algebraic stress case with scaled Gaussian local Jacobians. Not a BAL rollout, timing comparison, or universal frequency of negative curvature.',rows=rows)
    out=Path(__file__).with_name('energy_results.json');out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
if __name__=='__main__':main()
