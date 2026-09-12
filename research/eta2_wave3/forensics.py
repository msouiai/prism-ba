"""E1 coherent camera-block audit and E2 cap witness pre-test; no native rollout."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, sys, tarfile, tempfile, time
import numpy as np

P=Path(__file__).resolve().parent; W=P.parent/'eta2_wave2'; C=P.parent/'eta2_research_20260912'
sys.path[:0]=[str(W),str(C/'analysis'),str(C/'coarse')]
from audit_capture import load_capture_state,CHART
from diagnostic import read_array,verify_baseline
from spectrum import point_qr,point_inverse
import lossless_float_archive as FA
spec=importlib.util.spec_from_file_location('wave3_score',C/'separable_rescue/core.py')
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def aggregate(x,ids,n):
    shape=x.shape[1:];flat=x.reshape(len(x),-1)
    return np.column_stack([np.bincount(ids,weights=flat[:,k],minlength=n) for k in range(flat.shape[1])]).reshape((n,)+shape)

def audit(folder,scene,label,cap_screen=True):
    start=time.perf_counter();cam,X,meta=load_capture_state(folder);nc,np_=len(cam.R),len(X)
    ci,pi,uv,dims=CHART.load_observations('/workspace/bal/'+scene+'.txt')
    assert dims==(nc,np_,len(ci))
    E=read_array(folder/'E.f64',(nc,9));cd=read_array(folder/'Cdiag.f64',(np_,3))
    raw=-read_array(folder/'eta2_raw_scaled.f64',(nc,9));assert np.all(raw[:,8]==0)
    counts=np.bincount(ci,minlength=nc);tracks=np.bincount(pi,minlength=np_)
    chart=CHART.make_chart(X,cam,'euclidean')
    r,Jc,Jp,Y=CHART.observation_jacobians(cam,chart.H,chart.T,ci,pi,uv)
    diag=np.maximum(cd,.001*np.maximum(cd.mean(axis=1),1e-32)[:,None])
    multiplier=np.where(tracks>=6,.3,1.) if meta.get('static_replay',0) else np.ones(np_)
    point_diag=meta['tau']*multiplier[:,None]*diag
    _,Ri,_=point_qr(Jp,pi,point_diag)
    # Combine repeated camera/point observation pairs before forming W V^-1 W^T.
    keys=ci.astype(np.int64)*np_+pi;unique,inv=np.unique(keys,return_inverse=True)
    pci=unique//np_;ppi=unique%np_
    cross=aggregate(np.einsum('nri,nrj->nij',Jc,Jp),inv,len(unique))
    U=aggregate(np.einsum('nri,nrj->nij',Jc,Jc),ci,nc)
    factor=np.einsum('nij,njk->nik',cross,Ri[ppi])
    schur=U-aggregate(np.einsum('nik,njk->nij',factor,factor),pci,nc)
    del cross,factor
    r2=np.sum((Y[:,:2]/Y[:,2,None])**2,axis=1)
    avg=np.maximum(np.bincount(ci,weights=r2,minlength=nc)/np.maximum(counts,1),1e-12)
    prior=np.zeros((nc,9));prior[:,6]=np.where(counts>0,1/(.5*np.abs(cam.intrinsics[:,0])+1e-3)**2,0)
    prior[:,7]=np.where(counts>0,avg**2,0)
    scaled=schur*E[:,:,None]*E[:,None,:]
    symmetry=float(np.max(np.abs(scaled-scaled.transpose(0,2,1))))
    scaled=.5*(scaled+scaled.transpose(0,2,1))
    withprior=scaled.copy();withprior[:,np.arange(9),np.arange(9)]+=prior*E*E
    vals,vecs=np.linalg.eigh(scaled[:,:8,:8]);pv,pvecs=np.linalg.eigh(withprior[:,:8,:8])
    norms=np.linalg.norm(raw,axis=1);top=np.argsort(norms)[-5:][::-1]
    median_count=float(np.median(counts));median_eig=float(np.median(vals[:,0]));maxmed=float(np.median(vals[:,-1]))
    initial=float(.5*np.sum(r*r,dtype=np.longdouble));assert abs(initial-meta['cost'])/max(1,initial)<1e-8
    totalnorm=float(np.linalg.norm(raw));radius=float(meta['radius'])
    # A saved initial radius of zero means it has not yet been initialized.
    scanradius=radius if radius>0 else totalnorm
    entries=[]
    for c in top:
        c=int(c);obs=np.flatnonzero(ci==c);localtracks=np.unique(pi[obs]);v=vecs[c,:,0];v*=1 if v[np.argmax(abs(v))]>=0 else -1
        unit=np.zeros(9);unit[:8]=v;physical=E[c]*unit
        loading=dict(rotation=float(v[:3]@v[:3]),translation=float(v[3:6]@v[3:6]),f=float(v[6]**2),k1=float(v[7]**2),tz=float(v[5]**2))
        # Direct Gram: residual responses of all observations of affected points,
        # plus damping rows. Avoid subtracting two large normal blocks.
        involved=np.flatnonzero(np.isin(pi,localtracks));mapidx=np.searchsorted(localtracks,pi[involved])
        localJ=np.zeros((len(involved),2,8));own=ci[involved]==c
        localJ[own]=Jc[involved[own],:,:8]*E[c,:8]
        s=aggregate(np.einsum('nri,nrk->nik',Jp[involved],localJ),mapidx,len(localtracks))
        vi=np.einsum('nik,njk->nij',Ri[localtracks],Ri[localtracks])
        up=np.einsum('nij,njk->nik',vi,s)
        leftover=localJ-np.einsum('nri,nik->nrk',Jp[involved],up[mapidx])
        gram=np.einsum('nri,nrj->ij',leftover,leftover)+np.einsum('nik,ni,nil->kl',up,point_diag[localtracks],up)
        gramerr=float(np.linalg.norm(gram-scaled[c,:8,:8])/max(1,np.linalg.norm(gram)))
        scans=[];jdu=np.einsum('nri,i->nr',Jc[obs],physical)
        old=float(.5*np.sum(r[obs]*r[obs],dtype=np.longdouble))
        for a in [-10,-3,-1,-.3,-.1,-.03,-.01,0,.01,.03,.1,.3,1,3,10]:
            d=np.zeros((nc,9));d[c]=a*scanradius*physical;new=cam.retract(d)
            rr,_=S.residual(new,X[pi[obs]],ci[obs],uv[obs])
            cost=float(.5*np.sum(rr*rr,dtype=np.longdouble));lin=a*scanradius*jdu
            pred=-float(np.sum(r[obs]*lin+.5*lin*lin,dtype=np.longdouble))
            scans.append(dict(radius_multiple=a,full_cost=initial-old+cost if np.isfinite(cost) else None,
                true_decrease=old-cost if np.isfinite(cost) else None,prediction_fixed_points=pred,
                rho=(old-cost)/pred if np.isfinite(cost) and pred!=0 else None))
        entries.append(dict(camera=c,observations=int(counts[c]),count_ratio_to_median=counts[c]/max(1,median_count),
            tracks_ge3=int(np.count_nonzero(tracks[localtracks]>=3)),unique_tracks=len(localtracks),
            mean_track_length=float(np.mean(tracks[localtracks])),scaled_step_norm=float(norms[c]),
            raw_squared_fraction=float(norms[c]**2/max(totalnorm**2,1e-300)),active_eigenvalues=vals[c].tolist(),
            active_eigenvalues_with_intrinsic_prior=pv[c].tolist(),inactive_k2_eigenvalue=0.,
            min_eigenvalue_ratio_to_median=float(vals[c,0]/median_eig) if median_eig>0 else None,
            count_starved=bool(counts[c]<.25*median_count),spectrally_starved=bool(median_eig>0 and vals[c,0]<.01*median_eig),
            weakest_scaled_eigenvector=v.tolist(),physical_unit_tangent=physical.tolist(),loading=loading,
            focal_optical_axis_dominant=bool(loading['f']+loading['tz']>.5 and min(loading['f'],loading['tz'])>.05),
            direct_gram_relative_error=gramerr,direct_gram_active_eigenvalues=np.linalg.eigvalsh(gram).tolist(),
            fixed_point_scans=scans))
    # How many cameras a spectral floor would actually change. Include the
    # native intrinsic prior, since that is the production model to be modified.
    floors=[]
    for kind in ['block','global']:
        for eps in [.001,.01,.1]:
            threshold=eps*(pv[:,-1] if kind=='block' else np.full(nc,np.median(pv[:,-1])))
            touched=np.any(pv<threshold[:,None],axis=1)
            floors.append(dict(kind=kind,epsilon=eps,touched_count=int(touched.sum()),touched_fraction=float(touched.mean()),
                touched_camera_ids=np.flatnonzero(touched).tolist()))
    caps=[]
    if cap_screen and radius>0:
        def complete(z):
            dc=E*z;yc=np.einsum('nri,ni->nr',Jc,dc[ci])
            rhs=aggregate(np.einsum('nri,nr->ni',Jp,r+yc),pi,np_)
            return dc,-point_inverse(Ri,rhs)
        for rep in range(3):
            for c in [None,3,10,30]:
                factor=np.ones(nc) if c is None else np.minimum(1,c*np.median(norms)/np.maximum(norms,1e-300))
                z=raw*factor[:,None];inter=float(np.linalg.norm(z));globalfactor=min(1,radius/max(inter,1e-300))
                touched=factor<1;z*=globalfactor;dc,dp=complete(z);score=S.audit(cam,X,ci,pi,uv,dc,dp,E)
                caps.append(dict(rep=rep,arm='clipped' if c is None else 'cap'+str(c),cap=c,
                    locally_touched=int(touched.sum()),touched_fraction=float(touched.mean()),
                    touched_camera_ids=np.flatnonzero(touched).tolist(),intermediate_radius_ratio=inter/radius,
                    remaining_global_factor=globalfactor,healthy_camera_fraction_retained=globalfactor,
                    **{k:(v if not isinstance(v,float) or np.isfinite(v) else None) for k,v in score.items()}))
    return dict(label=label,scene=scene,metadata=meta,score_init=initial,source_files={p.name:sha(p) for p in folder.iterdir() if p.is_file() and p.suffix in ['.f64','.txt']},
        observation_input_sha256=sha('/workspace/bal/'+scene+'.txt'),camera_count=nc,median_observations=median_count,
        median_smallest_active_eigenvalue=median_eig,median_largest_active_eigenvalue=maxmed,
        active_spectrum_all_cameras=vals.tolist(),active_spectrum_with_prior_all_cameras=pv.tolist(),
        raw_radius_ratio=totalnorm/radius if radius>0 else None,top5=entries,symmetry_absolute_error=symmetry,
        floor_locality_screen=floors,cap_witness_rows=caps,seconds=time.perf_counter()-start,
        scope='Coherent fixed-state diagnostics. Repeated calculations are not independent solver runs. Eigenvector scans hold points fixed; cap scores recomplete points and retain the full objective.')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['primary','terminal']);a=ap.parse_args()
    write(P/'baseline_verification.json',verify_baseline())
    if a.stage=='primary':
        for scene,rep in [('venice-52',i) for i in (0,1,2)]+[('final-3068',i) for i in (0,5,6)]+[('ladybug-1197',0)]:
            label=f'{scene}-{rep}';out=P/'forensics'/f'{label}.json'
            if out.exists():continue
            print('E1 START',label,flush=True);r=audit(C/'evidence/collect'/f'{scene}-capture-{rep}',scene,label)
            write(out,r);print('E1 DONE',label,'top',[(x['camera'],x['observations'],x['count_starved'],x['spectrally_starved'],x['loading']) for x in r['top5']],flush=True)
            print('E2 CAPS',[(x['arm'],x['touched_fraction'],x['intermediate_radius_ratio'],x['true_decrease']) for x in r['cap_witness_rows'][:4]],flush=True)
    else:
        for rep in range(5):
            label=f'venice-terminal-{rep}';out=P/'forensics'/f'{label}.json'
            if out.exists():continue
            source=W/'composition'/f'terminal-static-0-{rep}';m=json.loads((source/'archive.json').read_text());arc=Path(m['path']);assert sha(arc)==m['sha256']
            with tempfile.TemporaryDirectory(prefix='e1-terminal-',dir='/dev/shm') as tmp:
                target=Path(tmp)
                if '.xor.' in arc.name:
                    FA.restore(arc,target)
                else:
                    with tarfile.open(arc) as tf:tf.extractall(target,filter='data')
                print('E1 START',label,flush=True);r=audit(target/'0','venice-52',label)
                r['archive_source']=m;write(out,r);print('E1 DONE',label,[(x['camera'],x['observations'],x['loading']) for x in r['top5']],flush=True)
if __name__=='__main__':main()
