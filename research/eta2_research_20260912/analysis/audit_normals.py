#!/usr/bin/env python3
"""Scaled full-normal/point-equation audit, including worst-track FP80 checks.

Native reduced-PCG certification does not certify these independent equations.
All arrays are held at point/camera resolution; observation work is chunked.
"""
import argparse
import json
from pathlib import Path
import time

import numpy as np

from audit_capture import (CHART, load_capture_state, map_f64, read_native_rows,
                           file_sha256, sanitize, _residual)


def rows(cameras, X, ci, pi, uv):
    r, _, dY, d_intr = _residual(cameras, X[pi], ci, uv)
    R = cameras.R[ci]
    RX = np.einsum("nij,nj->ni", R, X[pi])
    Jc = np.concatenate((dY @ (-CHART.skew(RX)), dY, d_intr), axis=2)
    Jp = dY @ R
    return r, Jc, Jp


def long_rows(cameras, point, ci, uv):
    """Reevaluate the mathematical projection/Jacobian in np.longdouble."""
    ld = np.longdouble
    R, t, X, intr = cameras.R[ci].astype(ld), cameras.t[ci].astype(ld), point.astype(ld), cameras.intrinsics[ci].astype(ld)
    RX = np.einsum("nij,j->ni", R, X)
    Y = RX + t
    xy = -Y[:, :2] / Y[:, 2, None]
    r2 = np.einsum("ni,ni->n", xy, xy)
    f, k = intr[:, 0], intr[:, 1]
    scale = 1 + k*r2
    pred = (f*scale)[:, None]*xy
    dxy = np.zeros((len(ci),2,3),dtype=ld)
    dxy[:,0,0] = -1/Y[:,2]; dxy[:,1,1] = -1/Y[:,2]
    dxy[:,:,2] = -xy/Y[:,2,None]
    drad = f[:,None,None]*(scale[:,None,None]*np.eye(2,dtype=ld)+2*k[:,None,None]*xy[:,:,None]*xy[:,None,:])
    dY = drad@dxy
    skew = np.zeros((len(ci),3,3),dtype=ld)
    skew[:,0,1]=-RX[:,2];skew[:,0,2]=RX[:,1]
    skew[:,1,0]=RX[:,2];skew[:,1,2]=-RX[:,0]
    skew[:,2,0]=-RX[:,1];skew[:,2,1]=RX[:,0]
    d_intr = np.zeros((len(ci),2,3),dtype=ld)
    d_intr[:,:,0]=scale[:,None]*xy; d_intr[:,:,1]=(f*r2)[:,None]*xy
    Jc = np.concatenate((dY@(-skew),dY,d_intr),axis=2)
    Jp = dY@R
    cancellation = (np.einsum("nij,j->ni",abs(R),abs(X))+abs(t))[:,2]/np.maximum(abs(Y[:,2]),np.finfo(ld).tiny)
    return pred-uv.astype(ld),Jc,Jp,Y,cancellation


def worst_track_audit(cameras, X, ci, pi, uv, dc, dp, damping, selected, order, offsets):
    out=[]
    for j in selected:
        indices=order[offsets[j]:offsets[j+1]]
        if not len(indices):
            continue
        ic=ci[indices];obs=uv[indices]
        r64,Jc64,Jp64=rows(cameras,X,ic,np.full(len(ic),j),obs)
        rl,Jcl,Jpl,Y,depth_condition=long_rows(cameras,X[j],ic,obs)
        stats={"point":int(j),"observations":int(len(indices)),"max_projected_depth_cancellation_condition":float(np.max(depth_condition)),
               "min_abs_projected_depth":float(np.min(abs(Y[:,2])))}
        for name,r,Jc,Jp in (("fp64_rows_extended_accumulation",r64.astype(np.longdouble),Jc64.astype(np.longdouble),Jp64.astype(np.longdouble)),
                            ("extended_geometry_and_accumulation",rl,Jcl,Jpl)):
            camera=np.einsum("nij,nj->ni",Jc,dc[ic].astype(np.longdouble))
            b=Jp.reshape(-1,3); z=dp[j].astype(np.longdouble);d=damping[j].astype(np.longdouble)
            linear_r=(r+camera).reshape(-1)
            rhs=-b.T@linear_r
            gram=b.T@b+np.diag(d)
            stable=b.T@(linear_r+b@z)+d*z
            assembled=gram@z-rhs
            den=np.sqrt(np.sum(gram*gram))*np.sqrt(np.sum(z*z))+np.sqrt(np.sum(rhs*rhs))
            norm=np.sqrt(np.sum(stable*stable))
            stats[name]={"absolute_residual_norm":float(norm),"rhs_norm":float(np.sqrt(np.sum(rhs*rhs))),
                         "normwise_backward_error":float(norm/max(den,np.longdouble(1e-300))),
                         "stable_minus_assembled_norm":float(np.sqrt(np.sum((stable-assembled)**2))),
                         "residual":stable.astype(float).tolist()}
        stats["point_J_relative_fp64_vs_extended"] = float(np.sqrt(np.sum((Jp64.astype(np.longdouble)-Jpl)**2))/max(np.sqrt(np.sum(Jpl*Jpl)),np.longdouble(1e-300)))
        out.append(stats)
    return out


def audit_normals(capture_dir,bal_path,*,output_path=None,chunk_size=50000):
    start=time.perf_counter();capture=Path(capture_dir);bal=Path(bal_path)
    cameras,X,meta=load_capture_state(capture)
    ci,pi,uv,dims=CHART.load_observations(bal)
    nc,npt,no=dims
    if dims!=(int(meta['ncam']),int(meta['npt']),int(meta['nobs'])):raise ValueError('dimension mismatch')
    E=map_f64(capture/'E.f64',(nc,9))
    Cdiag=map_f64(capture/'Cdiag.f64',(npt,3))
    tau=meta.get('tau',meta['lambda']);lam=meta['lambda']
    floor=tau*np.sum(Cdiag,axis=1)/3;floor=np.where(floor>0,floor,1e-32)
    damping=np.maximum(tau*Cdiag,1e-3*floor[:,None])
    # Point metric is the actual saved diagonal penalty divided by positive tau.
    metric=damping/tau if tau>0 else np.maximum(Cdiag,1e-3*np.sum(Cdiag,axis=1)[:,None]/3)
    whiten=1/np.sqrt(np.maximum(metric,1e-300))
    V=np.zeros((npt,3,3));gp=np.zeros((npt,3));gc=np.zeros((nc,9));r2sum=np.zeros(nc)
    for off in range(0,no,chunk_size):
        sl=slice(off,off+chunk_size);oi,oj=ci[sl],pi[sl]
        r,Jc,Jp=rows(cameras,X,oi,oj,uv[sl])
        Y=np.einsum('nij,nj->ni',cameras.R[oi],X[oj])+cameras.t[oi]
        xy=-Y[:,:2]/Y[:,2,None]
        r2sum+=np.bincount(oi,weights=np.einsum('ni,ni->n',xy,xy),minlength=nc)
        for a in range(3):
            gp[:,a]+=np.bincount(oj,weights=np.einsum('ni,ni->n',Jp[:,:,a],r),minlength=npt)
            for b in range(a,3):
                V[:,a,b]+=np.bincount(oj,weights=np.einsum('ni,ni->n',Jp[:,:,a],Jp[:,:,b]),minlength=npt)
        for a in range(9):gc[:,a]+=np.bincount(oi,weights=np.einsum('ni,ni->n',Jc[:,:,a],r),minlength=nc)
    for a in range(3):
        for b in range(a):V[:,a,b]=V[:,b,a]
    raw_diag=np.diagonal(V,axis1=1,axis2=2).copy()
    for a in range(3):V[:,a,a]+=damping[:,a]
    Vnorm=np.linalg.norm(V,axis=(1,2))
    counts=np.bincount(ci,minlength=nc)
    Q=np.zeros((nc,9));seen=counts>0
    Q[seen,6]=1/(.5*abs(cameras.intrinsics[seen,0])+1e-3)**2
    Q[seen,7]=np.maximum(r2sum[seen]/counts[seen],1e-12)**2
    gradient_norm=np.sqrt(np.sum((E*gc)**2)+np.sum((whiten*gp)**2))
    gp_norm=float(np.linalg.norm(gp))
    order=np.argsort(pi,kind='stable');track_counts=np.bincount(pi,minlength=npt);offsets=np.r_[0,np.cumsum(track_counts)]
    out=[]
    for native in read_native_rows(capture/'native_directions.csv'):
        arm,rep=native['arm'],native['rep'];step=map_f64(capture/f'{arm}-{rep}.step',(9*nc+3*npt,))
        dc=step[:9*nc].reshape(nc,9);dp=step[9*nc:].reshape(npt,3)
        rp=np.zeros((npt,3));cross=np.zeros((npt,3));rc=np.zeros((nc,9))
        for off in range(0,no,chunk_size):
            sl=slice(off,off+chunk_size);oi,oj=ci[sl],pi[sl]
            r,Jc,Jp=rows(cameras,X,oi,oj,uv[sl])
            yc=np.einsum('nij,nj->ni',Jc,dc[oi]);yp=np.einsum('nij,nj->ni',Jp,dp[oj]);rr=r+yc+yp
            for a in range(3):
                rp[:,a]+=np.bincount(oj,weights=np.einsum('ni,ni->n',Jp[:,:,a],rr),minlength=npt)
                cross[:,a]+=np.bincount(oj,weights=np.einsum('ni,ni->n',Jp[:,:,a],yc),minlength=npt)
            for a in range(9):rc[:,a]+=np.bincount(oi,weights=np.einsum('ni,ni->n',Jc[:,:,a],rr),minlength=nc)
        rp+=damping*dp
        # E=0 is not expected; retain the explicit guard rather than divide silently.
        if np.any(E==0):raise ValueError('zero saved camera scaling')
        rc+=Q*dc+lam*dc/(E*E)
        rhs=-(gp+cross);assembled=np.einsum('nij,nj->ni',V,dp)-rhs
        rp_per=np.linalg.norm(rp,axis=1);rhs_per=np.linalg.norm(rhs,axis=1)
        denom=Vnorm*np.linalg.norm(dp,axis=1)+rhs_per
        backward=rp_per/np.maximum(denom,1e-300)
        selected=np.unique(np.r_[np.argsort(-rp_per)[:10],np.argsort(-backward)[:10]])
        scale_point_norm=float(np.linalg.norm(whiten*rp));scale_camera_norm=float(np.linalg.norm(E*rc))
        out.append({
            'arm':arm,'rep':rep,'native_reduced_certified':bool(native['certified']),
            'label':('reference with certified reduced residual' if native['certified'] else 'approximate reference') if arm.startswith('exact') else 'native inexact direction',
            'camera_equation_applicability':'clipped camera direction is not expected to satisfy reduced/full normal equations' if arm=='exact_clip' else 'unclipped direction normal-equation diagnostic',
            'point_residual_norm':float(np.linalg.norm(rp)),'point_rhs_norm':float(np.linalg.norm(rhs)),
            'gp_norm':gp_norm,'WTdc_norm':float(np.linalg.norm(cross)),
            'point_residual_relative_rhs':float(np.linalg.norm(rp)/max(np.linalg.norm(rhs),1e-300)),
            'point_normwise_backward_error_global':float(np.linalg.norm(rp)/max(np.linalg.norm(denom),1e-300)),
            'point_normwise_backward_error_max':float(np.max(backward)),
            'point_normwise_backward_error_p95':float(np.quantile(backward,.95)),
            'point_stable_minus_assembled_norm':float(np.linalg.norm(rp-assembled)),
            'scaled_full_gradient_norm':float(gradient_norm),'Dp_whitened_point_residual_norm':scale_point_norm,
            'scaled_camera_residual_norm':scale_camera_norm,
            'Dp_whitened_point_residual_relative_full_gradient':scale_point_norm/max(float(gradient_norm),1e-300),
            'scaled_full_normal_residual_relative_full_gradient':float(np.hypot(scale_point_norm,scale_camera_norm)/max(float(gradient_norm),1e-300)),
            'worst_tracks':worst_track_audit(cameras,X,ci,pi,uv,dc,dp,damping,selected,order,offsets),
        })
    report={'kind':'independent full-normal and point backward-error audit','capture':str(capture),'bal':str(bal),
            'source_sha256':file_sha256(Path(__file__)),'longdouble_mantissa_bits':int(np.finfo(np.longdouble).nmant),
            'point_backward_error_definition':'||rp_j||2 / (||Vlambda_j||F ||dp_j||2 + ||rhs_j||2); global uses L2 norm of the per-point denominators',
            'scaled_residual_definition':'||[E rc; Dp^-1/2 rp]||2 / ||[E gc; Dp^-1/2 gp]||2; Dp is saved diagonal damping/tau',
            'saved_vs_recomputed_point_diagonal_relative_norm':float(np.linalg.norm(Cdiag-raw_diag)/max(np.linalg.norm(Cdiag),1e-300)),
            'rows':out,'cpu_seconds':time.perf_counter()-start,
            'scope':'Certification diagnostic only; reduced residual, full residual, nonlinear usefulness and backward stability are distinct'}
    report=sanitize(report)
    if output_path is not None:
        path=Path(output_path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True);p.add_argument('--bal',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=audit_normals(a.capture,a.bal,output_path=a.output)
    print(json.dumps({'output':str(a.output),'cpu_seconds':r['cpu_seconds']},indent=2))
