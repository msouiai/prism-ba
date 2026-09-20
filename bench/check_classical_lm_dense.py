"""Independent finite-difference dense LM check on a tiny synthetic BAL problem."""
import pathlib,json,os,subprocess,sys
import numpy as np
from solver_novelty_ablation import flags,BIN
from build_tr_candidate import sha
from audit_prism_state import audit,observations
root=pathlib.Path('/workspace/prism-tr-novelty-ablation/dense-check-v2');root.mkdir();rng=np.random.default_rng(319);nc,np_=5,20;n=9*nc+3*np_
def exp(w):
 a=np.linalg.norm(w);K=np.array([[0,-w[2],w[1]],[w[2],0,-w[0]],[-w[1],w[0],0]]);return np.eye(3)+np.sinc(a/np.pi)*K+.5*np.sinc(a/(2*np.pi))**2*(K@K)
w=rng.normal(0,.02,(nc,3));R=np.array([exp(a) for a in w]);t=rng.normal(0,.3,(nc,3));X=rng.normal(0,.7,(np_,3));X[:,2]-=5;intr=np.tile([700.,.01,0.],(nc,1));ci=np.repeat(np.arange(nc),np_);pi=np.tile(np.arange(np_),nc)
def evaluate(d):
 dc=d[:9*nc].reshape(nc,9);dp=d[9*nc:].reshape(np_,3);r=np.array([exp(dc[c,:3])@R[c] for c in range(nc)]);q=np.einsum('nij,nj->ni',r[ci],(X+dp)[pi])+t[ci]+dc[ci,3:6];uv=-q[:,:2]/q[:,2,None];rad=np.sum(uv*uv,axis=1);f=intr[ci,0]+dc[ci,6];k1=intr[ci,1]+dc[ci,7];return (uv*(f*(1+k1*rad))[:,None]).reshape(-1)
zero=np.zeros(n);obs=evaluate(zero)+rng.normal(0,2,2*len(ci));path=root/'tiny.txt'
with path.open('w') as f:
 f.write(f'{nc} {np_} {len(ci)}\n')
 for i,(c,p) in enumerate(zip(ci,pi)):f.write(f'{c} {p} {obs[2*i]:.17g} {obs[2*i+1]:.17g}\n')
 for c in range(nc):
  for v in [*w[c],*t[c],*intr[c]]:f.write(f'{v:.17g}\n')
 for v in X.flat:f.write(f'{v:.17g}\n')
J=np.zeros((len(obs),n));eps=1e-6
for j in range(n):
 if j<9*nc and j%9==8:continue
 d=zero.copy();d[j]=eps;J[:,j]=(evaluate(d)-evaluate(-d))/(2*eps)
r=evaluate(zero)-obs;H=J.T@J;D=np.diag(H).copy();D[:9*nc]=np.where(D[:9*nc]>0,D[:9*nc],1)
for p in range(np_):
 a=9*nc+3*p;D[a:a+3]=np.maximum(D[a:a+3],1e-3*np.sum(D[a:a+3])/3)
delta=np.linalg.solve(H+10*np.diag(D),-J.T@r);expected=evaluate(delta)
env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};env.update(flags('lm'));env.pop('OCA_FTOL',None);env.pop('OCA_FTOL_K',None)
state=root/'endpoint.state';cmd=['flock','/tmp/prism_gpu.lock',str(BIN),'--problem',str(path),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--mf-no-alpha','--ew-eta-max','1e-12','--max_iter','1','--state_out',str(state)]
with (root/'run.log').open('w') as f,(root/'run.stderr').open('w') as e:subprocess.run(cmd,env=env,stdout=f,stderr=e,check=True)
with state.open('rb') as f:
 assert f.read(8)==b'PRISMS01';dims=np.fromfile(f,dtype='<u8',count=3);rr=np.fromfile(f,dtype='<f8',count=9*nc).reshape(nc,3,3);tt=np.fromfile(f,dtype='<f8',count=3*nc).reshape(nc,3);xx=np.fromfile(f,dtype='<f8',count=3*np_).reshape(np_,3);ii=np.fromfile(f,dtype='<f8',count=3*nc).reshape(3,nc).T
q=np.einsum('nij,nj->ni',rr[ci],xx[pi])+tt[ci];uv=-q[:,:2]/q[:,2,None];actual=(uv*(ii[ci,0]*(1+ii[ci,1]*np.sum(uv*uv,axis=1)))[:,None]).reshape(-1)
error=np.linalg.norm(actual-expected)/max(1,np.linalg.norm(expected));point_error=np.max(np.abs(xx-(X+delta[9*nc:].reshape(np_,3))));trans_error=np.max(np.abs(tt-(t+delta[:9*nc].reshape(nc,9)[:,3:6])));assert error<1e-7 and point_error<1e-6 and trans_error<1e-6
result=dict(pixel_prediction_relative_error=error,point_max_error=point_error,translation_max_error=trans_error,input_sha256=sha(path),binary_sha256=sha(BIN),command=cmd,flags={k:v for k,v in env.items() if k.startswith('OCA_')},expected_cost=float(.5*np.sum((expected-obs)**2)),actual_cost=audit(state,*observations(path)));(root/'result.json').write_text(json.dumps(result,indent=2));print(result)
