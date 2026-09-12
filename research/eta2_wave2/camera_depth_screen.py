"""W6c camera-only linear depth bounds, followed by honest joint scoring."""
from pathlib import Path
import importlib.util,json,sys,time
import numpy as np
P=Path(__file__).resolve().parent;C=P.parent/'eta2_research_20260912'
sys.path[:0]=[str(C/'analysis'),str(C/'coarse')]
from audit_capture import load_capture_state,CHART
from diagnostic import read_array,verify_baseline
from spectrum import point_qr,point_inverse
spec=importlib.util.spec_from_file_location('w6_rescue_score',C/'separable_rescue/core.py');S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)

def run(scene,rep):
    dest=P/'camera_depth'/f'{scene}-{rep}.json';dest.parent.mkdir(exist_ok=True)
    if dest.exists():return
    cap=C/'evidence/collect'/f'{scene}-capture-{rep}';cam,X,meta=load_capture_state(cap);nc,np_=len(cam.R),len(X)
    ci,pi,uv,_=CHART.load_observations('/workspace/bal/'+scene+'.txt')
    E=read_array(cap/'E.f64',(nc,9));diag=read_array(cap/'Cdiag.f64',(np_,3));D=np.maximum(diag,.001*np.maximum(diag.mean(axis=1),1e-32)[:,None])
    raw=-read_array(cap/'eta2_raw_scaled.f64',(nc,9));dc=raw*E
    chart=CHART.make_chart(X,cam,'euclidean');r,jc,jp,Y=CHART.observation_jacobians(cam,chart.H,chart.T,ci,pi,uv)
    _,Ri,_=point_qr(jp,pi,meta['tau']*D)
    def backsub(d):
        rc=r+np.einsum('nri,ni->nr',jc,d[ci]);v=np.einsum('nri,nr->ni',jp,rc)
        rhs=np.column_stack([np.bincount(pi,weights=v[:,k],minlength=np_) for k in range(3)])
        return -point_inverse(Ri,rhs)
    oldnorm=np.linalg.norm(raw);baseline_dc=dc*min(1,meta['radius']/oldnorm)
    rate=(np.cross(dc[ci,:3],Y-cam.t[ci])[:,2]+dc[ci,5])/Y[:,2]
    perobs=np.ones(len(ci));danger=rate<0;perobs[danger]=np.minimum(1.,.9/(-rate[danger]))
    alpha=np.ones(nc);np.minimum.at(alpha,ci,perobs);bounded_dc=dc*alpha[:,None]
    rows=[]
    for repetition in range(3):
        for arm,d in [('clipped_recomplete',baseline_dc),('camera_depth_bound',bounded_dc)]:
            dp=backsub(d);score=S.audit(cam,X,ci,pi,uv,d,dp,E);new=cam.retract(d)
            newY=np.einsum('nij,nj->ni',new.R[ci],X[pi]+dp[pi])+new.t[ci]
            ratios=newY[:,2]/Y[:,2]
            rows.append(dict(rep=repetition,arm=arm,**score,
                minimum_actual_joint_depth_ratio=float(np.min(ratios)),joint_depth_violations=int(np.count_nonzero(ratios<.1-1e-10)),
                global_radius_ratio=score['camera_scaled_norm']/meta['radius']))
    result=dict(scene=scene,capture_rep=rep,epsilon=.1,cameras_bounded=int(np.count_nonzero(alpha<1)),minimum_alpha=float(alpha.min()),
                rows=rows,scope='Conditional box-bound witness screen. Bound is on linear CAMERA-ONLY depth, not certified joint depth or the old global ball.')
    dest.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(scene,rep,'changed',result['cameras_bounded'],[(r['arm'],r['true_decrease'],r['accepted'],r['joint_depth_violations'],r['global_radius_ratio']) for r in rows[:2]],flush=True)
if __name__=='__main__':
    verify_baseline()
    for scene,rep in [('venice-52',r) for r in (0,1,2)]+[('final-3068',r) for r in (0,5,6)]+[('ladybug-1197',0)]:run(scene,rep)
