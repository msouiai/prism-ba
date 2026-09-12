#!/usr/bin/env python3
"""Tiny independent ARC correctness tests; run before BAL witness data."""
from pathlib import Path
import json
import hashlib
import numpy as np
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation
from arc_core import CHART,Problem,Model,krylov,cubic_root

P=Path(__file__).resolve().parent


def main():
    baseline=CHART.verify_frozen_baseline();rng=np.random.default_rng(202609127)
    # Coherent normal system with coupled point damping: Schur is not a shift.
    J=rng.normal(size=(20,7));g=J.T@rng.normal(size=20);H=J.T@J
    nc=4;U,W,V=H[:nc,:nc],H[:nc,nc:],H[nc:,nc:]
    E=np.exp(rng.normal(scale=.4,size=nc));Dp=np.exp(rng.normal(scale=.4,size=3))
    def schur(lam):
        inv=np.linalg.inv(V+lam*np.diag(Dp))
        return E[:,None]*(U-W@inv@W.T)*E[None,:]+lam*np.eye(nc),-E*(g[:nc]-W@inv@g[nc:])
    a0,b0=schur(0.);a1,b1=schur(.7);extra=a1-a0-.7*np.eye(nc)
    nonscalar=extra-np.trace(extra)/nc*np.eye(nc)
    shifted=dict(extra_schur_term_fro=float(np.linalg.norm(extra)),nonscalar_component_fro=float(np.linalg.norm(nonscalar)),
                 reduced_rhs_change_norm=float(np.linalg.norm(b1-b0)))
    assert min(shifted.values())>1e-3,shifted
    D=np.r_[1/E**2,Dp];invroot=1/np.sqrt(D);whiten=invroot[:,None]*H*invroot[None,:]
    fullshift=invroot[:,None]*(H+.7*np.diag(D))*invroot[None,:]-whiten-.7*np.eye(7)
    shifted['full_whitened_shift_error']=float(np.linalg.norm(fullshift));assert np.linalg.norm(fullshift)<1e-13
    # Independent dense cubic minimization versus full-space Krylov secular solve.
    A=rng.normal(size=(12,12));H=A.T@A+.2*np.eye(12);g=rng.normal(size=12);sigma=.43
    Q,T,gp,kr=krylov(lambda v:H@v,g,12);y,root=cubic_root(T,gp,sigma);step=Q@y
    def fun(x):return g@x+.5*x@H@x+sigma*np.linalg.norm(x)**3/3
    def jac(x):return g+H@x+sigma*np.linalg.norm(x)*x
    def hess(x):
        n=np.linalg.norm(x)
        return H+sigma*n*np.eye(len(x))+(sigma*np.outer(x,x)/n if n else 0)
    direct=minimize(fun,np.zeros(12),jac=jac,hess=hess,method='trust-exact',options={'gtol':1e-12,'maxiter':200})
    rel=float(np.linalg.norm(step-direct.x)/np.linalg.norm(direct.x));station=float(np.linalg.norm(jac(step))/np.linalg.norm(g))
    assert rel<1e-7 and station<1e-10,(rel,station,direct.message)
    assert kr['orthogonality_error']<1e-12 and root['secular_relative_residual']<1e-10
    cubic_reference=dict(direction_relative_error=rel,full_stationarity_relative_residual=station,
        direct_optimizer_message=str(direct.message),direct_objective=float(direct.fun),projected_objective=float(fun(step)),
        basis=kr,root=root)
    # The production 64-vector path, with a deliberately unresolved full residual.
    large=rng.normal(size=(96,96));large=large.T@large+.001*np.eye(96);lg=rng.normal(size=96)
    lQ,lT,lgh,lkr=krylov(lambda v:large@v,lg,64);ly,lroot=cubic_root(lT,lgh,.02)
    ld=lQ@ly;lres=float(np.linalg.norm((large+lroot['lambda_value']*np.eye(96))@ld+lg)/np.linalg.norm(lg))
    assert lkr['dimension']==64 and lkr['full_products']==64 and lkr['orthogonality_error']<1e-12
    assert lres>lroot['projected_stationarity_relative_residual']*10
    fixed64=dict(basis=lkr,root=lroot,full_relative_residual=lres)
    # Full-whitened normal product from BA Jacobians versus independent dense J.
    nc,np_=3,5
    cameras=CHART.CameraState(Rotation.from_rotvec(rng.normal(scale=.05,size=(nc,3))).as_matrix(),
      rng.normal(scale=.1,size=(nc,3)),np.column_stack([np.full(nc,300.),np.full(nc,.01),np.zeros(nc)]))
    X=rng.normal(scale=.3,size=(np_,3));X[:,2]-=3
    ci=np.tile(np.arange(nc),np_);pi=np.repeat(np.arange(np_),nc);chart=CHART.make_chart(X,cameras,'euclidean')
    uv=CHART.observation_jacobians(cameras,chart.H,chart.T,ci,pi,np.zeros((len(ci),2)))[0]+rng.normal(size=(len(ci),2))
    problem=Problem(cameras,X,ci,pi,uv,np.exp(rng.normal(scale=.3,size=(nc,9))),np.exp(rng.normal(scale=.3,size=(np_,3))))
    model=Model(problem,np.zeros(problem.n));J=np.zeros((2*len(ci),problem.n))
    for obs,(cam,point) in enumerate(zip(ci,pi)):
        J[2*obs:2*obs+2,9*cam:9*cam+9]=model.Jc[obs]
        J[2*obs:2*obs+2,problem.ncf+3*point:problem.ncf+3*point+3]=model.Jp[obs]
    H=J.T@J+np.diag(np.r_[model.prior.reshape(-1),np.zeros(3*np_)])
    v=rng.normal(size=problem.n);rootD=np.sqrt(problem.D);d=v/rootD;lam=.2
    product=model.normal_product(d,lam)/rootD;direct=(H+lam*np.diag(problem.D))@d/rootD
    producterror=float(np.linalg.norm(product-direct)/np.linalg.norm(direct));assert producterror<1e-13,producterror
    actual_g=model.g/rootD;dense_g=J.T@model.r.reshape(-1)/rootD
    graderror=float(np.linalg.norm(actual_g-dense_g)/np.linalg.norm(dense_g));assert graderror<1e-13
    symmetry=float(abs(v@(model.normal_product(d,0.)/rootD)-d@H@d)/max(abs(d@H@d),1e-300));assert symmetry<1e-13
    result=dict(status='passed',seed=202609127,baseline=baseline,schur_shift_obstruction=shifted,
      dense_cubic_reference=cubic_reference,fixed64_test=fixed64,ba_full_product_relative_error=producterror,ba_whitened_gradient_relative_error=graderror,
      ba_whitened_quadratic_form_relative_error=symmetry,gpu_used=False,
      source_sha256={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in ('arc_core.py','verify.py')})
    (P/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='baseline'},indent=2))


if __name__=='__main__':main()
