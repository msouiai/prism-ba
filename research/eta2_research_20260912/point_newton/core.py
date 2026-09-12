"""Brief 8 conditional point-Newton reference, fixed cameras and full objective."""
from pathlib import Path
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'analysis'))
from audit_capture import CHART


def residual_hessian_Y(Y,intr,residual):
    """Exact sum_k residual_k Hessian_Y pixel_k, holding residual fixed.

    Snavely u=-Yxy/Yz; k2 is fixed zero. There is no depth floor or loss change.
    """
    if np.any(intr[:,2]!=0):raise ValueError('k2 must remain zero')
    with np.errstate(divide='ignore',invalid='ignore',over='ignore'):
        u=-Y[:,:2]/Y[:,2,None];z=Y[:,2]
        f,k=intr[:,0],intr[:,1]
        r2=np.einsum('ni,ni->n',u,u)
        G=f[:,None,None]*((1+k*r2)[:,None,None]*np.eye(2)+
                          2*k[:,None,None]*u[:,:,None]*u[:,None,:])
        Hdist=2*(f*k)[:,None,None]*(residual[:,:,None]*u[:,None,:]+
                u[:,:,None]*residual[:,None,:]+
                np.einsum('ni,ni->n',residual,u)[:,None,None]*np.eye(2))
        Du=np.zeros((len(Y),2,3));Du[:,0,0]=-1/z;Du[:,1,1]=-1/z;Du[:,:,2]=-u/z[:,None]
        H=Du.transpose(0,2,1)@Hdist@Du
        weighted=np.einsum('ni,nij->nj',residual,G)
        H[:,0,2]+=weighted[:,0]/z**2;H[:,2,0]+=weighted[:,0]/z**2
        H[:,1,2]+=weighted[:,1]/z**2;H[:,2,1]+=weighted[:,1]/z**2
        H[:,2,2]+=2*np.einsum('ni,ni->n',weighted,u)/z**2
    return H


def point_damping(V,lam):
    diagonal=np.diagonal(V,axis1=1,axis2=2)
    floor=lam*np.sum(diagonal,axis=1)/3
    floor=np.where(floor>0,floor,1e-32)
    return np.maximum(lam*diagonal,1e-3*floor[:,None])


def select_blocks(V,N,damping,lam):
    """Exactly registered SPD rule, with unmodified damped GN fallback."""
    if not np.isfinite(V).all() or not np.isfinite(damping).all() or np.any(damping<=0):
        raise FloatingPointError('invalid GN model/damping')
    if not np.isfinite(lam) or lam<=0:raise ValueError('positive lambda required for Dp whitening')
    Dp=damping/lam;scale=1/np.sqrt(Dp)
    Hgn=V.copy()
    for a in range(3):Hgn[:,a,a]+=damping[:,a]
    raw=V+N;candidate=Hgn+N
    with np.errstate(over='ignore',invalid='ignore'):
        raw_scaled=raw*scale[:,:,None]*scale[:,None,:]
        scaled=candidate*scale[:,:,None]*scale[:,None,:]
    finite=np.isfinite(scaled).all(axis=(1,2));raw_finite=np.isfinite(raw_scaled).all(axis=(1,2))
    ev=np.full((len(V),3),np.nan);raw_ev=ev.copy()
    ev[finite]=np.linalg.eigvalsh(scaled[finite])
    raw_ev[raw_finite]=np.linalg.eigvalsh(raw_scaled[raw_finite])
    active=finite & (ev[:,0]>1e-12*np.max(np.abs(ev),axis=1))
    selected=Hgn.copy();selected[active]=candidate[active]
    active_N=np.zeros_like(N);active_N[active]=N[active]
    return dict(matrix=selected,active_N=active_N,fallback=~active,
                raw_indefinite=raw_finite & (raw_ev[:,0]<0),
                raw_material_indefinite=raw_finite & (raw_ev[:,0]<-1e-12*np.max(np.abs(raw_ev),axis=1)),
                raw_nonfinite=~raw_finite,damped_nonfinite=~finite,
                damped_min_eigenvalue=ev[:,0],raw_min_eigenvalue=raw_ev[:,0],Dp=Dp)


def conditional_point_newton(cameras,X,cam_idx,pt_idx,uv,camera_step,lam,*,
                             chart='euclidean',anchor_idx=None,tau=None,
                             chunk_size=50000,freeze_depth=None):
    if chart!='euclidean' or anchor_idx is not None or freeze_depth is not None:
        raise ValueError('only original unconstrained Euclidean point blocks')
    if tau is not None and tau!=lam:raise ValueError('no tau sweep in Brief8')
    begin=time.perf_counter();cameras.retract(camera_step)
    pc=CHART.make_chart(X,cameras,'euclidean');npt=len(X)
    V=np.zeros((npt,3,3));N=np.zeros_like(V);b=np.zeros((npt,3));score=np.longdouble(0)
    for start in range(0,len(cam_idx),chunk_size):
        sl=slice(start,start+chunk_size);ci=cam_idx[sl];pi=pt_idx[sl]
        r,Jc,Jp,Y=CHART.observation_jacobians(cameras,pc.H,pc.T,ci,pi,uv[sl])
        rc=r+np.einsum('nij,nj->ni',Jc,camera_step[ci])
        H_Y=residual_hessian_Y(Y,cameras.intrinsics[ci],r)
        R=cameras.R[ci];H_X=R.transpose(0,2,1)@H_Y@R
        score+=.5*np.sum(r*r,dtype=np.longdouble)
        for a in range(3):
            b[:,a]-=np.bincount(pi,weights=np.einsum('ni,ni->n',Jp[:,:,a],rc),minlength=npt)
            for c in range(a,3):
                V[:,a,c]+=np.bincount(pi,weights=np.einsum('ni,ni->n',Jp[:,:,a],Jp[:,:,c]),minlength=npt)
                N[:,a,c]+=np.bincount(pi,weights=H_X[:,a,c],minlength=npt)
    for a in range(3):
        for c in range(a):V[:,a,c]=V[:,c,a];N[:,a,c]=N[:,c,a]
    damping=point_damping(V,lam)
    assembly_seconds=time.perf_counter()-begin;decision_start=time.perf_counter()
    selected=select_blocks(V,N,damping,lam)
    decision_seconds=time.perf_counter()-decision_start;solve_start=time.perf_counter()
    delta=np.linalg.solve(selected['matrix'],b[...,None])[...,0]
    solve_seconds=time.perf_counter()-solve_start
    if not np.isfinite(delta).all():raise FloatingPointError('nonfinite point solution')
    residual=np.einsum('nij,nj->ni',selected['matrix'],delta)-b
    rel=float(np.linalg.norm(residual)/max(np.linalg.norm(b),1e-300))
    denom=np.linalg.norm(selected['matrix'],axis=(1,2))*np.linalg.norm(delta,axis=1)+np.linalg.norm(b,axis=1)
    backward=np.linalg.norm(residual,axis=1)/np.maximum(denom,1e-300)
    invsqrt=1/np.sqrt(selected['Dp'])
    weighted_rel=float(np.linalg.norm(residual*invsqrt)/max(np.linalg.norm(b*invsqrt),1e-300))
    half_second=.5*np.einsum('ni,nij,nj->n',delta,selected['active_N'],delta)
    return dict(chart=pc,delta=delta,H_candidate=pc.retract(delta),point_normal=V,
                point_damping=damping,linear_relative_residual=rel,
                linear_whitened_relative_residual=weighted_rel,
                maximum_point_normwise_backward_error=float(np.max(backward)),
                half_active_second_order_per_track=half_second,
                masks={k:selected[k] for k in ('fallback','raw_indefinite','raw_material_indefinite','raw_nonfinite','damped_nonfinite')},
                score_init=float(score),lambda_value=lam,tau=lam,
                assembly_seconds=assembly_seconds,spd_decision_seconds=decision_seconds,
                linear_solve_seconds=solve_seconds,cpu_solve_seconds=time.perf_counter()-begin)


def evaluate(*args,**kwargs):
    """Reuse the immutable chart scorer, replacing only its conditional solve.

    Single-threaded process only. The original function is restored even on an
    exception; no source file or other process is modified.
    """
    ordinary=CHART.conditional_point_solve
    CHART.conditional_point_solve=conditional_point_newton
    try:result=CHART.evaluate_chart_step(*args,**kwargs,chart='euclidean')
    finally:CHART.conditional_point_solve=ordinary
    correction=float(np.sum(result['half_active_second_order_per_track'],dtype=np.longdouble))
    result['prediction_gn']=result['pred']
    result['prediction_hybrid']=result['pred']-correction
    result['rho_gn']=result['rho']
    result['rho_hybrid']=result['true_decrease']/result['prediction_hybrid'] if result['prediction_hybrid']!=0 else np.nan
    result['active_second_order_model_term']=correction
    result['model_error_hybrid_per_track']={k:result['model_error_per_track'][k]-(result['half_active_second_order_per_track'] if k in ('full','point') else 0)
                                            for k in result['model_error_per_track']}
    return result
