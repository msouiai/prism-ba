#!/usr/bin/env python3
"""Cross-trajectory audit: explicit Schur matrices and same-vector Rayleigh checks."""
import argparse,csv,fcntl,hashlib,json,os,struct,subprocess,sys
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix
P=Path(__file__).resolve().parent;F=P.parent/'eta2_champion'
INPUT=Path('/workspace/collab/results/v52_states')
sys.path.insert(0,str(F/'bench'))
from audit_prism_state import observations,audit
LD=np.longdouble
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def forward(R,b):
    y=np.empty_like(b,dtype=LD)
    y[:,0]=b[:,0]/R[:,0]
    y[:,1]=(b[:,1]-R[:,1]*y[:,0])/R[:,3]
    y[:,2]=(b[:,2]-R[:,2]*y[:,0]-R[:,4]*y[:,1])/R[:,5]
    return y
def dense_audit(folder,obs):
    meta={k:float(v) for k,v in (l.split('=') for l in (folder/'metadata.txt').read_text().splitlines())}
    nc,np_,no=(int(meta[k]) for k in ['ncam','npt','nobs']);dim=nc*9
    assert nc==52 and meta['lambda']==1e-8 and meta['tau']==1e-8 and meta['k2mask']==0
    assert meta['outer']==0 and meta['cg_completed']==0
    def read(n,shape):
        dtype='<f8' if n.endswith('f64') else '<f4' if n.endswith('f32') else '<i4'
        return np.fromfile(folder/n,dtype=dtype).reshape(shape)
    E=read('E.f64',(nc,9));H=read('Hcc.f64',(nc,9,9))
    fc=read('fragment_cams.i32',(no,));fp=read('fragment_points.i32',(no,))
    oc=read('obs_cams.i32',(no,));op=read('obs_points.i32',(no,));slot=read('o2slot.i32',(no,))
    assert np.array_equal(fc[slot],oc) and np.array_equal(fp[slot],op)
    assert np.array_equal(oc,obs[:,0]) and np.array_equal(op,obs[:,1])
    original=read('direction.f64',(nc,9));original_norm=np.linalg.norm(original)
    W32=read('W32.f32',(9,3,no));W64=read('W64.f64',(9,3,no))
    Rs=read('R_stored.f64',(np_,6));R64=read('R_fp64qr.f64',(np_,6))
    assert np.all(np.isfinite(Rs)) and np.all(Rs[:,[0,3,5]]>0)
    assert np.all(np.isfinite(R64)) and np.all(R64[:,[0,3,5]]>0)
    U=np.zeros((dim,dim))
    for c in range(nc):U[9*c:9*c+9,9*c:9*c+9]=H[c]*E[c,:,None]*E[c,None,:]
    U.flat[::dim+1]+=meta['lambda']
    # Per-observation R^-T W_o^T E_c, coalescing multiple observations of a
    # point-camera pair BEFORE forming F^T F. No assumption of unique edges.
    rows=np.broadcast_to((3*fp[:,None,None]+np.arange(3)[None,:,None]),(no,3,9)).reshape(-1).astype(np.int32)
    cols=np.broadcast_to((9*fc[:,None,None]+np.arange(9)[None,None,:]),(no,3,9)).reshape(-1).astype(np.int32)
    specs={'stored':(W32,Rs),'W64_Rstored':(W64,Rs),'W64_R64qr':(W64,R64)}
    matrices={};eigens={};checks={}
    for name,(W,R) in specs.items():
        data=np.empty((no,3,9))
        for lo in range(0,no,8192):
            hi=min(no,lo+8192);r=R[fp[lo:hi]]
            b=W[:,:,lo:hi].transpose(2,1,0).astype(np.float64)*E[fc[lo:hi],None,:]
            y=data[lo:hi]
            y[:,0]=b[:,0]/r[:,0,None]
            y[:,1]=(b[:,1]-r[:,1,None]*y[:,0])/r[:,3,None]
            y[:,2]=(b[:,2]-r[:,2,None]*y[:,0]-r[:,4,None]*y[:,1])/r[:,5,None]
        matrix=coo_matrix((data.reshape(-1),(rows,cols)),shape=(np_*3,dim)).tocsr()
        A=U-(matrix.T@matrix).toarray();del matrix,data
        symmetry=float(np.max(np.abs(A-A.T)));A=(A+A.T)*.5
        vals,vecs=np.linalg.eigh(A);matrices[name]=A;eigens[name]=(vals,vecs)
        native=read(name+'_product.f64',(dim,))/original_norm
        mv=A@(original.reshape(-1)/original_norm)
        err=float(np.linalg.norm(mv-native));rel=err/max(np.linalg.norm(native),1e-300)
        assert rel<1e-7,(name,rel)
        checks[name]=dict(min_eigenvalue=float(vals[0]),negative_eigenvalues=int((vals<0).sum()),
          below_cutoff=int((vals<=1e-14).sum()),symmetry_error=symmetry,native_product_absolute_error=err,
          native_product_relative_error=float(rel))
    # Extended precision Rayleigh evaluation of the SAME mixed minimum
    # eigenvector, independent of dense assembly/eigensolver cancellation.
    z=eigens['stored'][1][:,0].reshape(nc,9).astype(LD);v=z*E.astype(LD)
    camera=np.einsum('ci,cij,cj->',v,H.astype(LD),v,dtype=LD)
    quotients={}
    for name,(W,R) in specs.items():
        g=np.zeros((np_,3),dtype=LD)
        for lo in range(0,no,8192):
            hi=min(no,lo+8192)
            t=np.einsum('oij,oi->oj',W[:,:,lo:hi].transpose(2,0,1).astype(LD),v[fc[lo:hi]],dtype=LD)
            np.add.at(g,fp[lo:hi],t)
        y=forward(R.astype(LD),g)
        q=float(camera-np.sum(y*y,dtype=LD)+LD(meta['lambda'])*np.sum(z*z,dtype=LD))
        dense=float(z.reshape(-1).astype(float)@matrices[name]@z.reshape(-1).astype(float))
        assert abs(q-dense)<1e-10,(name,q,dense)
        quotients[name]=dict(extended_rayleigh=q,dense_rayleigh=dense,difference=q-dense)
    # Independent nonnegative full-Jacobian energy at the eliminated point
    # minimizer. This avoids Schur cancellation in the FP64 reference check.
    J=read('Jc64.f64',(no,2,9));B=read('B64.f64',(no,2,3))
    jv=np.empty((no,2),dtype=LD);g=np.zeros((np_,3),dtype=LD)
    for lo in range(0,no,8192):
        hi=min(no,lo+8192)
        jv[lo:hi]=np.einsum('ori,oi->or',J[lo:hi].astype(LD),v[oc[lo:hi]],dtype=LD)
        np.add.at(g,op[lo:hi],np.einsum('ori,or->oi',B[lo:hi].astype(LD),jv[lo:hi],dtype=LD))
    r=R64.astype(LD);y=forward(r,g);x=np.empty_like(y)
    x[:,2]=y[:,2]/r[:,5]
    x[:,1]=(y[:,1]-r[:,4]*x[:,2])/r[:,3]
    x[:,0]=(y[:,0]-r[:,1]*x[:,1]-r[:,2]*x[:,2])/r[:,0]
    residual=LD(0)
    R=read('R_state.f64',(nc,3,3)).astype(LD);t=read('t_state.f64',(nc,3)).astype(LD)
    X=read('X_state.f64',(np_,3)).astype(LD);intr=read('intr_state.f64',(3,nc)).astype(LD)
    radius_sum=np.zeros(nc,dtype=LD);counts=np.bincount(oc,minlength=nc)
    for lo in range(0,no,8192):
        hi=min(no,lo+8192);cc=oc[lo:hi];pt=op[lo:hi]
        rem=jv[lo:hi]-np.einsum('ori,oi->or',B[lo:hi].astype(LD),x[pt],dtype=LD)
        residual+=np.sum(rem*rem,dtype=LD)
        q=np.einsum('oij,oj->oi',R[cc],X[pt],dtype=LD)+t[cc]
        np.add.at(radius_sum,cc,(q[:,0]**2+q[:,1]**2)/q[:,2]**2)
    C=read('Cdiag.f64',(np_,3)).astype(LD);tau=LD(meta['tau'])
    floor=tau*np.sum(C,axis=1)/3;floor=np.where(floor>0,floor,LD(1e-32))
    D=np.maximum(tau*C,LD(.001)*floor[:,None])
    point_damping=np.sum(D*x*x,dtype=LD)
    mean=np.maximum(radius_sum/np.maximum(counts,1),LD(1e-12))
    prior=LD(meta['intr_damp'])*np.sum(np.where(counts>0,
      (v[:,6]/(LD(.5)*abs(intr[0])+LD(.001)))**2+(mean*v[:,7])**2,0),dtype=LD)
    camera_damping=LD(meta['lambda'])*np.sum(z*z,dtype=LD)
    stable=residual+point_damping+prior+camera_damping
    assert stable>=camera_damping and abs(float(stable)-quotients['W64_R64qr']['extended_rayleigh'])<1e-10
    cost=audit(folder/'endpoint.state',(nc,np_,no),obs)
    assert abs(cost-meta['cost'])/cost<1e-7
    # Ensure that the capture made no state update: the endpoint equals all
    # four arrays saved inside the initial linearization, byte for byte.
    endpoint=(folder/'endpoint.state').read_bytes()
    assert endpoint[:8]==b'PRISMS01' and struct.unpack('<QQQ',endpoint[8:32])==(nc,np_,no)
    expected=b''.join((folder/n).read_bytes() for n in ['R_state.f64','t_state.f64','X_state.f64','intr_state.f64'])
    assert endpoint[32:]==expected
    np.savez_compressed(folder/'dense_operators.npz',**matrices,
        mixed_min_vector=eigens['stored'][1][:,0],
        **{name+'_eigenvalues':v[0] for name,v in eigens.items()})
    result=dict(state=folder.name,metadata=meta,independent_cost=cost,operators=checks,
      mixed_min_vector_quotients=quotients,longdouble_significand_bits=np.finfo(LD).nmant+1,
      stable_full_jacobian_energy=float(stable),stable_terms=dict(residual=float(residual),
        point_damping=float(point_damping),intrinsics_prior=float(prior),camera_damping=float(camera_damping)),
      state_unchanged=True,dense_artifact_sha256=sha(folder/'dense_operators.npz'))
    write(folder/'audit.json',result)
    return result
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['opening','tail','all'],default='all');a=ap.parse_args()
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        external=P/'evidence/external';external.mkdir(parents=True,exist_ok=True)
        manifest=json.loads((INPUT/'MANIFEST.json').read_text())
        assert len(manifest)==18
        arch=INPUT/'v52_states.tgz'
        assert sha(arch)=='c73caa99310c603596c88c84005a1c0c4181f474172454bc3ee733c66f02f35a'
        dims,obs=observations(Path('/workspace/bal/venice-52.txt'))
        verified={}
        for name,m in manifest.items():
            f=INPUT/name;assert sha(f)==m['sha256'],name
            d,o=observations(f);assert d==dims and np.array_equal(o,obs),name
            with f.open() as stream:
                for _ in range(1+dims[2]):stream.readline()
                params=np.loadtxt(stream)
            assert params.size==9*dims[0]+3*dims[1]
            assert np.all(params[:9*dims[0]].reshape(-1,9)[:,8]==0),name
            verified[name]=dict(**m,observations_exact=True,k2_zero=True,bytes=f.stat().st_size)
        write(P/'external-inputs.json',dict(archive_sha256=sha(arch),manifest_sha256=sha(INPUT/'MANIFEST.json'),states=verified))
        print('VERIFIED all 18 hashes, observations, dimensions and k2',flush=True)
        bm=json.loads((P/'build/external-manifest.json').read_text())
        binary=P/'build/prism-external';assert sha(binary)==bm['binary_sha256']
        champ=json.loads((F/'champion.json').read_text())
        order=sorted(manifest,key=lambda n:(manifest[n]['outer'],n))
        for name in order:
            opening=manifest[name]['outer'] in [40,60]
            if (a.phase=='opening' and not opening) or (a.phase=='tail' and opening):continue
            folder=external/Path(name).stem;folder.mkdir(exist_ok=True)
            done=folder/'complete.json'
            if done.exists():continue
            print('EXTERNAL',name,flush=True)
            flags=dict(champ['flags'],OCA_CURVATURE_CAPTURE=str(folder),OCA_CURVATURE_AT_START='1')
            env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','MF_DEBUG','CASPAR_','CERES_','COLMAP_MFREE'))};env.update(flags)
            cmd=[str(binary),'--problem',str(INPUT/name),'--algo','mfree_shifted_cg','--dof9','--zero_k2',
                 '--lam0','1e-8','--max_iter','1','--state_out',str(folder/'endpoint.state')]
            write(folder/'manifest.json',dict(command=cmd,flags=flags,input_sha256=manifest[name]['sha256'],
              binary_sha256=bm['binary_sha256'],source_sha256=bm['source_sha256'],protocol_sha256=sha(P/'PROTOCOL.md'),diagnostic_only=True))
            with (folder/'stdout.log').open('w') as out,(folder/'stderr.log').open('w') as err:
                rc=subprocess.run(cmd,env=env,stdout=out,stderr=err,timeout=180).returncode
            assert rc==0,rc
            text=(folder/'stdout.log').read_text();assert 'CURVATURE_AUDIT diagnostic_complete' in text
            files={f.name:dict(sha256=sha(f),bytes=f.stat().st_size) for f in folder.iterdir() if f.is_file()}
            write(folder/'capture_complete.json',dict(returncode=rc,files=files))
            result=dense_audit(folder,obs)
            # Manifest costs are rounded to .1; allow .2 objective units.
            assert abs(result['independent_cost']-manifest[name]['cost_near'])<.2,(name,result['independent_cost'])
            print('EIGENS',name,{k:v['min_eigenvalue'] for k,v in result['operators'].items()},flush=True)
            print('SAME_VECTOR',name,result['mixed_min_vector_quotients'],flush=True)
            # Keep first complete capture; others are reproducible transient
            # arrays with hashes retained and dense evidence verified above.
            removed=[]
            if name!=order[0]:
                for f in folder.iterdir():
                    if f.suffix in ['.f64','.f32','.i32','.state']:
                        assert sha(f)==files[f.name]['sha256']
                        removed.append(f.name);f.unlink()
            write(done,dict(valid=True,transient_arrays_removed=removed,retained_full_capture=not removed,
              audit_sha256=sha(folder/'audit.json'),dense_sha256=sha(folder/'dense_operators.npz')))
        rows=[json.loads(f.read_text()) for f in sorted(external.glob('*/audit.json'))]
        write(P/'external-results.json',rows)
if __name__=='__main__':main()
