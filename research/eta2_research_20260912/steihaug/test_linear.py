#!/usr/bin/env python3
"""CPU algebra gate: exercise the exact boundary helper used by CUDA host code."""
import ctypes
import json
from pathlib import Path
import subprocess
import numpy as np

P=Path(__file__).resolve().parent
B=P/'build'


def load_helper():
    B.mkdir(exist_ok=True)
    wrapper=B/'boundary_wrapper.cc'
    wrapper.write_text('''#include "boundary.h"
extern "C" double tau(double xx,double xp,double pp,double radius){
 return prism_stcg::boundary_tau(xx,xp,pp,radius);}
extern "C" bool crosses(double xx,double xp,double pp,double alpha,double radius){
 return prism_stcg::crosses(xx,xp,pp,alpha,radius);}
''')
    subprocess.run(['g++','-std=c++17','-O2','-shared','-fPIC','-I'+str(P),
                    str(wrapper),'-o',str(B/'boundary.so')],check=True)
    lib=ctypes.CDLL(str(B/'boundary.so'))
    lib.tau.argtypes=[ctypes.c_double]*4;lib.tau.restype=ctypes.c_double
    lib.crosses.argtypes=[ctypes.c_double]*5;lib.crosses.restype=ctypes.c_bool
    return lib


def stcg(A,b,M,radius,lib,tol=1e-11):
    L=np.linalg.cholesky(M)
    def pre(r):return np.linalg.solve(L.T,np.linalg.solve(L,r))
    def gram(x,p):
        u=L.T@x;v=L.T@p
        return float(u@u),float(u@v),float(v@v)
    x=np.zeros_like(b);r=b.copy();z=pre(r);p=z.copy();rz=r@z
    trajectory=[];reason='cap'
    for k in range(5*len(b)):
        Ap=A@p;pAp=p@Ap;pp=p@p;g=gram(x,p)
        if pAp<=1e-14*pp:
            tau=lib.tau(*g,radius);x+=tau*p;reason='curvature_cutoff';break
        al=rz/pAp
        if lib.crosses(*g,al,radius):
            tau=lib.tau(*g,radius);x+=tau*p;reason='boundary';break
        x+=al*p;r-=al*Ap
        trajectory.append(float(x@M@x))
        if np.linalg.norm(r)<=tol*np.linalg.norm(b):reason='interior';break
        z=pre(r);next_rz=r@z;p=z+(next_rz/rz)*p;rz=next_rz
    return dict(x=x,reason=reason,depth=k+1,trajectory=trajectory,
                relative_residual=float(np.linalg.norm(A@x-b)/np.linalg.norm(b)),
                norm=float(np.sqrt(x@M@x)),
                model=float(.5*x@A@x-b@x))


def main():
    lib=load_helper();rng=np.random.default_rng(20260912)
    n=18
    Q,_=np.linalg.qr(rng.normal(size=(n,n)))
    A=(Q*np.geomspace(.5,30,n))@Q.T
    C=rng.normal(size=(n,n));M=C@C.T+3*np.eye(n)
    b=rng.normal(size=n);exact=np.linalg.solve(A,b)
    norm=float(np.sqrt(exact@M@exact))
    a=stcg(A,b,M,10*norm,lib)
    assert a['reason']=='interior',a
    error=float(np.linalg.norm(a['x']-exact)/np.linalg.norm(exact))
    assert error<1e-9,error
    # Finite precision can lose exact-arithmetic iterate-norm monotonicity
    # near convergence. We measure directly and do not use that theorem as
    # an unchecked recurrence or an assumption in the boundary implementation.
    relative_increments=[(y-x)/max(x,1e-300)
                         for x,y in zip(a['trajectory'],a['trajectory'][1:])]
    rows=[]
    for fraction in [.01,.1,.4,.8]:
        R=fraction*norm;c=stcg(A,b,M,R,lib)
        assert c['reason']=='boundary',c
        assert abs(c['norm']/R-1)<1e-12,c
        assert c['model']<0,c
        # Standard CG in whitened coordinates is the same algorithm.
        L=np.linalg.cholesky(M)
        Aw=np.linalg.solve(L,A)@np.linalg.inv(L.T)
        bw=np.linalg.solve(L,b)
        ref=stcg(Aw,bw,np.eye(n),R,lib)
        relative=float(np.linalg.norm(c['x']-np.linalg.solve(L.T,ref['x'])) /
                       max(1e-300,np.linalg.norm(c['x'])))
        assert relative<1e-10,relative
        rows.append(dict(radius_fraction=fraction,depth=c['depth'],
                         radius_relative_error=abs(c['norm']/R-1),
                         whitened_direction_relative_error=relative,model=c['model']))
    indefinite=stcg(np.diag([-2.,3.,5.]),np.array([1.,.1,.2]),
                    np.diag([.5,2.,4.]),.7,lib)
    assert indefinite['reason']=='curvature_cutoff'
    assert abs(indefinite['norm']/.7-1)<1e-12 and indefinite['model']<0
    numerical_cutoff=stcg(np.eye(3)*1e-18,np.array([1.,.1,.2]),np.eye(3),1.,lib)
    assert numerical_cutoff['reason']=='curvature_cutoff'
    assert abs(numerical_cutoff['norm']-1)<1e-12 and numerical_cutoff['model']<0
    # The threshold branch also fires for a strictly SPD matrix: never label
    # every cutoff a true saddle or a negative Hessian eigenvalue.
    maximum=0.
    for _ in range(1000):
        R=10**rng.uniform(-70,70)
        x=rng.normal(size=7);x*=R*rng.uniform(0,.999)/np.linalg.norm(x)
        p=rng.normal(size=7)*10**rng.uniform(-60,60)
        xx=float(x@x);xp=float(x@p);pp=float(p@p)
        tau=lib.tau(xx,xp,pp,R)
        error=abs(np.linalg.norm(x+tau*p)/R-1)
        assert np.isfinite(tau) and tau>=0 and error<3e-13,(tau,error)
        maximum=max(maximum,error)
    assert lib.tau(1,1,1,1)==0
    assert abs(lib.tau(1,-1,1,1)-2)<1e-15
    assert lib.tau(1+1e-15,1,1,1)==0
    for inp in [(2,0,1,1),(0,0,0,1),(0,0,1,-1),(float('nan'),0,1,1)]:
        assert np.isnan(lib.tau(*inp)),inp
    result=dict(seed=20260912,shared_cpp_boundary_helper=True,
                interior_direction_relative_error=float(np.linalg.norm(a['x']-exact)/np.linalg.norm(exact)),
                interior_relative_residual=a['relative_residual'],
                minimum_interior_M_norm_squared_relative_increment=min(relative_increments),
                interior_depth=a['depth'],boundary_cases=rows,
                indefinite_case=dict(reason=indefinite['reason'],norm=indefinite['norm'],model=indefinite['model']),
                positive_but_cutoff_case=dict(reason=numerical_cutoff['reason'],
                    smallest_eigenvalue=1e-18,model=numerical_cutoff['model']),
                random_root_trials=1000,max_radius_relative_error=maximum,
                invalid_input_checks=4,status='passed',gpu_tested=False)
    (P/'linear_verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
