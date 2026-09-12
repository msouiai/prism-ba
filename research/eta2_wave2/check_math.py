"""Independent small checks of identities and decomposition, before promotion."""
import json
from pathlib import Path
import numpy as np
from scipy.optimize import brentq
from witness_composition import subspaces,decompose,D

P=Path(__file__).resolve().parent
def main():
    # Exact illustrative TR root (the quoted 0.008 is only approximate).
    A=np.diag([1.,1e-6]);b=np.array([1.,1e-3]);d=np.linalg.solve(A,b)
    root=brentq(lambda l:np.linalg.norm(np.linalg.solve(A+l*np.eye(2),b))-1,1e-12,1.)
    clipped=d/np.linalg.norm(d);consistent=np.linalg.solve(A+root*np.eye(2),b)
    gain=lambda x:float(b@x-.5*x@A@x)
    # A positive-definite coupled normal system whose camera norm INCREASES
    # with increasing damping: point/camera RHS cancellation at small lambda.
    H=np.array([[2.,1.],[1.,1.]]);g=np.array([1.,1.]);Dc=np.diag(np.diag(H))
    ls=np.array([1e-9,1e-3,.1,1.]);steps=[np.linalg.solve(H+l*Dc,-g) for l in ls]
    assert abs(steps[2][0])>100*abs(steps[0][0])
    # A consistent joint gauge null direction with point-damping injection.
    J=np.array([[1.,-1.],[2.,-2.]]);r=np.array([.7,-.2]);H=J.T@J;g=J.T@r
    tau=.3;lam=.01;V=H[1,1];W=H[0,1];Dp=V
    S=H[0,0]-W*W/(V+tau*Dp)+lam
    rhs=-g[0]+W*g[1]/(V+tau*Dp)
    inj=tau*g[1]*Dp/(V+tau*Dp)
    additional=V-V*V/(V+tau*Dp)
    assert abs(rhs-inj)<1e-15 and abs(S-lam-additional)<1e-14 and additional>lam
    records=[]
    C=P.parent/'eta2_research_20260912/evidence/collect'
    for folder in sorted(C.glob('*capture-*')):
        if not (folder/'metadata.txt').exists():continue
        m=D.read_metadata(folder/'metadata.txt');nc=int(m['ncam'])
        R=D.read_array(folder/'R_state.f64',(nc,3,3));t=D.read_array(folder/'t_state.f64',(nc,3));E=D.read_array(folder/'E.f64',(nc,9))
        G,Q,meta=subspaces(R,t,E);z=D.read_array(folder/'eta2_raw_scaled.f64',(nc,9))
        parts,info=decompose(z,G,Q)
        assert abs(info['sum_squared_fraction']-1)<1e-8
        assert meta['cross_orthogonality']<1e-8
        # Compare finite-difference gauge basis against native analytic formula.
        raw=np.zeros((nc,9,7));cent=(-np.einsum('nji,nj->ni',R,t)).mean(axis=0)
        centers=-np.einsum('nji,nj->ni',R,t)
        for k in range(3):
            u=np.eye(3)[k];raw[:,:3,k]=-np.einsum('nij,j->ni',R,u)
            raw[:,3:6,k]=np.einsum('nij,j->ni',R,np.cross(u,cent))
            raw[:,3:6,3+k]=-np.einsum('nij,j->ni',R,u)
        raw[:,3:6,6]=-np.einsum('nij,nj->ni',R,centers-cent)
        B=(raw/E[:,:,None]).reshape(-1,7);B/=np.linalg.norm(B,axis=0)
        error=np.linalg.norm(B-G@(G.T@B))/np.linalg.norm(B)
        assert error<1e-8
        records.append(dict(capture=folder.name,projection_sum=info['sum_squared_fraction'],native_analytic_gauge_span_error=float(error)))
    out=dict(passed=True,toy_exact_lambda=root,quoted_lambda_radius=float(np.linalg.norm(np.linalg.solve(A+.008*np.eye(2),b))),
        clipped_model_decrease=gain(clipped),consistent_model_decrease=gain(consistent),gain_factor=gain(consistent)/gain(clipped),
        coupled_camera_norm_counterexample=dict(lambdas=ls.tolist(),camera_steps=[float(x[0]) for x in steps]),
        gauge_rhs=rhs,gauge_injection=inj,point_damping_gauge_curvature=additional,projection_checks=records)
    (P/'math_checks.json').write_text(json.dumps(out,indent=2)+'\n');print('MATH PASSED',len(records),flush=True)
if __name__=='__main__':main()
