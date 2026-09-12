#!/usr/bin/env python3
"""Sparse coherent terminal coarse stopping-oracle screen; CPU only."""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np
from scipy import sparse
from scipy.linalg import cho_factor,cho_solve

P=Path(__file__).resolve().parent
C=P.parents[1]
sys.path.insert(0,str(P.parent))
import diagnostic as geometry
import spectrum

def audit_module():
    path=C/'analysis/audit_capture.py'
    spec=importlib.util.spec_from_file_location('terminal_oracle_audit',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module,path

def local_sparse_basis(blocks,nc):
    rows=[];cols=[];values=[];offset=0
    for block in blocks:
        ids,Q=block['ids'],block['Q'];a,b=np.nonzero(Q)
        rows.append((9*ids[:,None]+np.arange(9)).reshape(-1)[a]);cols.append(b+offset);values.append(Q[a,b]);offset+=Q.shape[1]
    return sparse.coo_matrix((np.concatenate(values),(np.concatenate(rows),np.concatenate(cols))),shape=(9*nc,offset)).tocsr()

def score_direction(audit,camera,X,ci,pi,uv,dc,dp,meta):
    moved=camera.retract(dc);initial=np.longdouble(0);final=np.longdouble(0);decrease=np.longdouble(0);prediction=np.longdouble(0);scale=np.longdouble(0)
    for start in range(0,len(ci),50000):
        sl=slice(start,start+50000);ic,j=ci[sl],pi[sl]
        r,Y,dY,dintr=audit._residual(camera,X[j],ic,uv[sl])
        RX=np.einsum('nij,nj->ni',camera.R[ic],X[j])
        yc=np.einsum('nij,nj->ni',dY,np.cross(dc[ic,:3],RX)+dc[ic,3:6])+np.einsum('nij,nj->ni',dintr,dc[ic,6:9])
        yp=np.einsum('nij,nj->ni',dY,np.einsum('nij,nj->ni',camera.R[ic],dp[j]))
        rd,_,_,_=audit._residual(moved,X[j]+dp[j],ic,uv[sl])
        c0=.5*np.einsum('ni,ni->n',r,r);c1=.5*np.einsum('ni,ni->n',rd,rd);jd=yc+yp
        linear=np.einsum('ni,ni->n',r,jd);quadratic=.5*np.einsum('ni,ni->n',jd,jd)
        initial+=np.sum(c0,dtype=np.longdouble);final+=np.sum(c1,dtype=np.longdouble);decrease+=np.sum(c0-c1,dtype=np.longdouble)
        prediction+=np.sum(-linear-quadratic,dtype=np.longdouble)
        scale+=np.sum(np.abs(linear)+quadratic,dtype=np.longdouble)
    return dict(score_init=float(initial),cost=float(final),true_decrease=float(decrease),prediction=float(prediction),
                rho=float(decrease/prediction) if prediction else None,prediction_term_scale=float(scale))

def run(capture:Path,bal:Path,rep:int):
    start=time.perf_counter();baseline=geometry.verify_baseline();charts,chartpath=spectrum.chart_module();audit,auditpath=audit_module()
    meta=geometry.read_metadata(capture/'metadata.txt');nc,np_,no=[int(meta[k]) for k in ('ncam','npt','nobs')]
    shape={'R_state.f64':(nc,3,3),'t_state.f64':(nc,3),'X_state.f64':(np_,3),'intr_state.f64':(3,nc),
           'E.f64':(nc,9),'Cdiag.f64':(np_,3),'Hcc.f64':(nc,9,9)}
    data={name:geometry.read_array(capture/name,s) for name,s in shape.items()};E=data['E.f64'];lam=meta['lambda']
    assert lam>0 and meta['tau']==lam
    camera=charts.CameraState(data['R_state.f64'],data['t_state.f64'],data['intr_state.f64'].T);X=data['X_state.f64']
    ci,pi,uv,dims=charts.load_observations(bal);assert dims==(nc,np_,no)
    manifest=json.loads((capture/'manifest.json').read_text());assert geometry.sha256(bal)==manifest['input_sha256']
    native=audit.read_native_rows(capture/'native_directions.csv');control=next(r for r in native if r['arm']=='eta2' and r['rep']==0)
    labels,clustering=geometry.cluster_centers(camera.centers(),8);blocks,basis=geometry.build_blocks(camera.R,camera.t,E,labels)
    global_blocks,global_basis=geometry.build_blocks(camera.R,camera.t,E,np.zeros(nc,dtype=int))
    Z=local_sparse_basis(blocks,nc);EZ=Z.multiply(E.reshape(-1,1)).tocsr();rank=Z.shape[1]
    H=np.column_stack((X,np.ones(np_)));tangent=np.zeros((np_,4,3));tangent[:,:3,:]=np.eye(3)
    residual,Jc,Jp,Y=charts.observation_jacobians(camera,H,tangent,ci,pi,uv)
    if not all(np.isfinite(a).all() for a in (residual,Jc,Jp)):raise ValueError('nonfinite Jacobian')
    counts=np.bincount(ci,minlength=nc);r2=np.sum((Y[:,:2]/Y[:,2,None])**2,axis=1)
    mean=np.maximum(np.bincount(ci,weights=r2,minlength=nc)/np.maximum(counts,1),1e-12)
    prior=np.zeros((nc,9));seen=counts>0
    prior[seen,6]=1/(.5*np.abs(camera.intrinsics[seen,0])+1e-3)**2;prior[seen,7]=mean[seen]**2
    U=np.zeros((nc,9,9));gc=np.zeros((nc,9));order=np.argsort(ci,kind='stable');offsets=np.r_[0,np.cumsum(counts)]
    sorted_Jc=Jc[order];sorted_r=residual[order]
    for c in range(nc):
        sl=slice(offsets[c],offsets[c+1]);local=sorted_Jc[sl].reshape(-1,9)
        U[c]=local.T@local+np.diag(prior[c]);gc[c]=local.T@sorted_r[sl].reshape(-1)
    del sorted_Jc,sorted_r,H,tangent,Y,r2
    gp=spectrum.sum_tracks(np.einsum('nri,nr->ni',Jp,residual),pi,np_)
    floor=lam*np.sum(data['Cdiag.f64'],axis=1)/3;floor=np.where(floor>0,floor,1e-32)
    damping=np.maximum(lam*data['Cdiag.f64'],1e-3*floor[:,None])
    R,inverse_R,point_counts=spectrum.point_qr(Jp,pi,damping)
    cross=np.einsum('nri,nrj->nij',Jc,Jp)
    rows=np.broadcast_to(9*ci[:,None,None]+np.arange(9)[None,:,None],cross.shape).reshape(-1)
    cols=np.broadcast_to(3*pi[:,None,None]+np.arange(3)[None,None,:],cross.shape).reshape(-1)
    W=sparse.coo_matrix((cross.reshape(-1),(rows,cols)),shape=(9*nc,3*np_)).tocsr();W.eliminate_zeros()
    del cross,rows,cols
    sparse_Rinv=sparse.bsr_matrix((inverse_R,np.arange(np_),np.arange(np_+1)),shape=(3*np_,3*np_)).tocsr()
    T=(W.T@EZ).tocsr();factor_T=sparse_Rinv.T@T
    Ac=-(factor_T.T@factor_T).toarray();camera_term=np.zeros_like(Ac)
    col_offset=0
    for block in blocks:
        ids,Q=block['ids'],block['Q'];r=Q.shape[1];q=Q.reshape(len(ids),9,r);physical=q*E[ids,:,None]
        local=np.einsum('nqi,nqr,nrj->ij',physical,U[ids],physical,optimize=True)+lam*(Q.T@Q)
        camera_term[col_offset:col_offset+r,col_offset:col_offset+r]=local;col_offset+=r
    Ac+=camera_term;Ac=.5*(Ac+Ac.T)
    point_zero=spectrum.point_inverse(inverse_R,gp)
    b=-E.reshape(-1)*(gc.reshape(-1)-W@point_zero.reshape(-1));bc=np.asarray(Z.T@b).reshape(-1)
    point_constant=.5*float(np.einsum('ni,ni->',gp,point_zero))
    chol=cho_factor(Ac,lower=True,check_finite=True);coefficient=cho_solve(chol,bc)
    decrement=.5*float(bc@coefficient);coarse_residual=float(np.linalg.norm(Ac@coefficient-bc)/max(np.linalg.norm(bc),1e-300))
    def product(v):
        physical=(E*v.reshape(nc,9))[ci];y=np.einsum('nri,ni->nr',Jc,physical)
        s=spectrum.sum_tracks(np.einsum('nri,nr->ni',Jp,y),pi,np_);u=spectrum.point_inverse(inverse_R,s)
        z=y-np.einsum('nri,ni->nr',Jp,u[pi]);g=spectrum.sum_tracks(np.einsum('nri,nr->ni',Jc,z),ci,nc)
        return (E*g+(lam+E**2*prior)*v.reshape(nc,9)).reshape(-1)
    probes=[];rng=np.random.default_rng(92012)
    for name,q in [('fixed_random',rng.normal(size=rank)),('rhs',bc),('solution',coefficient),('first_column',np.eye(rank)[0])]:
        norm=np.linalg.norm(q)
        if not norm:probes.append(dict(name=name,zero=True,relative_error=0));continue
        q=q/norm;reference=np.asarray(Z.T@product(np.asarray(Z@q))).reshape(-1)
        error=np.linalg.norm(reference-Ac@q)/max(np.linalg.norm(reference),1e-300)
        probes.append(dict(name=name,relative_error=float(error)))
    reduced_residual=residual-np.einsum('nri,ni->nr',Jp,point_zero[pi])
    reduced_gradient=-E*spectrum.sum_tracks(np.einsum('nri,nr->ni',Jc,reduced_residual),ci,nc)
    projected_gradient=np.asarray(Z.T@reduced_gradient.reshape(-1)).reshape(-1)
    gradient_projection=float(np.linalg.norm(projected_gradient-bc)/max(np.linalg.norm(bc),1e-300))
    parity=max(gradient_projection,max(q['relative_error'] for q in probes))<=1e-7
    assembly_seconds=time.perf_counter()-start
    z_raw=np.asarray(Z@coefficient).reshape(nc,9);raw_norm=float(np.linalg.norm(z_raw));radius=meta['radius']
    ratios=[('raw',1.),('clipped',min(1.,radius/raw_norm) if raw_norm else 1.)];arms=[]
    for arm,alpha in ratios:
        z=alpha*z_raw;dc=E*z
        camera_y=np.einsum('nri,ni->nr',Jc,dc[ci])
        conditional=-spectrum.sum_tracks(np.einsum('nri,nr->ni',Jp,residual+camera_y),pi,np_)
        dp=spectrum.point_inverse(inverse_R,conditional)
        row=score_direction(audit,camera,X,ci,pi,uv,dc,dp,meta)
        linear=residual+camera_y+np.einsum('nri,ni->nr',Jp,dp[pi])
        point_equation=spectrum.sum_tracks(np.einsum('nri,nr->ni',Jp,linear),pi,np_)+damping*dp
        point_relative=float(np.linalg.norm(point_equation)/max(np.linalg.norm(conditional),1e-300))
        damp_penalty=.5*(lam*np.sum(z*z)+np.sum(damping*dp*dp)+np.sum(prior*dc*dc))
        damped_prediction=row['prediction']-float(damp_penalty)
        eliminated_prediction=point_constant+alpha*float(bc@coefficient)-.5*alpha*alpha*float(coefficient@Ac@coefficient)
        scale=max(1.,row['prediction_term_scale'],abs(float(damp_penalty)),abs(point_constant),abs(decrement))
        identity_error=abs(damped_prediction-eliminated_prediction)/scale
        zero_norm=float(np.linalg.norm(z));projected=geometry.project_blocks(z,global_blocks)
        row.update(arm=arm,clip_scale=alpha,camera_scaled_norm=zero_norm,radius=radius,
                   global_similarity_fraction=float(np.linalg.norm(projected)/zero_norm) if zero_norm else None,
                   point_conditional_residual_relative_rhs=point_relative,
                   damped_prediction=damped_prediction,point_only_damped_constant=point_constant,
                   eliminated_damped_prediction=eliminated_prediction,
                   model_identity_normalized_error=identity_error,model_identity_pass=identity_error<=1e-7,
                   full_objective_score_init_relative_error=abs(row['score_init']-meta['cost'])/max(1,abs(meta['cost'])),
                   eta2_native_gain=control['decrease'],true_gain_over_eta2=row['true_decrease']/control['decrease'],
                   practical_gate=bool(arm=='clipped' and row['rho'] is not None and row['rho']>.1 and row['true_decrease']>2*control['decrease']))
        arms.append(row)
    zero_threshold=100*np.finfo(float).eps*max(1,abs(point_constant))
    result=dict(kind='registered terminal coarse oracle',capture=str(capture),rep=rep,metadata=meta,baseline=baseline,
                settings=dict(K=8,point_factors='coherent FP64 QR',matrix='sparse W, block-local Z, small Ac',pcg_operator_changed=False),
                clustering=clustering,basis=basis,global_similarity_rank=global_basis['rank'],
                gauge_note='Global similarity retained with damping; not removed as a nullspace.',
                camera_coarse_decrement=decrement,point_only_damped_constant=point_constant,
                decrement_over_eta2_gain=decrement/control['decrease'],decrement_numerically_zero=bool(decrement<=zero_threshold),
                numerical_zero_threshold=zero_threshold,coarse_solve_relative_residual=coarse_residual,
                coarse_eigenvalues=np.linalg.eigvalsh(Ac).tolist(),coarse_matrix=Ac.tolist(),coarse_rhs=bc.tolist(),
                operator_parity=probes,operator_parity_pass=bool(parity),independent_reduced_gradient_relative_error=gradient_projection,
                native_Hcc_relative_discrepancy=float(np.linalg.norm(U-data['Hcc.f64'])/np.linalg.norm(data['Hcc.f64'])),
                sparse_sizes=dict(W_shape=W.shape,W_nnz=W.nnz,Z_shape=Z.shape,Z_nnz=Z.nnz,T_shape=T.shape,T_nnz=T.nnz),
                arms=arms,assembly_and_parity_cpu_seconds=assembly_seconds,total_cpu_seconds=time.perf_counter()-start,
                original_mismatches_retained=str(C/'analysis/retained_mismatches.json'),
                input_sha256={**{name:geometry.sha256(capture/name) for name in shape},'metadata.txt':geometry.sha256(capture/'metadata.txt'),
                              'native_directions.csv':geometry.sha256(capture/'native_directions.csv'),'BAL':geometry.sha256(bal)},
                implementation_sha256={'run.py':geometry.sha256(Path(__file__)),'spectrum.py':geometry.sha256(Path(spectrum.__file__)),
                                       'diagnostic.py':geometry.sha256(Path(geometry.__file__)),'charts/reference.py':geometry.sha256(chartpath),'audit_capture.py':geometry.sha256(auditpath)},
                protocol_sha256=geometry.sha256(C/'PROTOCOL_09.md'),
                limitation='Fixed-state deterministic CPU repetitions, not optimizer hit-rate or speed evidence.')
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--capture',type=Path,required=True);parser.add_argument('--bal',type=Path,required=True);parser.add_argument('--rep',type=int,required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    result=run(a.capture,a.bal,a.rep);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(capture=a.capture.name,rep=a.rep,decrement=result['camera_coarse_decrement'],constant=result['point_only_damped_constant'],parity=result['operator_parity_pass'],arms=[{k:r[k] for k in ('arm','true_decrease','rho','true_gain_over_eta2','practical_gate','model_identity_normalized_error')} for r in result['arms']],cpu_seconds=result['total_cpu_seconds']),indent=2))

if __name__=='__main__':main()
