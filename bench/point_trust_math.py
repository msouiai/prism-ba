#!/usr/bin/env python3
"""Independent dense checks of the identities used by point-trust feedback."""
import json,pathlib,numpy as np
rng=np.random.default_rng(20260907);errors=[];brackets=[]
for _ in range(200):
 J=rng.normal(size=(20,7));H=J.T@J;g=rng.normal(size=7);U=H[:4,:4];G=H[:4,4:];V=H[4:,4:];Dc=np.diag(np.diag(U));Dp=np.diag(np.maximum(np.diag(V),1e-3*np.trace(V)/3));lam=10**rng.uniform(-4,2);tau=10**rng.uniform(-7,2)
 Vt=V+tau*Dp;S=U-G@np.linalg.solve(Vt,G.T);b=g[:4]-G@np.linalg.solve(Vt,g[4:]);xc=rng.normal(size=4);xp=np.linalg.solve(Vt,g[4:]-G.T@xc);x=np.r_[xc,xp]
 full=g@x-.5*x@H@x;red=b@xc-.5*xc@(S+lam*Dc)@xc+.5*g[4:]@np.linalg.solve(Vt,g[4:]);corrected=red+.5*lam*xc@Dc@xc+.5*tau*xp@Dp@xp
 errors.append(abs(full-corrected)/max(1,abs(full)))
 # Conditional norm: dense eigenbasis independently certifies the bracket.
 di=np.sqrt(np.diag(Dp));W=V/di[:,None]/di[None,:];w,Q=np.linalg.eigh(W);z=di*xp;zh=Q.T@z;alpha=2.**(-int(rng.integers(1,9)))
 ratio=lambda t:np.linalg.norm(zh*(w+tau)/(w+t))/np.linalg.norm(zh)
 lo=tau/alpha;hi=(tau+3)/alpha-3
 assert w.min()>-1e-12 and w.max()<=3+1e-12
 assert ratio(lo)>=alpha*(1-1e-10) and ratio(hi)<=alpha*(1+1e-10)
 ts=np.geomspace(tau,hi,30);rs=[ratio(t) for t in ts];assert all(b<=a+1e-12 for a,b in zip(rs,rs[1:]))
 brackets.append([ratio(lo)/alpha,ratio(hi)/alpha])
assert max(errors)<1e-10
# Distinct eigendirections require different damping changes to scale equally.
required=(np.array([1.,10.])+0.1)/0.25-np.array([1.,10.]);assert required[0]!=required[1]
# Large camera damping leaves the conditional point relaxation, not zero.
J=rng.normal(size=(20,7));H=J.T@J;g=rng.normal(size=7);A=H.copy();A[:4,:4]+=1e12*np.eye(4);A[4:,4:]+=0.2*np.eye(3);x=np.linalg.solve(A,g);limit=np.linalg.solve(H[4:,4:]+.2*np.eye(3),g[4:]);assert np.linalg.norm(x[:4])<1e-9 and np.linalg.norm(x[4:]-limit)<1e-9
out=dict(cases=200,max_full_prediction_identity_error=max(errors),conditional_norm_brackets='all pass',monotonicity='all pass',scalar_damping_counterexample=required.tolist(),camera_limit='nonzero point relaxation verified')
pathlib.Path('/workspace/prism-point-trust/math-tests.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
