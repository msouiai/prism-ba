#!/usr/bin/env python3
"""Numerical checks of the stated block identities and toy counterexample."""
import json,numpy as np,pathlib
rng=np.random.default_rng(17);J=rng.normal(size=(12,7));H=J.T@J;g=rng.normal(size=7);A=H[:3,:3];W=H[:3,3:];V=H[3:,3:];P=V+.1*np.eye(4);Dc=np.diag([.2,1.,3.]);lam=2.
B=np.block([[A+lam*Dc,W],[W.T,P]]);direct=np.linalg.solve(B,-g);S=A-W@np.linalg.solve(P,W.T);rhs=-g[:3]+W@np.linalg.solve(P,g[3:]);dc=np.linalg.solve(S+lam*Dc,rhs);dp=-np.linalg.solve(P,g[3:]+W.T@dc)
assert np.allclose(direct,np.r_[dc,dp],rtol=1e-12,atol=1e-12)
T=np.diag(1/np.sqrt(np.diag(Dc)));assert np.allclose(T@np.linalg.solve(T@S@T+lam*np.eye(3),T@rhs),dc)
rows=[]
for eps in [.01,.001]:
 def cost(x):c,p=x;return .5*((c+p*p-1)**2+c*c)
 x=np.array([0.,eps]);r=np.array([eps*eps-1,0]);J=np.array([[1,2*eps],[1,0]]);g=J.T@r
 for damping in [1e2,1e6,1e12]:
  d=np.linalg.solve(J.T@J+np.diag([damping,0]),-g);slope=g@d
  alphas=[2.**-k for k in range(1,9)];rescue=next((alpha for alpha in alphas if cost(x+alpha*d)<=cost(x)+1e-4*alpha*slope),None)
  rows.append(dict(epsilon=eps,camera_damping=damping,camera_step=d[0],point_step=d[1],initial_cost=cost(x),full_step_cost=cost(x+d),slope=slope,rescue_alpha=rescue))
assert any(r['rescue_alpha'] is None for r in rows if r['epsilon']==.001)
assert all(r['full_step_cost']>r['initial_cost'] for r in rows)
print(json.dumps(dict(block_identity='passed',congruence_identity='passed',counterexamples=rows),indent=2))
