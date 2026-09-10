#!/usr/bin/env python3
"""Small counterexamples and shared/independent-CG consistency checks."""
import json
import numpy as np

def cg(A,b,shift,k):
    x=np.zeros_like(b);r=b.copy();p=r.copy();rr=r@r
    for _ in range(k):
        Ap=A@p+shift*p;alpha=rr/(p@Ap);x+=alpha*p;r-=alpha*Ap
        rn=r@r;p=r+(rn/rr)*p;rr=rn
    return x

def shared(A,b,shifts,k):
    L=len(shifts);X=np.zeros((L,len(b)));P=np.tile(b,(L,1));r=b.copy()
    rr=r@r;aprev=1.;bprev=0.;z=np.ones(L);zp=z.copy()
    for _ in range(k):
        Ap=A@P[0]+shifts[0]*P[0];alpha=rr/(P[0]@Ap)
        X[0]+=alpha*P[0];r-=alpha*Ap;rn=r@r;beta=rn/rr
        for l in range(1,L):
            den=alpha*bprev*(zp[l]-z[l])+zp[l]*aprev*(1+(shifts[l]-shifts[0])*alpha)
            zn=z[l]*zp[l]*aprev/den;ratio=zn/z[l]
            X[l]+=alpha*ratio*P[l];P[l]=beta*ratio**2*P[l]+zn*r
            zp[l],z[l]=z[l],zn
        P[0]=r+beta*P[0];rr=rn;aprev=alpha;bprev=beta
    return X

rng=np.random.default_rng(17);J=rng.normal(size=(40,12));A=J.T@J+np.eye(12);b=rng.normal(size=12)
shifts=np.array([.01,.1,1.,10.,100.]);X=shared(A,b,shifts,5)
error=max(np.linalg.norm(x-cg(A,b,s,5)) for x,s in zip(X,shifts));assert error<1e-12,error
# A simple nonlinear least-squares analogue, not a BAL benchmark.
f=lambda c,p:.5*(c*c+(p*p-1)**2)
c,p=1.,.1;cost=f(c,p);dp=(1-p*p)/(2*p)
camera_only=[f(c-c/(1+s),p+dp) for s in shifts]
full_damped=[f(c-c/(1+s),p+dp/(1+s)) for s in shifts]
assert all(v>cost for v in camera_only)
assert min(full_damped)<cost
# Full point damping changes off-diagonal Schur entries, not just a scalar shift.
U=A[:4,:4];W=A[:4,4:];V=A[4:,4:];gp=b[4:];gc=b[:4];D=np.diag(np.diag(V))
def reduced(tau):
    return U-W@np.linalg.solve(V+tau*D,W.T),gc-W@np.linalg.solve(V+tau*D,gp)
S0,b0=reduced(.001);S1,b1=reduced(.1);delta=S1-S0
assert np.linalg.norm(delta-np.diag(np.diag(delta)))>1e-4
assert np.linalg.norm(b1-b0)>1e-4
print(json.dumps(dict(shared_independent_error=error,initial_cost=cost,camera_only_costs=camera_only,full_damped_costs=full_damped,schur_offdiagonal_change=float(np.linalg.norm(delta-np.diag(np.diag(delta)))),rhs_change=float(np.linalg.norm(b1-b0))),indent=2))
