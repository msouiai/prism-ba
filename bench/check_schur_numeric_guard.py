#!/usr/bin/env python3
"""Independent dense check of monotone coupled damping with inconsistent blocks."""
import argparse
import json
import pathlib
import numpy as np

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path,required=True);a=ap.parse_args()
    rng=np.random.default_rng(92026);rows=[]
    for _ in range(100):
        jp=rng.normal(size=(24,7));jc=jp@rng.normal(size=(7,9))+1e-5*rng.normal(size=(24,9))
        B=jc.T@jc;C=jp.T@jp;Dp=np.diag(np.diag(C));E=np.diag(1/np.sqrt(np.diag(B)))
        # A rounded/inconsistent cross block can defeat positivity of the block Gram.
        W=(jc.T@jp)*(1+1e-5)
        def S(lam):return E@(B-W@np.linalg.solve(C+lam*Dp,W.T))@E+lam*np.eye(9)
        lam=1e-9;before=S(lam);ev,U=np.linalg.eigh(before);p=U[:,0];q=p@before@p
        assert q<0
        repaired=4*max(lam,lam-q);after=S(repaired)
        lower=q+repaired-lam;observed=p@after@p
        increment_min=np.linalg.eigvalsh(after-before-(repaired-lam)*np.eye(9))[0]
        assert observed>=lower-1e-10 and observed>0
        assert increment_min>=-1e-10
        # Independent least-squares elimination: full joint energy equals the
        # coherent Schur energy and is nonnegative despite a nearly null mode.
        W0=jc.T@jp;camera=E@p;point=-np.linalg.solve(C+repaired*Dp,W0.T@camera)
        positive=np.linalg.norm(jc@camera+jp@point)**2+repaired*point@Dp@point+repaired*(p@p)
        schur=p@(E@(B-W0@np.linalg.solve(C+repaired*Dp,W0.T))@E+repaired*np.eye(9))@p
        assert positive>0 and abs(positive-schur)<1e-10*max(1,positive)
        rows.append(dict(before=float(q),after=float(observed),directional_lower_bound=float(lower),monotonicity_min_eigenvalue=float(increment_min),energy_identity_error=float(abs(positive-schur))))
    result=dict(cases=len(rows),all_passed=True,min_repaired_curvature=min(r['after'] for r in rows),max_energy_identity_error=max(r['energy_identity_error'] for r in rows),scope='Fixed Hcc coordinates, SPD point damping, frozen quantized blocks. Directional repair guarantee in exact arithmetic; no certificate for all directions, no nonlinear convergence or speed claim.',cases_detail=rows)
    with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='cases_detail'}))

if __name__=='__main__':main()
