import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import numpy as np
from paths import ROOT,write_json
from reference_ba import synthetic,Linearization
from geometry import project,retract
from projective_paths import chart_vectors,projective_retract,solve
from lm_checkpoints import solve as ordinary

checks=[]
for seed in [301,302,303]:
    _,s,obs=synthetic(seed,'depth'); before=s.copy();lin=Linearization(s,obs)
    dc,dp=lin.factor(.1).solve();dc[:]=0
    r,q,_,jp,_,_=project(s,obs,6,True)
    jpdp=np.einsum('nij,nj->ni',jp,dp[lin.pi])
    gamma=np.einsum('ij,ij->i',s.R[lin.ci,2,:],dp[lin.pi])/q[:,2]
    for arm in ['anchored','mean_view']:
        v=chart_vectors(s,lin,arm);h=np.einsum('ij,ij->i',v,dp)
        for alpha in [.1,.01,.001]:
            trial,n=projective_retract(s,dc,dp,v,alpha,margin=0.)
            assert n==0
            delta=project(trial,obs,6)[0]-r
            exact=alpha*jpdp/(1+alpha*(gamma-h[lin.pi]))[:,None]
            rel=np.linalg.norm(delta-exact)/max(np.linalg.norm(exact),1e-15)
            assert rel<1e-10,(arm,alpha,rel)
            assert trial.X[0,2]==s.X[0,2]
            checks.append({'seed':seed,'arm':arm,'alpha':alpha,'identity_relative':rel})
        trial,_=projective_retract(s,dc,dp,v,1e-6)
        tangent=np.linalg.norm((trial.X-s.X)/1e-6-dp)/np.linalg.norm(dp)
        assert tangent<1e-5
    # Construct local inverse-depth chart explicitly, including its exact tangent.
    v=chart_vectors(s,lin,'anchored');h=np.einsum('ij,ij->i',v,dp)
    first=np.full(len(s.X),len(obs),int);np.minimum.at(first,lin.pi,np.arange(len(obs)))
    cams=lin.ci[first];a=-np.einsum('nji,nj->ni',s.R[cams],s.t[cams]);ray=s.X-a
    ell=np.linalg.norm(ray,axis=1);normal=ray/ell[:,None];rho=1/ell
    drho=-np.einsum('ij,ij->i',normal,dp)/ell**2
    dnormal=(dp-normal*np.einsum('ij,ij->i',normal,dp)[:,None])/ell[:,None]
    explicit=a+(normal+.1*dnormal)/(rho+.1*drho)[:,None]
    trial,_=projective_retract(s,dc,dp,v,.1,margin=0.)
    np.testing.assert_allclose(explicit[1:],trial.X[1:],rtol=2e-14,atol=2e-14)
    linear=ell[:,None]*dnormal-normal*drho[:,None]*ell[:,None]**2
    np.testing.assert_allclose(linear,dp,rtol=2e-13,atol=2e-13)
    for name in ['R','t','X','intr']: assert np.array_equal(getattr(s,name),getattr(before,name))
    a,ra,_=ordinary(s,obs,-1,max_attempts=8)
    b,rb=solve(s,obs,-1,'xyz',max_attempts=8)
    assert ra['cost']==rb['cost'] and ra['lambda']==rb['lambda']
    for name in ['R','t','X','intr']: assert np.array_equal(getattr(a,name),getattr(b,name))
# Force a near-pole fallback; finite, exact ordinary path for that point.
v=np.zeros_like(s.X);v[1]=dp[1]/np.dot(dp[1],dp[1])
trial,n=projective_retract(s,dc,dp,v)
assert n==1
np.testing.assert_array_equal(trial.X[1],(s.X+dp)[1])
write_json(ROOT/'chart_checks.json',{'passed':True,'identity_checks':checks,
    'explicit_anchor_chart':True,'linearized_chart_equals_xyz':True,'xyz_baseline_exact':True,
    'parent_immutable':True,'gauge_preserved':True,'near_pole_fallback':True})
print('projective algebra and exact XYZ continuation: PASS')
