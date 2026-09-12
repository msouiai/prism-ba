"""W1 fixed-state camera-mode decomposition; no optimizer changes."""
from pathlib import Path
import json, sys, time, hashlib
import numpy as np
from scipy import sparse

P = Path(__file__).resolve().parent
C = P.parent/'eta2_research_20260912'
sys.path[:0] = [str(C/'coarse'), str(C/'analysis')]
import diagnostic as D
from audit_capture import load_capture_state, CHART
from spectrum import point_qr, point_inverse

def subspaces(R,t,E):
    n=len(R)
    blocks, gm=D.build_blocks(R,t,E,np.zeros(n,dtype=int)); G=blocks[0]['Q']
    labels, cluster=D.cluster_centers(D.centers(R,t),8)
    blocks, cm=D.build_blocks(R,t,E,labels)
    Z=np.zeros((n*9,sum(b['Q'].shape[1] for b in blocks)))
    off=0
    for b in blocks:
        ids=(9*b['ids'][:,None]+np.arange(9)).reshape(-1)
        k=b['Q'].shape[1];Z[np.ix_(ids,np.arange(off,off+k))]=b['Q'];off+=k
    Z-=G@(G.T@Z)
    U,s,_=np.linalg.svd(Z,full_matrices=False);Q=U[:,s>1e-8]
    return G,Q,dict(gauge=gm,clusters=cluster,cluster_rank_without_gauge=Q.shape[1],
                    cross_orthogonality=float(np.max(np.abs(G.T@Q))))

def decompose(z,G,Q):
    z=z.reshape(-1);g=G@(G.T@z);c=Q@(Q.T@z);r=z-g-c
    norms=np.sum(z.reshape(-1,9)**2,axis=1);ids=np.argsort(norms)[-5:][::-1]
    norm2=float(z@z)
    return [g,c,r],dict(norm=float(np.sqrt(norm2)),gauge_fraction=float(g@g/max(norm2,1e-300)),
        cluster_without_gauge_fraction=float(c@c/max(norm2,1e-300)),
        remainder_fraction=float(r@r/max(norm2,1e-300)),top5_camera_ids=ids.tolist(),
        top5_raw_fraction=float(norms[ids].sum()/max(norm2,1e-300)),
        reconstruction_error=float(np.linalg.norm(z-g-c-r)),
        sum_squared_fraction=float((g@g+c@c+r@r)/max(norm2,1e-300)))

def sum_tracks(x,pi,np_):
    return np.column_stack([np.bincount(pi,weights=x[:,i],minlength=np_) for i in range(x.shape[1])])

def run(scene,rep):
    start=time.perf_counter();folder=C/'evidence/collect'/f'{scene}-capture-{rep}'
    cam,X,meta=load_capture_state(folder);nc,np_=len(cam.R),len(X)
    ci,pi,uv,dims=CHART.load_observations('/workspace/bal/'+scene+'.txt')
    E=D.read_array(folder/'E.f64',(nc,9));Cdiag=D.read_array(folder/'Cdiag.f64',(np_,3))
    G,Q,bases=subspaces(cam.R,cam.t,E)
    chart=CHART.make_chart(X,cam,'euclidean')
    residual,Jc,Jp,Y=CHART.observation_jacobians(cam,chart.H,chart.T,ci,pi,uv)
    dpdiag=np.maximum(Cdiag,.001*np.maximum(Cdiag.mean(axis=1),1e-32)[:,None])
    _,Ri,_=point_qr(Jp,pi,meta['tau']*dpdiag)
    gp=sum_tracks(np.einsum('nri,nr->ni',Jp,residual),pi,np_)
    offset=-point_inverse(Ri,gp)
    joffset=np.einsum('nri,ni->nr',Jp,offset[pi])
    sources=[('eta2_raw',-D.read_array(folder/'eta2_raw_scaled.f64',(nc,9)))]
    for r in range(3):
        z=D.read_array(folder/f'exact-{r}.step',(9*nc+3*np_,))[:9*nc].reshape(nc,9)/E
        sources.append((f'coherent_reference_{r}',z))
    records=[]
    initial=float(.5*np.sum(residual*residual,dtype=np.longdouble))
    for name,z in sources:
        parts,norms=decompose(z,G,Q);jdparts=[]
        for part in parts:
            dc=(E.reshape(-1)*part).reshape(nc,9)
            yc=np.einsum('nri,ni->nr',Jc,dc[ci])
            cross=sum_tracks(np.einsum('nri,nr->ni',Jp,yc),pi,np_)
            dp=-point_inverse(Ri,cross)
            jdparts.append(yc+np.einsum('nri,ni->nr',Jp,dp[pi]))
        jdparts.append(joffset)
        total=sum(jdparts)
        pred=-float(np.sum(residual*total+.5*total*total,dtype=np.longdouble))
        # Symmetric allocation of all quadratic cross terms, summing to pred.
        allocations=[-float(np.sum(residual*v+.5*v*total,dtype=np.longdouble)) for v in jdparts]
        assert abs(sum(allocations)-pred)<1e-8*max(1,abs(pred))
        records.append(dict(direction=name,raw_radius_ratio=norms['norm']/meta['radius'],**norms,
            prediction=pred,model_decrease_allocation=dict(zip(['gauge','local_cluster','remainder','point_offset'],allocations))))
    # Check the damped gauge RHS identity for all seven physical modes.
    raw,_=D.finite_difference_modes(cam.R,cam.t)
    ctr=cam.centers().mean(axis=0)
    nc_modes=raw;np_modes=np.zeros((np_,3,7))
    for m in range(3):
        unit=np.eye(3)[m];np_modes[:,:,m]=np.cross(unit,X-ctr)
        np_modes[:,:,3+m]=unit
    np_modes[:,:,6]=X-ctr
    # World rotation uses centroid: finite_difference_modes rotates about ctr.
    gc=sum_tracks(np.einsum('nri,nr->ni',Jc,residual),ci,nc)
    up=point_inverse(Ri,gp);wup=np.einsum('nri,ni->nr',Jp,up[pi])
    red=-gc+sum_tracks(np.einsum('nri,nr->ni',Jc,wup),ci,nc)
    gauge=[]
    for m in range(7):
        a=nc_modes[:,:,m];b=np_modes[:,:,m]
        null=np.einsum('nri,ni->nr',Jc,a[ci])+np.einsum('nri,ni->nr',Jp,b[pi])
        direct=float(np.sum(red*a,dtype=np.longdouble))
        identity=meta['tau']*float(np.sum(gp*point_inverse(Ri,dpdiag*b),dtype=np.longdouble))
        gauge.append(dict(mode=m,direct=direct,rhs_identity=identity,
            absolute_error=abs(direct-identity),scaled_error=abs(direct-identity)/max(1,abs(direct),abs(identity)),
            joint_null_residual_norm=float(np.linalg.norm(null))))
    return dict(scene=scene,rep=rep,metadata=meta,score_init=initial,bases=bases,rows=records,
        gauge_rhs_audit=gauge,seconds=time.perf_counter()-start,
        caveat='Point responses/model allocations use coherent CPU rows and captured tau; native raw CG direction is retained. These are diagnostics, not target timings.')

def main():
    D.verify_baseline();out=P/'witness';out.mkdir(exist_ok=True)
    cases=[('venice-52',r) for r in [0,1,2]]+[('final-3068',r) for r in [0,5,6]]+[('ladybug-1197',0)]
    for scene,rep in cases:
        path=out/f'{scene}-{rep}.json'
        if path.exists():continue
        ans=run(scene,rep);path.write_text(json.dumps(ans,indent=2,allow_nan=False)+'\n')
        for row in ans['rows'][:2]:print(scene,rep,row['direction'],{k:row[k] for k in ['raw_radius_ratio','gauge_fraction','cluster_without_gauge_fraction','top5_raw_fraction']},flush=True)

if __name__=='__main__':main()
