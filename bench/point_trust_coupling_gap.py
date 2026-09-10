#!/usr/bin/env python3
"""Measure the exact conditional guarantee's gap to a recoupled solve."""
import numpy as np,json,pathlib
rng=np.random.default_rng(311);rows=[];worst=None
for i in range(500):
 J=rng.normal(size=(8,7));H=J.T@J;U=H[:4,:4];G=H[:4,4:];V=H[4:,4:];D=np.diag(np.diag(V));Dc=np.diag(np.diag(U));tau=10**rng.uniform(-5,0);lam=10**rng.uniform(-5,0);x=rng.normal(size=7);M=H.copy();M[:4,:4]+=lam*Dc;M[4:,4:]+=tau*D;g=M@x;pp=x[4:];h=(V+tau*D)@pp;alpha=.125
 norm=lambda p:np.sqrt(p@D@p)
 lo=tau/alpha;hi=(tau+3)/alpha-3
 for k in range(60):
  mid=np.sqrt(lo*hi);q=np.linalg.solve(V+mid*D,h)
  if norm(q)/norm(pp)>alpha:lo=mid
  else:hi=mid
 Mn=M.copy();Mn[4:,4:]+=(hi-tau)*D;y=np.linalg.solve(Mn,g);ratio=norm(y[4:])/norm(pp)
 # Recomputing Schur equilibration changes camera damping as well.
 S=lambda t:U-G@np.linalg.solve(V+t*D,G.T)
 Mc=H.copy();Mc[:4,:4]+=lam*np.diag(np.diag(S(tau)));Mc[4:,4:]+=tau*D;gc=Mc@x
 Mc[:4,:4]+=lam*np.diag(np.diag(S(hi)-S(tau)));Mc[4:,4:]+=(hi-tau)*D;yc=np.linalg.solve(Mc,gc);ratio_changing=norm(yc[4:])/norm(pp)
 row=dict(case=i,conditional_tau=hi,old_tau=tau,coupled_ratio=ratio,changing_metric_ratio=ratio_changing,target=alpha);rows.append(row)
 if worst is None or ratio_changing>worst['changing_metric_ratio']:worst=dict(row,H=H.tolist(),x=x.tolist(),lambda_=lam)
r=pathlib.Path('/workspace/prism-point-trust');summary=dict(cases=len(rows),fixed_metric_violations=sum(x['coupled_ratio']>.125*(1+1e-8) for x in rows),changing_metric_violations=sum(x['changing_metric_ratio']>.125*(1+1e-8) for x in rows),median_coupled_contraction=float(np.median([x['coupled_ratio'] for x in rows])),worst=worst)
(r/'coupling-gap.json').write_text(json.dumps(dict(summary=summary,rows=rows),indent=2,default=lambda x:x.item()));print(json.dumps({k:v for k,v in summary.items() if k!='worst'},indent=2,default=lambda x:x.item()));print('worst ratios',worst['coupled_ratio'],worst['changing_metric_ratio'])
