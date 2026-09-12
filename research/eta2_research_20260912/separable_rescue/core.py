"""FP64 separable point/camera rescues of one prescribed Euclidean direction."""
from pathlib import Path
import sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'charts'));sys.path.insert(0,str(ROOT/'analysis'))
# Avoid this module's name shadowing charts/reference.py when imported directly.
import importlib.util
spec=importlib.util.spec_from_file_location('chart_reference_separable',ROOT/'charts/reference.py')
chart=importlib.util.module_from_spec(spec);sys.modules[spec.name]=chart;spec.loader.exec_module(chart)
CameraState=chart.CameraState


def residual(cameras,points,ci,uv):
    Y=np.einsum('nij,nj->ni',cameras.R[ci],points)+cameras.t[ci]
    return chart.project_jacobian(Y,cameras.intrinsics[ci])[0]-uv,Y


def block_cost(cameras,X,ci,pi,uv,block='point',chunk=50000):
    n=len(X) if block=='point' else len(cameras.R)
    result=np.zeros(n)
    for s in range(0,len(ci),chunk):
        sl=slice(s,s+chunk);c=ci[sl];p=pi[sl]
        r,_=residual(cameras,X[p],c,uv[sl])
        with np.errstate(over='ignore',invalid='ignore'):
            cost=.5*np.einsum('ni,ni->n',r,r)
        cost=np.where(np.isfinite(cost),cost,np.inf)
        result+=np.bincount(p if block=='point' else c,weights=cost,minlength=n)
    return result


def choose_points(proposed,X,dp,ci,pi,uv,fractions):
    fractions=sorted(set(fractions),reverse=True)
    if not fractions or fractions[0]!=1. or fractions[-1]!=0. or any(a<0 or a>1 for a in fractions):
        raise ValueError('fractions must include 0 and 1 and stay in [0,1]')
    alpha=np.ones(len(X));best=block_cost(proposed,X+dp,ci,pi,uv)
    for value in fractions[1:]:
        costs=block_cost(proposed,X+value*dp,ci,pi,uv)
        use=costs<best  # strict; larger fractions and full win exact ties
        alpha[use]=value;best[use]=costs[use]
    return alpha,best


def choose_cameras(old,proposed,chosen_X,ci,pi,uv):
    moved=block_cost(proposed,chosen_X,ci,pi,uv,'camera')
    kept=block_cost(old,chosen_X,ci,pi,uv,'camera')
    keep=kept<moved
    return ~keep,np.where(keep,kept,moved)


def choose_arm(cameras,X,dc,dp,ci,pi,uv,arm):
    start=time.perf_counter();proposed=cameras.retract(dc)
    fractions=(0.,.25,.5,1.) if arm=='point_fractions' else (0.,1.)
    if arm not in ('binary','point_fractions','point_then_camera'):raise ValueError('unknown arm')
    alpha,point_cost=choose_points(proposed,X,dp,ci,pi,uv,fractions)
    selected_dp=alpha[:,None]*dp;point_seconds=time.perf_counter()-start
    camera_start=time.perf_counter();move=np.ones(len(dc),bool)
    if arm=='point_then_camera':move,selected_cost=choose_cameras(cameras,proposed,X+selected_dp,ci,pi,uv)
    else:selected_cost=point_cost
    return dict(dc=dc*move[:,None],dp=selected_dp,alpha=alpha,camera_move=move,
                separable_cost=float(np.sum(selected_cost,dtype=np.longdouble)),
                binary_point_then_camera_cost=float(np.sum(point_cost,dtype=np.longdouble)),
                point_selection_seconds=point_seconds,camera_selection_seconds=time.perf_counter()-camera_start,
                selected_block_costs=selected_cost)


def audit(cameras,X,ci,pi,uv,dc,dp,E=None,chunk=50000):
    """Independent all-observation scoring and full original GN prediction."""
    start=time.perf_counter();proposed=cameras.retract(dc)
    init=np.longdouble(0);cost=np.longdouble(0);decrease=np.longdouble(0);prediction=np.longdouble(0);scale=np.longdouble(0)
    f2b=b2f=invalid0=invalid1=0
    for s in range(0,len(ci),chunk):
        sl=slice(s,s+chunk);c=ci[sl];p=pi[sl]
        Y0=np.einsum('nij,nj->ni',cameras.R[c],X[p])+cameras.t[c]
        pixel,dY,dintr=chart.project_jacobian(Y0,cameras.intrinsics[c]);r0=pixel-uv[sl]
        r1,Y1=residual(proposed,X[p]+dp[p],c,uv[sl])
        RX=Y0-cameras.t[c]
        dYc=np.cross(dc[c,:3],RX)+dc[c,3:6]
        dYp=np.einsum('nij,nj->ni',cameras.R[c],dp[p])
        jd=np.einsum('nij,nj->ni',dY,dYc+dYp)+np.einsum('nij,nj->ni',dintr,dc[c,6:9])
        with np.errstate(over='ignore',invalid='ignore'):
            c0=.5*np.einsum('ni,ni->n',r0,r0);c1=.5*np.einsum('ni,ni->n',r1,r1)
            quad=.5*np.einsum('ni,ni->n',jd,jd)
            prediction-=np.sum(np.einsum('ni,ni->n',r0,jd)+quad,dtype=np.longdouble)
            scale+=np.sum(abs(r0*jd),dtype=np.longdouble)+np.sum(quad,dtype=np.longdouble)
            decrease-=.5*np.sum((r1-r0)*(r1+r0),dtype=np.longdouble)
        invalid0+=int(np.count_nonzero(~np.isfinite(c0)));invalid1+=int(np.count_nonzero(~np.isfinite(c1)))
        init+=np.sum(np.where(np.isfinite(c0),c0,np.inf),dtype=np.longdouble)
        cost+=np.sum(np.where(np.isfinite(c1),c1,np.inf),dtype=np.longdouble)
        f2b+=int(np.count_nonzero((Y0[:,2]<0)&(Y1[:,2]>0)))
        b2f+=int(np.count_nonzero((Y0[:,2]>0)&(Y1[:,2]<0)))
    pred=float(prediction);gain=float(decrease);rho=gain/pred if pred!=0 else float('nan')
    centers=cameras.centers();center=np.mean(centers,axis=0);radius=float(np.max(np.linalg.norm(centers-center,axis=1)))
    dist=np.linalg.norm(dp,axis=1);oldr=np.linalg.norm(X-center,axis=1);newr=np.linalg.norm(X+dp-center,axis=1)
    large=dist>radius
    scaled=None
    if E is not None:
        if np.any((E==0)&(dc!=0)):raise ValueError('nonzero step in zero scaling coordinate')
        z=np.divide(dc,E,out=np.zeros_like(dc),where=E!=0);scaled=float(np.linalg.norm(z))
    finite=all(np.isfinite(v) for v in (float(init),float(cost),gain,pred,rho))
    return dict(score_init=float(init),cost=float(cost),true_decrease=gain,prediction=pred,rho=rho,
                accepted=bool(finite and pred>0 and gain>0 and rho>.1),acceptance_rule='finite full cost, pred>0, true decrease>0, strict rho>0.1',
                prediction_absolute_term_scale=float(scale),maximum_point_displacement=float(np.max(dist)),
                scene_radius=radius,large_moves_inward=int(np.count_nonzero(large&(newr<oldr))),
                large_moves_outward=int(np.count_nonzero(large&~(newr<oldr))),
                camera_scaled_norm=scaled,front_to_behind_observations=f2b,behind_to_front_observations=b2f,
                invalid_initial_observations=invalid0,invalid_candidate_observations=invalid1,
                changed_k2_entries=int(np.count_nonzero(dc[:,8])),cpu_scoring_audit_seconds=time.perf_counter()-start)
