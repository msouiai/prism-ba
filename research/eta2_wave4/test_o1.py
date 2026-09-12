"""Independent NumPy object-space QP/KKT audit of actual GPU kernels."""
from pathlib import Path
import fcntl,hashlib,json,os,subprocess
os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
P=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def check(path):
 d=json.loads(path.read_text())
 if d['mode']==4:return dict(mode=4,passed=d['expected_guard'],scope='unsupported fourth point constraint fails explicitly, not a solved QP',reason=d['reason'],sha256=sha(path))
 nc,np_=d['nc'],d['np'];n=3*(nc+np_)
 R=np.array(d['R']).reshape(nc,3,3);t=np.array(d['t']).reshape(nc,3);X=np.array(d['X']).reshape(np_,3);intr=np.array(d['intr']).reshape(3,nc)
 uv=np.array(d['uv']).reshape(np_,nc,2);ray=np.array(d['ray']).reshape(np_,nc,3);weight=np.array(d['weight']).reshape(np_,nc)
 H=np.zeros((n,n));b=np.zeros(n);B=[];h=[];rerr=0;werr=0
 U=np.zeros((nc,3,3));V=np.zeros((np_,3,3));W=np.zeros((np_,nc,3,3))
 for j in range(np_):
  for c in range(nc):
   Y=R[c]@X[j]+t[c];q=-Y[:2]/Y[2];obs=uv[j,c]/intr[0,c];k=intr[1,c];un=np.linalg.norm(obs)
   roots=np.roots([k,0,1,-un]) if k else [un]
   roots=[float(np.real(x)) for x in roots if abs(np.imag(x))<1e-8]
   radius=min(roots,key=lambda a:np.linalg.norm(obs*a/un-q)) if un else 0
   vv=np.r_[-obs*radius/un,1.] if un else np.array([0.,0.,1.]);vv/=np.linalg.norm(vv)
   rerr=max(rerr,np.linalg.norm(vv-ray[j,c]));PP=np.eye(3)-np.outer(vv,vv);e=PP@Y
   rr=intr[0,c]*(1+k*(q@q))*q-uv[j,c];w=(rr@rr)/(e@e) if e@e>1e-30 else intr[0,c]**2/Y[2]**2
   werr=max(werr,abs(w/weight[j,c]-1));J=np.zeros((3,n));J[:,3*c:3*c+3]=PP;J[:,3*nc+3*j:3*nc+3*j+3]=PP@R[c]
   H+=w*J.T@J;b-=w*J.T@e;U[c]+=w*PP;V[j]+=w*R[c].T@PP@R[c];W[j,c]=w*PP@R[c]
   row=np.zeros(n);sg=np.sign(Y[2]);row[3*c+2]=sg;row[3*nc+3*j:3*nc+3*j+3]=sg*R[c,2];B.append(row);h.append(-.5*abs(Y[2]))
 B=np.array(B);h=np.array(h)
 if d['mode']==1:
  desired=np.zeros(n);desired[3*nc+2]=-.9*X[0,2];b=H@desired
 bg=np.r_[d['bc'],d['bp']];block_error=max(np.linalg.norm(U-np.array(d['U']).reshape(U.shape))/np.linalg.norm(U),np.linalg.norm(V-np.array(d['V']).reshape(V.shape))/np.linalg.norm(V),np.linalg.norm(W-np.array(d['W']).reshape(W.shape))/np.linalg.norm(W))
 rhs_error=np.linalg.norm(b-bg)/np.linalg.norm(b)
 G=np.zeros((4,n));G[:3,:3]=np.eye(3);G[3,3*d['far']:3*d['far']+3]=d['axis']
 act=d['act'];A=np.vstack([G,B[act]]);hh=np.r_[np.zeros(4),h[act]]
 K=np.block([[H,A.T],[A,np.zeros((len(A),len(A)))]])
 ref=np.linalg.solve(K,np.r_[b,hh]);step=np.r_[d['dt'],d['dX']]
 relative=np.linalg.norm(step-ref[:n])/max(1.,np.linalg.norm(ref[:n]));stationarity=np.linalg.norm(H@step+A.T@ref[n:]-b)/np.linalg.norm(b)
 feasibility=max(0.,float(np.max((h-B@step)/np.maximum(abs(h)*2,1e-12))))
 equality=np.linalg.norm(A@step-hh)/max(1.,np.linalg.norm(hh));dual=max(0.,float(max(ref[n+4:],default=0)))
 # Equality-only case 2 checks the exact constrained Schur algebra, not an inequality optimum.
 passed=block_error<1e-10 and rhs_error<1e-9 and relative<5e-5 and stationarity<1e-6 and equality<1e-7 and rerr<1e-8 and werr<1e-7 and d['rank_failure_checked']
 if d['mode']!=2:passed=passed and feasibility<1e-7 and dual<1e-6*max(1,np.linalg.norm(b))
 extra={}
 if d['mode']==5:
  rotations=R.copy();ii=intr.copy()
  for c in range(nc):
   Y=X@R[c].T+t[c];vv=ray[:,c];targets=vv*np.sum(vv*Y,axis=1)[:,None]-t[c];cov=(targets*weight[:,c,None]).T@X
   u,sv,vh=np.linalg.svd(cov);D=np.eye(3);D[2,2]=np.linalg.det(u@vh);rot=u@D@vh
   if np.all(np.sign(Y[:,2])*(X@rot.T+t[c])[:,2]>=.5*abs(Y[:,2])):rotations[c]=rot
   Yn=X@rotations[c].T+t[c];q=-Yn[:,:2]/Yn[:,2,None];qq=np.sum(q*q,axis=1);M=np.stack([q,q*qq[:,None]],axis=2).reshape(-1,2)
   a,b=np.linalg.lstsq(M,uv[:,c].reshape(-1),rcond=None)[0];ii[0,c]=a;ii[1,c]=b/a
  extra=dict(rotation_error=float(np.linalg.norm(rotations-np.array(d['rotation_updated']).reshape(R.shape))),intrinsics_error=float(np.linalg.norm(ii-np.array(d['intrinsics_updated']).reshape(intr.shape))/np.linalg.norm(ii)))
  passed=passed and extra['rotation_error']<1e-9 and extra['intrinsics_error']<1e-9
 return dict(mode=d['mode'],passed=bool(passed),ray_error=rerr,weight_error=werr,block_error=block_error,rhs_error=rhs_error,dense_step_relative_error=relative,stationarity=stationarity,feasibility=feasibility,equality=equality,dual_sign_error=dual,active=act,sha256=sha(path),**extra)
def main():
 b=P/'build/o1-kernel-test';cmd=['nvcc','-O3','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',str(P/'o1_kernel_test.cu'),'-o',str(b),'-lcublas']
 with (P/'build/o1-kernel-build.log').open('w') as f:subprocess.run(cmd,env=dict(os.environ,TMPDIR='/dev/shm'),stdout=f,stderr=subprocess.STDOUT,check=True)
 rows=[]
 with open('/tmp/prism_gpu.lock','w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  for mode in range(6):
   dest=P/'build'/f'o1-qp-{mode}.json';log=P/'build'/f'o1-qp-{mode}.log'
   with log.open('w') as f:subprocess.run(['compute-sanitizer','--tool','memcheck','--error-exitcode','97',str(b),str(dest),str(mode)],stdout=f,stderr=subprocess.STDOUT,check=True)
   assert 'ERROR SUMMARY: 0 errors' in log.read_text();rows.append(check(dest));print(rows[-1],flush=True)
 r=dict(passed=all(x['passed'] for x in rows),rows=rows,command=cmd,binary_sha256=sha(b),header_sha256=sha(P/'o1.cuh'),test_sha256=sha(__file__))
 (P/'o1-kernel-validation.json').write_text(json.dumps(r,indent=2)+'\n');assert r['passed'],r
if __name__=='__main__':main()
