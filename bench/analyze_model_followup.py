#!/usr/bin/env python3
"""Independent fixed-state FP64 residual defects and Schur-curvature checks."""
import argparse
import json
import pathlib
import numpy as np
from audit_prism_state import observations
from local_curvature_model import FixedDirection


def dot(x,y):
    return float(np.sum(x*y,dtype=np.longdouble))


def positive_schur(d,meta,diag_path):
    """Rebuild original-double point Jacobians; eliminate with the same damping.

    Evaluate energy as a sum of squares, avoiding camera/point cancellation.
    No endpoint or controller changes; all work is outside solve timing.
    """
    q=d.RX+d.t[d.ci];iz=1/q[:,2];u=-q[:,0]*iz;v=-q[:,1]*iz
    r2=u*u+v*v;f=d.intr[0,d.ci];k=d.intr[1,d.ci]
    a=f*(1+k*r2+2*k*u*u);b=2*f*k*u*v;c=f*(1+k*r2+2*k*v*v)
    dx=np.stack((-a*iz,-b*iz,-(a*u+b*v)*iz),axis=1)
    dy=np.stack((-b*iz,-c*iz,-(b*u+c*v)*iz),axis=1)
    jx=np.einsum('ni,nij->nj',dx,d.R[d.ci]);jy=np.einsum('ni,nij->nj',dy,d.R[d.ci])
    vc,_=d.jacobian_directions()
    C=np.empty((d.np,3,3));bpt=np.empty((d.np,3))
    for i in range(3):
        bpt[:,i]=np.bincount(d.pi,weights=jx[:,i]*vc[:,0]+jy[:,i]*vc[:,1],minlength=d.np)
        for j in range(i,3):
            C[:,i,j]=np.bincount(d.pi,weights=jx[:,i]*jx[:,j]+jy[:,i]*jy[:,j],minlength=d.np)
            C[:,j,i]=C[:,i,j]
    diag=np.fromfile(diag_path,'<f8').reshape(d.np,3)
    fl=meta['tau']*diag.sum(axis=1)/3
    fl=np.where(fl>0,fl,1e-32)
    reg=np.maximum(meta['tau']*diag,1e-3*fl[:,None])
    C[:,np.arange(3),np.arange(3)]+=reg
    try:
        dp=np.linalg.solve(C,-bpt[...,None])[...,0]
    except np.linalg.LinAlgError:
        # Rank-deficient blocks are reported explicitly, not called an exact solve.
        return dict(rebuild_failed=True)
    jdp=np.stack((np.sum(jx*dp[d.pi],axis=1),np.sum(jy*dp[d.pi],axis=1)),axis=1)
    reduced_energy=dot(vc+jdp,vc+jdp)+dot(reg*dp,dp)+meta['lambda']*meta['pp']
    trial_dp=np.fromfile(diag_path.with_suffix('.step'),'<f8')[9*d.nc:].reshape(d.np,3)
    _,stored_point=d.jacobian_directions()
    stored_energy=dot(vc+stored_point,vc+stored_point)+dot(reg*trial_dp,trial_dp)+meta['lambda']*meta['pp']
    stationarity=np.einsum('pij,pj->pi',C,trial_dp)+bpt
    solved_residual=np.einsum('pij,pj->pi',C,dp)+bpt
    backward=np.linalg.norm(solved_residual,axis=1)/np.maximum(1e-300,np.linalg.norm(C,axis=(1,2))*np.linalg.norm(dp,axis=1)+np.linalg.norm(bpt,axis=1))
    return dict(rebuild_failed=False,stored_pap=meta['pap'],true_schur_energy=reduced_energy,
        stored_direction_true_energy=stored_energy,normalized_stored_pap=meta['pap']/meta['pp'],
        normalized_true_energy=reduced_energy/meta['pp'],
        rebuilt_point_max_backward_error=float(np.max(backward)),
        point_stationarity_relative=float(np.linalg.norm(stationarity)/max(1e-300,np.linalg.norm(bpt))),
        point_solution_relative_difference=float(np.linalg.norm(trial_dp-dp)/max(1e-300,np.linalg.norm(dp))))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--captures',type=pathlib.Path,required=True)
    ap.add_argument('--output',type=pathlib.Path,required=True);a=ap.parse_args()
    rows=[];obs_cache={}
    for path in sorted(a.captures.glob('*.json')):
        scene=path.name.split('-capture-')[0]
        if scene not in obs_cache:obs_cache[scene]=observations(pathlib.Path('/workspace/bal')/(scene+'.txt'))[1]
        m=json.loads(path.read_text());d=FixedDirection(path.with_suffix(''),obs_cache[scene]);r,_=d.residual(0,0);vc,vp=d.jacobian_directions();v=vc+vp
        F=.5*dot(r,r);row=dict(capture=path.name,scene=scene,metadata=m,initial_audit_relative=abs(F-m['cost'])/max(1,F))
        assert row['initial_audit_relative']<1e-7,row
        if '-negative-' in path.name:
            row['curvature']=positive_schur(d,m,path.with_suffix('.diag'))
        else:
            r1,z1=d.residual(1,1);e=r1-r-v;rv=dot(r,v);vv=dot(v,v);re=dot(r,e);ve=dot(v,e);ee=dot(e,e)
            pred=-rv-.5*vv;ared=F-.5*dot(r1,r1)
            poly=np.array([rv,.5*vv+re,ve,.5*ee])
            roots=np.roots([2*ee,3*ve,vv+2*re,rv]);scales=[0.,1.]+[float(z.real) for z in roots if abs(z.imag)<1e-8 and 0<z.real<1]
            q=lambda x:x*(poly[0]+x*(poly[1]+x*(poly[2]+x*poly[3])))
            alpha=min(scales,key=q)
            probes={}
            for label,t in [('full',1.),('half',.5),('gn_ray',float(np.clip(-rv/vv,0,1))),('residual_curve',alpha)]:
                actual=d.evaluate(t,t)['cost'];pt=-t*rv-.5*t*t*vv
                probes[label]=dict(alpha=t,cost=actual,rho=(F-actual)/pt if pt>0 else None,armijo=bool(actual<F and actual<=F+1e-4*t*rv),strict_accept=bool(pt>0 and actual<F and (F-actual)/pt>.1))
            per=np.sum((r+v)*e+.5*e*e,axis=1)
            tracks=np.bincount(d.pi,weights=per,minlength=d.np)
            total=np.sum(np.abs(tracks));ordered=np.sort(np.abs(tracks))[::-1]
            fd_errors={}
            for eps in [1e-2,1e-3,1e-4,1e-5,1e-6]:
                fd=(d.residual(eps,eps)[0]-d.residual(-eps,-eps)[0])/(2*eps)
                fd_errors[str(eps)]=float(np.linalg.norm(fd-v)/max(1e-300,np.linalg.norm(v)))
            row.update(prediction=pred,actual_reduction=ared,full_trial_cost=F-ared,
                trial_audit_relative=abs(F-ared-m['trial'])/max(1,abs(m['trial'])),
                rho=ared/pred if pred>0 else None,linearization_relative=float(np.linalg.norm(e)/max(1e-300,np.linalg.norm(v))),
                finite_difference_relative=fd_errors,
                identity_scaled_error=abs((pred-ared)-(re+ve+.5*ee))/max(1,abs(pred),abs(ared)),
                top_one_percent_tracks_error_share=float(ordered[:max(1,d.np//100)].sum()/total) if total else 0.,
                depth_flip_observations=int(np.sum(z1*d.z0<0)),quartic_coefficients=poly.tolist(),probes=probes)
        rows.append(row);print(json.dumps(row),flush=True)
    with a.output.open('x') as f:json.dump(rows,f,indent=2);f.write('\n')

if __name__=='__main__':main()
