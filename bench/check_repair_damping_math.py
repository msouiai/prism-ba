#!/usr/bin/env python3
"""Independent algebra and counterexamples for repaired-step model feedback."""
import numpy as np,json,pathlib
rng=np.random.default_rng(827);maxerr=0;wrong=[]
for i in range(1000):
 J=rng.normal(size=(17,18));r=rng.normal(size=17);d=rng.normal(size=18);alpha=float(rng.choice([.125,.5,1.]));z=d.copy();z[:9]*=alpha;z[9:]*=np.repeat(rng.choice([0.,.125,1.],3),3)
 g=J.T@r;H=J.T@J;pred=-g@z-.5*z@H@z;actual=.5*(r@r-(r+J@z)@(r+J@z));err=abs(pred-actual)/max(1,abs(actual));maxerr=max(maxerr,err);assert err<1e-12
 original=-g@d-.5*d@H@d;wrong.append(abs(original-pred))
# Same current residual, gradient, GN matrix and full-step rho, different block error.
# Residual vectors [3-a-b, sqrt(2)*a^2] and [3-a-b,sqrt(2)*b^2].
def F(a,b,which):return .5*(3-a-b)**2+(a if which=='camera' else b)**4
case=dict(initial=F(0,0,'camera'),full_camera_error=F(1,1,'camera'),full_point_error=F(1,1,'point'),camera_only=[F(1,0,w) for w in ['camera','point']],point_only=[F(0,1,w) for w in ['camera','point']],prediction=4.)
assert case['full_camera_error']==case['full_point_error'];case['rho']=(case['initial']-case['full_camera_error'])/case['prediction'];assert case['camera_only'][0]!=case['camera_only'][1]
h=1e-6;rr=1-h+1000*h*h;tiny=dict(step=-h,prediction=h-.5*h*h,actual=.5-.5*rr*rr,full_step_cost=500000.);tiny['rho']=tiny['actual']/tiny['prediction'];assert tiny['rho']>.99
result=dict(affine_identity_cases=1000,max_relative_error=maxerr,original_prediction_median_absolute_error=float(np.median(wrong)),block_identifiability_counterexample=case,tiny_step_counterexample=tiny)
p=pathlib.Path('/workspace/prism-repair-damping/math-tests.json');p.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
