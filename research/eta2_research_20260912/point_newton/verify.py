#!/usr/bin/env python3
"""Analytic residual-Hessian and registered fallback verification; CPU only."""
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from core import CHART,residual_hessian_Y,select_blocks,conditional_point_newton

P=Path(__file__).resolve().parent


def main():
    baseline=CHART.verify_frozen_baseline();rng=np.random.default_rng(20260912)
    n=64;R=Rotation.random(n,random_state=rng).as_matrix();t=rng.normal(size=(n,3))
    Y=rng.normal(scale=.5,size=(n,3));Y[:,2]=rng.uniform(1,8,size=n)*rng.choice([-1,1],size=n)
    X=np.einsum('nji,nj->ni',R,Y-t)
    intr=np.column_stack([rng.uniform(100,1500,size=n),rng.uniform(-.2,.2,size=n),np.zeros(n)])
    r=rng.normal(scale=30,size=(n,2));pixel,dY,_=CHART.project_jacobian(Y,intr);obs=pixel-r
    H_Y=residual_hessian_Y(Y,intr,r);H_X=R.transpose(0,2,1)@H_Y@R
    fd=np.zeros_like(H_X);full_fd=np.zeros_like(H_X)
    for a in range(3):
        step=2e-5*np.maximum(1,np.abs(X[:,a]));d=np.zeros_like(X);d[:,a]=step
        Ys=[np.einsum('nij,nj->ni',R,X+sgn*d)+t for sgn in (1,-1)]
        grads=[];fullgrads=[]
        for yy in Ys:
            pp,jy,_=CHART.project_jacobian(yy,intr);jp=jy@R
            grads.append(np.einsum('nji,nj->ni',jp,r))
            fullgrads.append(np.einsum('nji,nj->ni',jp,pp-obs))
        fd[:,:,a]=(grads[0]-grads[1])/(2*step[:,None])
        full_fd[:,:,a]=(fullgrads[0]-fullgrads[1])/(2*step[:,None])
    contraction_error=np.linalg.norm(fd-H_X,axis=(1,2))/np.maximum(np.linalg.norm(H_X,axis=(1,2)),1e-300)
    Jp=dY@R;full=Jp.transpose(0,2,1)@Jp+H_X
    full_error=np.linalg.norm(full_fd-full,axis=(1,2))/np.maximum(np.linalg.norm(full,axis=(1,2)),1e-300)
    assert np.max(contraction_error)<3e-7,np.max(contraction_error)
    assert np.max(full_error)<3e-7,np.max(full_error)
    assert np.array_equal(residual_hessian_Y(Y,intr,np.zeros_like(r)),np.zeros_like(H_Y))
    V=np.repeat(np.eye(3)[None],5,axis=0);N=np.zeros_like(V)
    N[0]=-2*np.eye(3);N[1]=-1.05*np.eye(3);N[2,0,0]=np.nan
    N[3]=-np.eye(3);N[4]=.1*np.eye(3)
    damping=np.full((5,3),.1);selected=select_blocks(V,N,damping,.1)
    assert selected['fallback'].tolist()==[True,False,True,False,False]
    assert selected['raw_indefinite'].tolist()==[True,True,False,False,False]
    assert np.array_equal(selected['matrix'][selected['fallback']],1.1*V[selected['fallback']])
    assert np.array_equal(selected['active_N'][selected['fallback']],np.zeros((2,3,3)))
    b=rng.normal(size=(5,3));actual=np.linalg.solve(selected['matrix'],b[...,None])[...,0]
    control=np.linalg.solve(1.1*V,b[...,None])[...,0]
    assert np.array_equal(actual[selected['fallback']],control[selected['fallback']])
    nc,np_=3,12
    cameras=CHART.CameraState(R[:nc],t[:nc],intr[:nc])
    points=X[:np_];ci=np.tile(np.arange(nc),np_);pi=np.repeat(np.arange(np_),nc)
    pc=CHART.make_chart(points,cameras,'euclidean')
    zero=np.zeros((len(ci),2))
    uv=CHART.observation_jacobians(cameras,pc.H,pc.T,ci,pi,zero)[0]
    dc=rng.normal(scale=1e-4,size=(nc,9));dc[:,8]=0
    gn=CHART.conditional_point_solve(cameras,points,ci,pi,uv,dc,.1)
    pn=conditional_point_newton(cameras,points,ci,pi,uv,dc,.1)
    assert np.array_equal(gn['point_normal'],pn['point_normal'])
    assert np.array_equal(gn['point_damping'],pn['point_damping'])
    assert np.array_equal(gn['delta'],pn['delta'])
    assert not np.any(pn['masks']['fallback'])
    result=dict(status='passed',seed=20260912,baseline=baseline,
      finite_difference_projections=n,max_residual_contraction_relative_error=float(np.max(contraction_error)),
      max_full_objective_hessian_relative_error=float(np.max(full_error)),
      zero_residual_exact_gn_parity=True,zero_residual_points=np_,
      fallback_exact_gn_parity=True,damped_spd_can_accept_raw_indefinite=True,
      nonfinite_newton_block_falls_back=True,gpu_used=False)
    (P/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='baseline'},indent=2))


if __name__=='__main__':main()
