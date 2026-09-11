"""Exact small-system validation of mode scores and balanced inverse."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import numpy as np
from paths import ROOT,write_json
from reference_ba import Linearization  # resolves the pinned SciPy path
from scipy.linalg import eigh

rows=[]
for seed in range(400,410):
    rng=np.random.default_rng(seed);n=40;m=12
    A=rng.normal(size=(n,n));S=A.T@A+.1*np.eye(n)
    L=np.linalg.cholesky(np.diag(np.diag(S)))
    M=L@L.T;Mi=np.linalg.inv(M);V=rng.normal(size=(n,m));r=rng.normal(size=n)
    K=V.T@S@V;G=V.T@M@V;theta,Y=eigh(K,G);Z=V@Y
    projected=Z.T@r;w=projected**2/theta;order=np.argsort(-w)
    np.testing.assert_allclose(Z.T@M@Z,np.eye(m),atol=2e-13)
    np.testing.assert_allclose(Z.T@S@Z,np.diag(theta),atol=2e-13)
    for rank in [2,4]:
        z=Z[:,order[:rank]];k=z.T@S@z;q=z@np.linalg.solve(k,z.T)
        pinv=q+(np.eye(n)-q@S)@Mi@(np.eye(n)-S@q)
        np.testing.assert_allclose(pinv,pinv.T,atol=2e-13)
        assert np.linalg.eigvalsh(pinv).min()>0
        d=q@r;gain=r@d-.5*d@S@d;score=.5*w[order[:rank]].sum()
        assert abs(gain-score)/score<1e-12
        # Check the exact two-sided application used by the native class.
        coeff=np.linalg.solve(k,z.T@r);work=r-S@z@coeff
        application=Mi@work
        application+=z@(coeff-np.linalg.solve(k,(S@z).T@application))
        np.testing.assert_allclose(application,pinv@r,atol=2e-13)
        rows.append({'seed':seed,'rank':rank,'score':score,'actual_quadratic_gain':gain,
            'inverse_min_eigenvalue':np.linalg.eigvalsh(pinv).min()})
write_json(ROOT/'schur_math_checks.json',{'passed':True,'checks':rows})
print('generalized score and balanced SPD inverse: PASS')
