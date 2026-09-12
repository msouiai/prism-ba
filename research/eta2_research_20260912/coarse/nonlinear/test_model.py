#!/usr/bin/env python3
"""Meaningful correctness gates before registered witness evaluations."""
import json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
import model as m

def tests():
    rng=np.random.default_rng(920129);nc=4;np_=15
    R=Rotation.from_rotvec(rng.normal(size=(nc,3))*.06).as_matrix();C=rng.normal(size=(nc,3))*.4
    t=-np.einsum('nij,nj->ni',R,C);intr=np.tile([700.,.015,0.],(nc,1));camera=m.charts.CameraState(R,t,intr)
    X=rng.normal(size=(np_,3));X[:,2]-=7
    labels=np.array([0,0,1,1]);ci=np.tile(np.arange(nc),np_-1);pi=np.repeat(np.arange(np_-1),nc)
    # Original observation order controls anchors; alternating anchor clusters.
    ci=ci.reshape(-1,4);ci[1::2]=ci[1::2][:,[2,3,0,1]];ci=ci.reshape(-1)
    uv=np.zeros((len(ci),2));r,*_=m.audit._residual(camera,X[pi],ci,uv);uv=r+rng.normal(size=r.shape)*.3
    membership=m.anchors(ci,pi,np_,labels)
    assert np.array_equal(membership[:-1],np.arange(np_-1)%2) and membership[-1]==-1
    E=rng.uniform(.8,1.2,size=(nc,9));Dp=rng.uniform(.1,1.,size=(np_,3))
    blocks,rank=m.fixed_metric(camera,X,E,Dp,labels,membership)
    assert rank==14
    q=rng.normal(size=(2,7))*.03;moved,movedX=m.transform(camera,X,labels,membership,blocks,q)
    direct_error=0.
    for b,a in zip(blocks,q):
        ids=b['cameras'];Q=Rotation.from_rotvec(a[:3]).as_matrix();Cc=b['mu']+np.exp(a[6])*((C[ids]-b['mu'])@Q.T)+a[3:6]
        tt=-np.einsum('nij,nj->ni',moved.R[ids],Cc)
        direct_error=max(direct_error,float(np.linalg.norm(tt-moved.t[ids])))
    assert np.array_equal(movedX[-1],X[-1])
    initial,*_=m.audit._residual(camera,X[pi],ci,uv);after,*_=m.audit._residual(moved,movedX[pi],ci,uv)
    internal=labels[ci]==membership[pi];invariance=float(np.max(np.abs(initial[internal]-after[internal])))
    assert invariance<1e-9 and direct_error<1e-12
    normal=m.normal(camera,X,ci,pi,uv,labels,membership,blocks,rank,chunk=11,dense=True)
    J=normal['J'];g=J.T@initial.reshape(-1);H=J.T@J
    normal_error=float(np.linalg.norm(H-normal['H'])/np.linalg.norm(H));gradient_error=float(np.linalg.norm(g-normal['g'])/np.linalg.norm(g))
    assert normal_error<1e-12 and gradient_error<1e-12
    # Independently use the native camera tangent and Euclidean point tangent.
    hh=np.column_stack((X,np.ones(np_)));pt=np.zeros((np_,4,3));pt[:,:3,:]=np.eye(3)
    rr,Jc,Jp,Y=m.charts.observation_jacobians(camera,hh,pt,ci,pi,uv)
    raw_camera=np.zeros((nc,9,rank));raw_point=np.zeros((np_,3,rank))
    for b in blocks:
        sl=slice(b['offset'],b['offset']+b['rank']);ids=b['cameras'];ip=b['points']
        raw_camera[ids,:,sl]=m.native_camera_basis(R[ids],C[ids],b['mu'])@b['T']
        raw_point[ip,:,sl]=m.passenger_basis(X[ip],b['mu'])@b['T']
    independent=(Jc@raw_camera[ci]+Jp@raw_point[pi]).reshape(-1,rank)
    chain_error=float(np.linalg.norm(independent-J)/np.linalg.norm(J));assert chain_error<1e-12
    fd=[]
    for col in range(rank):
        y=np.eye(rank)[col];q=m.parameters(y,blocks);h=1e-6
        plus,Xplus=m.transform(camera,X,labels,membership,blocks,h*q);minus,Xminus=m.transform(camera,X,labels,membership,blocks,-h*q)
        rp,*_=m.audit._residual(plus,Xplus[pi],ci,uv);rm,*_=m.audit._residual(minus,Xminus[pi],ci,uv)
        estimate=((rp-rm)/(2*h)).reshape(-1)
        fd.append(float(np.linalg.norm(estimate-J[:,col])/max(1.,np.linalg.norm(J[:,col]))))
    assert max(fd)<1e-7
    # Finite group action and native retraction agree to first order.
    y=rng.normal(size=rank);q=m.parameters(y,blocks);errors=[]
    for h in (1e-3,5e-4):
        moved,_=m.transform(camera,X,labels,membership,blocks,h*q)
        native=camera.retract(h*np.einsum('nij,j->ni',raw_camera,y))
        errors.append(float(np.linalg.norm(native.R-moved.R)+np.linalg.norm(native.t-moved.t)))
    assert errors[1]<.27*errors[0]
    # Joint singleton scale survives when the passenger is not at its center.
    one=m.charts.CameraState(R[:1],t[:1],intr[:1]);singleton,rank1=m.fixed_metric(one,X[:2],E[:1],Dp[:2],np.zeros(1,int),np.zeros(2,int))
    assert rank1==7
    return dict(passed=True,rank=rank,singleton_joint_rank=rank1,normal_relative_error=normal_error,
                gradient_relative_error=gradient_error,chain_rule_relative_error=chain_error,finite_difference_relative_errors=fd,
                same_cluster_max_pixel_drift=invariance,direct_vs_stable_action_translation_error=direct_error,
                native_first_order_errors=errors,metric_whitening_error=max(b['whitening_error'] for b in blocks),
                unobserved_point_unchanged=True,all_observations_scored=True,
                implementation_sha256={p.name:m.geometry.sha256(p) for p in (Path(__file__),Path(m.__file__))})

if __name__=='__main__':
    result=tests();out=Path(__file__).with_name('toy_checks.json');out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
