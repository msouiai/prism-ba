"""Full-objective Sim3 passenger-cluster CPU diagnostic, no point elimination."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import time
import numpy as np
from scipy.linalg import qr, svd, cho_factor, cho_solve
from scipy.spatial.transform import Rotation

HERE=Path(__file__).resolve().parent
CAMPAIGN=HERE.parents[1]
sys.path.insert(0,str(HERE.parent))
import diagnostic as geometry
import spectrum
charts,_=spectrum.chart_module()
spec=importlib.util.spec_from_file_location('passenger_audit',CAMPAIGN/'analysis/audit_capture.py')
audit=importlib.util.module_from_spec(spec);sys.modules[spec.name]=audit;spec.loader.exec_module(audit)

def skew(v):
    out=np.zeros(v.shape[:-1]+(3,3));out[...,0,1]=-v[...,2];out[...,0,2]=v[...,1]
    out[...,1,0]=v[...,2];out[...,1,2]=-v[...,0];out[...,2,0]=-v[...,1];out[...,2,1]=v[...,0]
    return out

def anchors(ci,pi,npt,labels):
    first=np.full(npt,len(ci),dtype=np.int64)
    np.minimum.at(first,pi,np.arange(len(ci)))
    membership=np.full(npt,-1,dtype=np.int64);seen=first<len(ci)
    membership[seen]=labels[ci[first[seen]]]
    return membership

def native_camera_basis(R,C,mu):
    out=np.zeros((len(R),9,7));out[:,:3,:3]=-R
    out[:,3:6,:3]=-R@skew(np.broadcast_to(mu,C.shape))
    out[:,3:6,3:6]=-R;out[:,3:6,6]=-np.einsum('nij,nj->ni',R,C-mu)
    return out

def passenger_basis(X,mu):
    out=np.zeros((len(X),3,7));out[:,:,:3]=-skew(X-mu);out[:,:,3:6]=np.eye(3);out[:,:,6]=X-mu
    return out

def fixed_metric(camera,X,E,Dp,labels,membership):
    C=camera.centers();blocks=[];offset=0
    for k in range(int(labels.max())+1):
        cameras=np.flatnonzero(labels==k);points=np.flatnonzero(membership==k);mu=C[cameras].mean(axis=0)
        bc=native_camera_basis(camera.R[cameras],C[cameras],mu)/E[cameras,:,None]
        bp=passenger_basis(X[points],mu)*np.sqrt(Dp[points,:,None])
        tall=np.vstack((bc.reshape(-1,7),bp.reshape(-1,7)));norms=np.linalg.norm(tall,axis=0)
        invnorm=np.divide(1.,norms,out=np.zeros_like(norms),where=norms>0)
        normalized=tall*invnorm
        R=qr(normalized,mode='r',check_finite=True)[0][:7]
        _,singular,Vt=svd(R,full_matrices=False,check_finite=True)
        keep=singular>1e-10*singular[0] if len(singular) and singular[0]>0 else np.zeros(len(singular),bool)
        transform=invnorm[:,None]*Vt[keep].T/singular[keep]
        weighted=tall@transform;rank=int(keep.sum());identity=weighted.T@weighted
        error=float(np.linalg.norm(identity-np.eye(rank),ord=2)) if rank else 0.
        if error>1e-6:raise ValueError('joint metric whitening failed')
        blocks.append(dict(cluster=k,cameras=cameras,points=points,mu=mu,T=transform,rank=rank,
                           offset=offset,singular_values=singular,column_norms=norms,whitening_error=error))
        offset+=rank
    return blocks,offset

def parameters(y,blocks):
    return np.asarray([b['T']@y[b['offset']:b['offset']+b['rank']] for b in blocks])

def transform(camera,X,labels,membership,blocks,q):
    C=camera.centers();newR=camera.R.copy();newt=camera.t.copy();newX=X.copy()
    for b,a in zip(blocks,q):
        ic,ip,mu=b['cameras'],b['points'],b['mu'];Q=Rotation.from_rotvec(a[:3]).as_matrix();em1=np.expm1(a[6]);scale=1+em1
        world_delta=(np.eye(3)-Q.T)@mu-Q.T@a[3:6]-em1*(C[ic]-mu)
        newR[ic]=camera.R[ic]@Q.T;newt[ic]+=np.einsum('nij,nj->ni',camera.R[ic],world_delta)
        relative=X[ip]-mu
        newX[ip]+=em1*relative+scale*(relative@(Q-np.eye(3)).T)+a[3:6]
    return charts.CameraState(newR,newt,camera.intrinsics),newX

def raw_jacobian_blocks(camera,X,ci,pi,uv,labels,membership,blocks):
    residual,Y,dY,_=audit._residual(camera,X[pi],ci,uv)
    kc=labels[ci];kp=membership[pi]
    if np.any(kp<0):raise ValueError('observed point missing anchor')
    centers=camera.centers()[ci];centroids=np.asarray([b['mu'] for b in blocks])
    R=camera.R[ci];jcam=np.zeros((len(ci),3,7));jpoint=np.zeros_like(jcam)
    jcam[:,:,:3]=R@skew(X[pi]-centroids[kc]);jcam[:,:,3:6]=-R
    jcam[:,:,6]=-np.einsum('nij,nj->ni',R,centers-centroids[kc])
    jpoint[:,:,:3]=-R@skew(X[pi]-centroids[kp]);jpoint[:,:,3:6]=R
    jpoint[:,:,6]=np.einsum('nij,nj->ni',R,X[pi]-centroids[kp])
    return residual,dY@jcam,dY@jpoint,kc,kp

def normal(camera,X,ci,pi,uv,labels,membership,blocks,rank,chunk=50000,dense=False):
    H=np.zeros((rank,rank));g=np.zeros(rank);cost=np.longdouble(0);same=0;cross=0;matrix=[]
    for start in range(0,len(ci),chunk):
        sl=slice(start,start+chunk)
        r,Jc,Jp,kc,kp=raw_jacobian_blocks(camera,X,ci[sl],pi[sl],uv[sl],labels,membership,blocks)
        cost+=np.sum(.5*np.einsum('ni,ni->n',r,r),dtype=np.longdouble)
        active=kc!=kp;same+=int((~active).sum());cross+=int(active.sum())
        if dense:full=np.zeros((len(r),2,rank))
        pair=kc*len(blocks)+kp
        for code in np.unique(pair[active]):
            a,b=divmod(int(code),len(blocks));ids=np.flatnonzero(active&(pair==code));ba,bb=blocks[a],blocks[b]
            sa=slice(ba['offset'],ba['offset']+ba['rank']);sb=slice(bb['offset'],bb['offset']+bb['rank'])
            A=(Jc[ids]@ba['T']).reshape(2*len(ids),ba['rank']);B=(Jp[ids]@bb['T']).reshape(2*len(ids),bb['rank']);rr=r[ids].reshape(-1)
            H[sa,sa]+=A.T@A;H[sb,sb]+=B.T@B;off=A.T@B;H[sa,sb]+=off;H[sb,sa]+=off.T
            g[sa]+=A.T@rr;g[sb]+=B.T@rr
            if dense:full[ids,:,sa]=A.reshape(len(ids),2,-1);full[ids,:,sb]=B.reshape(len(ids),2,-1)
        if dense:matrix.append(full.reshape(-1,rank))
    return dict(H=.5*(H+H.T),g=g,cost=float(cost),same_observations=same,cross_observations=cross,
                J=np.vstack(matrix) if dense else None)

def score(camera,X,moved,movedX,ci,pi,uv,labels,membership,chunk=50000):
    initial=np.longdouble(0);final=np.longdouble(0);gain=np.longdouble(0);internal=np.longdouble(0);internal_abs=np.longdouble(0);max_internal=0.
    for start in range(0,len(ci),chunk):
        sl=slice(start,start+chunk);ic,ip=ci[sl],pi[sl]
        r,*_=audit._residual(camera,X[ip],ic,uv[sl]);rr,*_=audit._residual(moved,movedX[ip],ic,uv[sl])
        c0=.5*np.einsum('ni,ni->n',r,r);c1=.5*np.einsum('ni,ni->n',rr,rr);difference=c0-c1
        mask=labels[ic]==membership[ip]
        initial+=np.sum(c0,dtype=np.longdouble);final+=np.sum(c1,dtype=np.longdouble);gain+=np.sum(difference,dtype=np.longdouble)
        internal+=np.sum(difference[mask],dtype=np.longdouble);internal_abs+=np.sum(np.abs(difference[mask]),dtype=np.longdouble)
        if np.any(mask):max_internal=max(max_internal,float(np.max(np.abs(rr[mask]-r[mask]))))
    return dict(score_init=float(initial),cost=float(final),gain=float(gain),same_cluster_gain=float(internal),
                same_cluster_absolute_cost_drift=float(internal_abs),same_cluster_max_pixel_drift=max_internal)

def displacement(camera,X,moved,movedX,E,radius):
    dc=np.zeros((len(camera.R),9));dc[:,:3]=Rotation.from_matrix(moved.R@camera.R.transpose(0,2,1)).as_rotvec();dc[:,3:6]=moved.t-camera.t
    camera_norm=float(np.linalg.norm(dc/E));pn=np.linalg.norm(movedX-X,axis=1);scene_radius=float(np.max(np.linalg.norm(camera.centers()-camera.centers().mean(axis=0),axis=1)))
    return dict(camera_scaled_norm=camera_norm,old_radius=radius,camera_norm_over_old_radius=camera_norm/radius,
                point_displacement_max=float(np.max(pn)),point_displacement_p99=float(np.quantile(pn,.99)),
                point_displacement_l2=float(np.linalg.norm(pn)),scene_radius=scene_radius,points_beyond_scene_radius=int(np.count_nonzero(pn>scene_radius)))

def episode(camera,X,E,ci,pi,uv,labels,membership,blocks,rank,lam,radius):
    start=time.perf_counter();base_camera,baseX=camera,X;attempts=[];normal_calls=0;score_calls=0;cached=None
    for iteration in range(3):
        assembly_start=time.perf_counter()
        if cached is None:cached=normal(camera,X,ci,pi,uv,labels,membership,blocks,rank);normal_calls+=1
        assembly_seconds=time.perf_counter()-assembly_start;H,g=cached['H'],cached['g']
        A=H+lam*np.eye(rank);y=cho_solve(cho_factor(A,lower=True,check_finite=True),-g)
        linear=float(g@y);quadratic=float(y@H@y);decrement=-.5*linear
        q=parameters(y,blocks);trials=[];accepted=False
        for half in range(9):
            alpha=2.**(-half);pred=-alpha*linear-.5*alpha*alpha*quadratic
            with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
                try:
                    moved,movedX=transform(camera,X,labels,membership,blocks,alpha*q)
                    row=score(camera,X,moved,movedX,ci,pi,uv,labels,membership);score_calls+=1
                    finite=all(np.isfinite(v) for v in row.values())
                except (ValueError,FloatingPointError):finite=False;row={}
            rho=row['gain']/pred if finite and pred>0 else None
            accepted=bool(finite and pred>0 and row['gain']>0 and rho>.1)
            trials.append(dict(alpha=alpha,prediction=pred,rho=rho,accepted=accepted,**row))
            if accepted:break
        entry=dict(iteration=iteration,lambda_=lam,decrement=decrement,gradient_norm=float(np.linalg.norm(g)),
                   solve_relative_residual=float(np.linalg.norm(A@y+g)/max(np.linalg.norm(g),1e-300)),
                   model_linear=linear,model_quadratic=quadratic,same_observations=cached['same_observations'],
                   cross_observations=cached['cross_observations'],assembly_cpu_seconds=assembly_seconds,
                   accepted=accepted,trials=trials,backtracking_halvings=len(trials)-1)
        if accepted:
            entry['displacement']=displacement(camera,X,moved,movedX,E,radius)
            camera,X=moved,movedX;cached=None
            if rho>.75:lam*=.1
        else:lam*=10.
        entry['lambda_next']=lam;attempts.append(entry)
    total=score(base_camera,baseX,camera,X,ci,pi,uv,labels,membership);score_calls+=1
    return dict(attempts=attempts,cumulative=total,cumulative_displacement=displacement(base_camera,baseX,camera,X,E,radius),
                normal_assemblies=normal_calls,full_scores=score_calls,episode_cpu_seconds=time.perf_counter()-start),camera,X
