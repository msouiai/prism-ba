#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P.parent/'nonlinear'));import model as m
D=P/'evidence/toy'
def create():
    D.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(12092026);nc,np_=12,32
    R=Rotation.from_rotvec(.04*rng.normal(size=(nc,3))).as_matrix();C=rng.normal(size=(nc,3));t=-np.einsum('nij,nj->ni',R,C)
    X=rng.normal(size=(np_,3));X[:,2]-=9;intr=np.tile([600.,.02,0.],(nc,1));camera=m.charts.CameraState(R,t,intr)
    pi=np.repeat(np.arange(np_),4);ci=(pi+np.tile([0,1,4,7],np_))%nc;uv=m.audit._residual(camera,X[pi],ci,np.zeros((len(ci),2)))[0]+rng.normal(size=(len(ci),2))*.1
    for name,array in dict(R=R,t=t,X=X,intr=intr.T,E=rng.uniform(.6,1.3,size=(nc,9)),Cdiag=rng.uniform(.1,2,size=(np_,3)),uv=uv).items():np.asarray(array,dtype='<f8').tofile(D/(name+'.f64'))
    ci.astype('<i4').tofile(D/'ci.i32');pi.astype('<i4').tofile(D/'pi.i32');(D/'dims.txt').write_text(f'{nc} {np_} {len(ci)}\n')
def check():
    nc,np_,no=map(int,(D/'dims.txt').read_text().split());load=lambda n,shape:np.fromfile(D/(n+'.f64'),dtype='<f8').reshape(shape)
    camera=m.charts.CameraState(load('R',(nc,3,3)),load('t',(nc,3)),load('intr',(3,nc)).T);X=load('X',(np_,3));E=load('E',(nc,9));Dp=load('Cdiag',(np_,3));uv=load('uv',(no,2))
    ci=np.fromfile(D/'ci.i32',dtype='<i4');pi=np.fromfile(D/'pi.i32',dtype='<i4');labels=np.fromfile(D/'labels.i32',dtype='<i4');points=np.fromfile(D/'points.i32',dtype='<i4')
    independent_labels,_=m.geometry.cluster_centers(camera.centers(),8);assert np.array_equal(labels,independent_labels);assert np.array_equal(points,m.anchors(ci,pi,np_,labels))
    ranks=np.fromfile(D/'ranks.i32',dtype='<i4');offset=np.fromfile(D/'offset.i32',dtype='<i4');T=load('T',(8,7,7));mu=load('mu',(8,3));rank=int(offset[-1]);meta=m.geometry.read_metadata(D/'metadata.txt')
    blocks=[dict(cluster=k,cameras=np.flatnonzero(labels==k),points=np.flatnonzero(points==k),mu=mu[k],rank=int(ranks[k]),offset=int(offset[k]),T=T[k,:,:ranks[k]]) for k in range(8)]
    # Metric equivalence is invariant to arbitrary SVD basis signs/rotations.
    metricerr=0.
    for b in blocks:
        ids,ip=b['cameras'],b['points'];bc=m.native_camera_basis(camera.R[ids],camera.centers()[ids],b['mu'])/E[ids,:,None]
        bp=m.passenger_basis(X[ip],b['mu'])*np.sqrt(Dp[ip,:,None]);raw=np.vstack((bc.reshape(-1,7),bp.reshape(-1,7)));W=raw@b['T'];metricerr=max(metricerr,float(np.linalg.norm(W.T@W-np.eye(b['rank']))))
    native=m.normal(camera,X,ci,pi,uv,labels,points,blocks,rank,dense=True);H=load('H',(rank,rank));g=load('g',(rank,))
    herr=np.linalg.norm(H-native['H'])/np.linalg.norm(native['H']);gerr=np.linalg.norm(g-native['g'])/np.linalg.norm(native['g'])
    q=load('q',(8,7));moved,newX=m.transform(camera,X,labels,points,blocks,q);got=m.charts.CameraState(load('newR',(nc,3,3)),load('newt',(nc,3)),camera.intrinsics);gotX=load('newX',(np_,3))
    movement=max(np.max(np.abs(moved.R-got.R)),np.max(np.abs(moved.t-got.t)),np.max(np.abs(newX-gotX)))
    scores=m.score(camera,X,got,gotX,ci,pi,uv,labels,points);costerr=max(abs(scores['score_init']-meta['cost']),abs(scores['cost']-meta['newcost']))/max(1.,scores['cost'])
    own,ownrank=m.fixed_metric(camera,X,E,Dp,labels,points);assert ownrank==rank
    assert max(herr,gerr,metricerr,costerr)<1e-10 and movement<1e-11 and scores['same_cluster_max_pixel_drift']<1e-9
    report=dict(passed=True,rank=rank,camera_memberships_match=True,anchors_match=True,joint_metric_error=metricerr,normal_relative_error=float(herr),gradient_relative_error=float(gerr),action_absolute_error=float(movement),full_cost_relative_error=costerr,same_cluster_max_pixel_drift=scores['same_cluster_max_pixel_drift'],all_original_observations_scored=True)
    (P/'toy_verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--create',action='store_true');a=p.parse_args();create() if a.create else check()
