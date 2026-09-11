#!/usr/bin/env python3
"""Independent CPU same-vector Schur and nonnegative Jacobian-energy audit."""
import csv,fcntl,hashlib,json,math,os,sys
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent
sys.path.insert(0,str(P.parent/'eta2_champion/bench'))
from audit_prism_state import audit,observations
LD=np.longdouble
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def forward(R,b):
    y=np.empty_like(b,dtype=LD)
    y[:,0]=b[:,0]/R[:,0]
    y[:,1]=(b[:,1]-R[:,1]*y[:,0])/R[:,3]
    y[:,2]=(b[:,2]-R[:,2]*y[:,0]-R[:,4]*y[:,1])/R[:,5]
    return y
def backward(R,b):
    x=np.empty_like(b,dtype=LD)
    x[:,2]=b[:,2]/R[:,5]
    x[:,1]=(b[:,1]-R[:,4]*x[:,2])/R[:,3]
    x[:,0]=(b[:,0]-R[:,1]*x[:,1]-R[:,2]*x[:,2])/R[:,0]
    return x
def analyze(folder):
    meta={k:float(v) for k,v in (l.split('=') for l in (folder/'metadata.txt').read_text().splitlines())}
    nc,np_,no=(int(meta[k]) for k in ['ncam','npt','nobs'])
    def read(name,shape=None):
        dtype='<f8' if name.endswith('.f64') else '<f4' if name.endswith('.f32') else '<i4'
        a=np.fromfile(folder/name,dtype=dtype)
        assert a.size==(np.prod(shape) if shape is not None else a.size),(name,a.size,shape)
        return a.reshape(shape) if shape else a
    complete=json.loads((folder/'capture_complete.json').read_text())
    for name,f in complete['files'].items():assert sha(folder/name)==f['sha256'],name
    p=read('direction.f64',(nc,9)).astype(LD);pp=np.sum(p*p,dtype=LD);z=p/np.sqrt(pp)
    E=read('E.f64',(nc,9)).astype(LD);v=E*z
    H=read('Hcc.f64',(nc,9,9)).astype(LD)
    camera=np.einsum('ci,cij,cj->',v,H,v,dtype=LD)
    fc=read('fragment_cams.i32',(no,));fp=read('fragment_points.i32',(no,))
    oc=read('obs_cams.i32',(no,));op=read('obs_points.i32',(no,));slot=read('o2slot.i32',(no,))
    assert np.array_equal(fc[slot],oc) and np.array_equal(fp[slot],op)
    W32=read('W32.f32',(9,3,no));W64=read('W64.f64',(9,3,no))
    g={};rounding={}
    for label,W in [('W32',W32),('W64',W64)]:
        b=np.zeros((np_,3),dtype=LD)
        for lo in range(0,no,8192):
            hi=min(no,lo+8192);block=W[:,:,lo:hi].transpose(2,0,1).astype(LD)
            t=np.einsum('oij,oi->oj',block,v[fc[lo:hi]],dtype=LD)
            np.add.at(b,fp[lo:hi],t)
        g[label]=b
    factors={k:read(name,(np_,6)).astype(LD) for k,name in
             [('stored','R_stored.f64'),('R32qr','R_fp32qr.f64'),('R64qr','R_fp64qr.f64')]}
    assert all(np.isfinite(r).all() and (r[:,[0,3,5]]>0).all() for r in factors.values())
    names={'stored':('W32','stored'),'W32_R32qr':('W32','R32qr'),
           'W64_Rstored':('W64','stored'),'W32_R64qr':('W32','R64qr'),'W64_R64qr':('W64','R64qr')}
    quotients={};point_terms={}
    for name,(w,r) in names.items():
        y=forward(factors[r],g[w]);point=np.sum(y*y,dtype=LD)
        quotients[name]=float(camera-point+LD(meta['lambda']));point_terms[name]=float(point)
    gpu=list(csv.DictReader((folder/'gpu_rayleigh.csv').open()))
    repeat=[float(r['quotient']) for r in gpu if r['operator']=='stored_repeat']
    differences={r['operator']:float(r['quotient'])-quotients[r['operator']] for r in gpu if r['operator'] in quotients}
    # Exact camera rows and point rows from this same accepted state.
    J=read('Jc64.f64',(no,2,9));B=read('B64.f64',(no,2,3))
    jv=np.empty((no,2),dtype=LD);bref=np.zeros((np_,3),dtype=LD)
    camera_rows=LD(0)
    for lo in range(0,no,8192):
        hi=min(no,lo+8192);j=J[lo:hi].astype(LD);b=B[lo:hi].astype(LD)
        jv[lo:hi]=np.einsum('ori,oi->or',j,v[oc[lo:hi]],dtype=LD)
        camera_rows+=np.sum(jv[lo:hi]**2,dtype=LD)
        np.add.at(bref,op[lo:hi],np.einsum('ori,or->oi',b,jv[lo:hi],dtype=LD))
    y=backward(factors['R64qr'],forward(factors['R64qr'],bref))
    residual_energy=LD(0)
    for lo in range(0,no,8192):
        hi=min(no,lo+8192)
        r=jv[lo:hi]-np.einsum('ori,oi->or',B[lo:hi].astype(LD),y[op[lo:hi]],dtype=LD)
        residual_energy+=np.sum(r*r,dtype=LD)
    C=read('Cdiag.f64',(np_,3));tau=meta['tau']
    fl=tau*C.sum(axis=1)/3;fl=np.where(fl>0,fl,1e-32)
    damping=np.maximum(tau*C,1e-3*fl[:,None]).astype(LD)
    point_damping=np.sum(damping*y*y,dtype=LD)
    R=read('R_state.f64',(nc,3,3));t=read('t_state.f64',(nc,3));X=read('X_state.f64',(np_,3))
    intr=read('intr_state.f64',(3,nc));r2sum=np.zeros(nc,dtype=LD);counts=np.bincount(oc,minlength=nc)
    for lo in range(0,no,8192):
        hi=min(no,lo+8192);cc=oc[lo:hi];pt=op[lo:hi]
        xyz=np.einsum('oij,oj->oi',R[cc].astype(LD),X[pt].astype(LD))+t[cc].astype(LD)
        r2=(xyz[:,0]**2+xyz[:,1]**2)/xyz[:,2]**2;np.add.at(r2sum,cc,r2)
    mean=np.maximum(r2sum/np.maximum(counts,1),LD(1e-12));weight=LD(meta['intr_damp'])
    diagf=weight/(LD(.5)*np.abs(intr[0].astype(LD))+LD(.001))**2
    diagk=weight*mean**2
    prior=np.sum(np.where(counts>0,diagf*v[:,6]**2+diagk*v[:,7]**2,0),dtype=LD)
    assert meta['k2mask']==0
    stable=residual_energy+point_damping+prior+LD(meta['lambda'])
    row_schur=camera_rows+prior-np.sum(forward(factors['R64qr'],bref)**2,dtype=LD)+LD(meta['lambda'])
    Werr=np.linalg.norm((W32.astype(np.float64)-W64).ravel())/np.linalg.norm(W64.ravel())
    B32=read('B32.f32',(no,2,3));Berr=np.linalg.norm((B32.astype(np.float64)-B).ravel())/np.linalg.norm(B.ravel())
    Hnew=read('Hcc_rebuilt.f64',(nc,9,9)).astype(LD)
    h_delta=np.einsum('ci,cij,cj->',v,Hnew-H,v,dtype=LD)
    state_cost=audit(folder/'endpoint.state',*observations(Path('/workspace/bal/venice-52.txt')))
    assert abs(state_cost-meta['cost'])/meta['cost']<1e-6
    actual=read('actual_product.f64',(nc,9)).astype(LD)
    actual_q=np.sum(actual*p,dtype=LD)/pp
    q=meta['quotient']
    classification='nonfinite' if not math.isfinite(q) else 'negative' if q<0 else 'zero' if q==0 else 'small_positive'
    # Exact fixed-factor perturbation identity for rounding W alone:
    # delta q = -2 <R^-T W64^T v, R^-T deltaW^T v> - ||R^-T deltaW^T v||^2.
    y64=forward(factors['stored'],g['W64'])
    dy=forward(factors['stored'],g['W32']-g['W64'])
    linear=-2*np.sum(y64*dy,axis=1,dtype=LD)
    quadratic=-np.sum(dy*dy,axis=1,dtype=LD)
    point_error=linear+quadratic
    tracks=np.bincount(op,minlength=np_)
    bins={}
    for label,mask in [('2',tracks==2),('3',tracks==3),('4',tracks==4),('5+',tracks>=5),('0-1',tracks<2)]:
        bins[label]=dict(points=int(mask.sum()),signed_rayleigh_error=float(np.sum(point_error[mask],dtype=LD)),
                         absolute_rayleigh_error=float(np.sum(np.abs(point_error[mask]),dtype=LD)))
    worst=np.argsort(point_error)[:10]
    perturbation=dict(linear=float(np.sum(linear,dtype=LD)),quadratic=float(np.sum(quadratic,dtype=LD)),
        total=float(np.sum(point_error,dtype=LD)),track_bins=bins,
        worst_points=[dict(point=int(i),observations=int(tracks[i]),error=float(point_error[i])) for i in worst])
    assert abs(perturbation['total']-(quotients['stored']-quotients['W64_Rstored']))<1e-15
    result=dict(metadata=meta,cutoff_class=classification,actual_cpu_dot_quotient=float(actual_q),
        cpu_schur_quotients=quotients,gpu_rows=gpu,gpu_stored_repeat_range=[min(repeat),max(repeat)],
        gpu_minus_cpu_quotients=differences,camera_energy=float(camera),point_schur_terms=point_terms,
        stable_fp64_energy=float(stable),jacobian_rows_schur=float(row_schur),
        stable_terms=dict(residual=float(residual_energy),point_damping=float(point_damping),intrinsic_prior=float(prior),camera_damping=meta['lambda']),
        camera_block_vs_rows_plus_prior=float(camera-camera_rows-prior),
        camera_reassembly_rayleigh_delta=float(h_delta),cross_rounding_relative_frobenius=float(Werr),point_rows_rounding_relative_frobenius=float(Berr),
        cross_rounding_perturbation=perturbation,
        cpu_independent_cost=state_cost,longdouble_bits=np.finfo(LD).nmant+1)
    assert abs(float(actual_q)-q)<1e-10*max(1,abs(q))
    assert max(abs(v) for v in differences.values())<1e-10*max(1,abs(float(camera)))
    assert stable>=meta['lambda']
    assert abs(float(stable)-float(row_schur))<1e-10*max(1,abs(float(camera)))
    assert abs(quotients['W64_R64qr']-float(stable))<1e-10*max(1,abs(float(camera)))
    (folder/'audit.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(folder.name,classification,'mixed',q,'fp64',quotients['W64_R64qr'],'stable',float(stable),flush=True)
    return result
def main():
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        rows=[analyze(f) for f in sorted((P/'evidence').glob('capture-*'))]
    (P/'results.json').write_text(json.dumps(rows,indent=2,allow_nan=False)+'\n')
if __name__=='__main__':main()
