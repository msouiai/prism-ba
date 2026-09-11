"""New view-diverse cases; no candidate-specific selection or tuning."""
import numpy as np
from paths import ROOT
from geometry import State,exp_so3,project
from reference_ba import valid_cost

def orbit_case(seed,family,nc=8,np_=120):
    rng=np.random.default_rng(seed)
    half=.025 if family=='low_parallax' else .55
    angle=np.linspace(-half,half,nc)
    center=np.array([0.,0.,-5.5])
    C=np.column_stack([5.5*np.sin(angle),.35*np.sin(2*angle),5.5*np.cos(angle)])+center
    z=C-center;z/=np.linalg.norm(z,axis=1)[:,None]
    x=np.cross(np.tile([0.,1.,0.],(nc,1)),z);x/=np.linalg.norm(x,axis=1)[:,None]
    y=np.cross(z,x);R=np.stack([x,y,z],axis=1)
    X=rng.uniform([-1.1,-.7,-6.8],[1.1,.7,-4.2],size=(np_,3))
    truth=State(R,-np.einsum('nij,nj->ni',R,C),X,np.tile([500.,0.,0.],(nc,1)))
    obs=np.array([[c,p,0.,0.] for p in range(np_) for c in sorted(rng.choice(nc,size=5,replace=False))])
    obs[:,2:]=project(truth,obs,6)[0]+rng.normal(0,.2,size=(len(obs),2))
    initial=truth.copy()
    if family in ['depth','low_parallax']:
        initial.X=C[0]+(initial.X-C[0])*np.exp(rng.normal(0,.45,size=np_))[:,None]
        rotation=.025
    elif family=='joint':
        initial.X+=rng.normal(0,.15,size=initial.X.shape);rotation=.12
    else:raise ValueError(family)
    initial.R=exp_so3(rng.normal(0,rotation,size=(nc,3)))@initial.R
    perturbed_C=C+rng.normal(0,.02,size=C.shape)
    initial.t=-np.einsum('nij,nj->ni',initial.R,perturbed_C)
    initial.R[0]=truth.R[0];initial.t[0]=truth.t[0];initial.X[0,2]=truth.X[0,2]
    assert np.isfinite(valid_cost(initial,obs)),(family,seed,'invalid registered initial case')
    return truth,initial,obs
