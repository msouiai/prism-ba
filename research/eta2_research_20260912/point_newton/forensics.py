#!/usr/bin/env python3
"""Descriptive audit of the unchanged registered Ladybug failure; no new arm."""
import hashlib
import json
from pathlib import Path
import numpy as np
from core import ROOT,CHART,evaluate,residual_hessian_Y
from audit_capture import load_capture_state,map_f64,sanitize

P=Path(__file__).resolve().parent


def main():
    capture=ROOT/'evidence/collect/ladybug-1197-capture-0'
    cameras,X,meta=load_capture_state(capture)
    ci,pi,uv,dims=CHART.load_observations('/workspace/bal/ladybug-1197.txt')
    full=map_f64(capture/'eta2-0.step',(9*dims[0]+3*dims[1],));dc=full[:9*dims[0]].reshape(dims[0],9)
    centers=cameras.centers();radius=float(np.max(np.linalg.norm(centers-np.mean(centers,axis=0),axis=1)))
    a=evaluate(cameras,X,ci,pi,uv,dc,meta['lambda'],tau=meta['lambda'],scene_radius=radius)
    rows=[json.loads(x) for x in (P/'results/rows.jsonl').read_text().splitlines()]
    registered=next(r for r in rows if r['scene']=='ladybug-1197' and r['capture_rep']==0 and r['camera_direction']=='eta2' and r['rep']==0)
    assert abs(a['costs']['full']/registered['cost']-1)<1e-12
    track=a['costs_per_track']['full'];rank=np.lexsort((np.arange(len(X)),-track))
    proposed=cameras.retract(dc);Xnew=CHART.euclidean_from_homogeneous(a['H_candidate'])
    detail=[]
    for j in rank[:20]:
        which=np.flatnonzero(pi==j);cc=ci[which];pp=pi[which]
        r,Jc,Jp,Y0=CHART.observation_jacobians(cameras,a['chart'].H,a['chart'].T,cc,pp,uv[which])
        Y1=np.einsum('nij,nj->ni',proposed.R[cc],Xnew[pp])+proposed.t[cc]
        H=residual_hessian_Y(Y0,cameras.intrinsics[cc],r)
        RR=cameras.R[cc];N=np.sum(RR.transpose(0,2,1)@H@RR,axis=0)
        V=a['point_normal'][j];damp=a['point_damping'][j]
        metric=1/np.sqrt(damp/meta['lambda']);candidate=V+N+np.diag(damp)
        eig=np.linalg.eigvalsh(candidate*metric[:,None]*metric[None,:])
        u=-Y1[:,:2]/Y1[:,2,None]
        distortion=1+proposed.intrinsics[cc,1]*np.einsum('ni,ni->n',u,u)
        detail.append(dict(point=int(j),observations=len(which),fallback=bool(a['masks']['fallback'][j]),
            cost_initial=a['costs_per_track']['initial'][j],cost_candidate=track[j],
            fraction_candidate_cost=track[j]/a['costs']['full'],
            camera_only_cost=a['costs_per_track']['camera_only'][j],point_only_cost=a['costs_per_track']['point_only'][j],
            camera_indices=cc.tolist(),depth_before=Y0[:,2].tolist(),depth_after=Y1[:,2].tolist(),
            minimum_abs_depth_ratio=float(np.min(np.abs(Y1[:,2]/Y0[:,2]))),
            euclidean_point_displacement=float(a['euclidean_displacement'][j]),scene_radius=radius,
            damped_whitened_eigenvalues=eig.tolist(),spd_margin_ratio=float(eig[0]/np.max(np.abs(eig))),
            maximum_candidate_bearing_norm=float(np.max(np.linalg.norm(u,axis=1))),
            maximum_absolute_radial_distortion=float(np.max(np.abs(distortion))),
            point_hybrid_model_error=a['model_error_hybrid_per_track']['point'][j]))
    result=dict(scope='Post-grid descriptive replay of the identical Ladybug0/Eta2 conditional point-Newton candidate; no new config or benchmark row',
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        registered_candidate_cost=registered['cost'],replayed_candidate_cost=a['costs']['full'],
        top1_fraction=float(track[rank[0]]/a['costs']['full']),
        top5_fraction=float(np.sum(track[rank[:5]],dtype=np.longdouble)/a['costs']['full']),
        top200_fraction=float(np.sum(track[rank[:200]],dtype=np.longdouble)/a['costs']['full']),
        top_tracks=detail)
    (P/'results/failure_forensics.json').write_text(json.dumps(sanitize(result),indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='top_tracks'},indent=2))
    print(json.dumps(sanitize(detail[0]),indent=2))


if __name__=='__main__':main()
