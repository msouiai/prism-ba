import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import numpy as np
from paths import ROOT,write_json
from cases import orbit_case
from reference_ba import Linearization
from geometry import project
from joint_paths import candidate
from path_solver import solve
from lm_checkpoints import solve as prior

rows=[]
for family in ['depth','joint','low_parallax']:
    truth,s,obs=orbit_case(590,family);before=s.copy();lin=Linearization(s,obs);dc,dp=lin.factor(.1).solve()
    for arm in ['moving_host','virtual_ray']:
        zero,_=candidate(s,lin,dc,dp,.1,arm,alpha=0)
        zero_error=np.linalg.norm(zero.X-s.X)
        assert zero_error<1e-10,(family,arm,zero_error)
        eps=1e-4
        plus,_=candidate(s,lin,dc,dp,.1,arm,alpha=eps)
        minus,_=candidate(s,lin,dc,dp,.1,arm,alpha=-eps)
        err=np.linalg.norm((plus.X-minus.X)/(2*eps)-dp)/max(np.linalg.norm(dp),1.)
        assert err<1e-6,(family,arm,err)
        assert plus.X[0,2]==s.X[0,2] and np.array_equal(plus.R[0],s.R[0])
        rows.append({'family':family,'arm':arm,'zero_point_error':zero_error,'tangent_relative_error':err})
    anchored,_=candidate(s,lin,np.zeros_like(dc),dp,.1,'anchored',alpha=.1)
    moving,_=candidate(s,lin,np.zeros_like(dc),dp,.1,'moving_host',alpha=.1)
    np.testing.assert_allclose(anchored.X,moving.X,rtol=1e-13,atol=1e-13)
    changed=obs.copy();changed[:,2:]+=123.;lin2=Linearization(s,changed)
    v1,_=candidate(s,lin,dc,dp,.1,'virtual_ray')
    v2,_=candidate(s,lin2,dc,dp,.1,'virtual_ray')
    np.testing.assert_array_equal(v1.X,v2.X)
    for name in ['R','t','X','intr']:np.testing.assert_array_equal(getattr(s,name),getattr(before,name))
    b,rb,_=prior(s,obs,-1,max_attempts=8);a,ra,_=solve(s,obs,-1,max_attempts=8)
    assert ra['cost']==rb['cost'] and ra['lambda']==rb['lambda']
    for name in ['R','t','X','intr']:np.testing.assert_array_equal(getattr(a,name),getattr(b,name))
write_json(ROOT/'ray_checks.json',{'passed':True,'rows':rows,'observed_pixels_not_used_by_virtual_target':True,
    'fixed_host_reduces_to_old_anchor':True,'unchanged_parent_and_gauge':True,'xyz_matches_prior_exactly':True})
print('joint paths: algebra/gauge/target-independence/XYZ baseline PASS')
