#!/usr/bin/env python3
"""CPU retract captured repaired steps into shared, audited BAL restart files.

This preserves geometry to the checked roundtrip tolerance, not solver history.
"""
import argparse,json,pathlib,struct
import numpy as np
from audit_prism_state import observations
from profile_iterations import score_initial,sha
from local_curvature_model import FixedDirection

def exp(w):
 theta=np.linalg.norm(w,axis=1);K=np.zeros((len(w),3,3))
 K[:,0,1]=-w[:,2];K[:,0,2]=w[:,1];K[:,1,0]=w[:,2]
 K[:,1,2]=-w[:,0];K[:,2,0]=-w[:,1];K[:,2,1]=w[:,0]
 return np.eye(3)+np.sinc(theta/np.pi)[:,None,None]*K+(.5*np.sinc(theta/(2*np.pi))**2)[:,None,None]*(K@K)

def log_rotation(R):
 # Symmetric quaternion eigensystem avoids the axis singularity at pi.
 out=[]
 for m in R:
  a,b,c=m[0];d,e,f=m[1];g,h,i=m[2]
  K=np.array([[a-e-i,b+d,c+g,h-f],[b+d,e-a-i,f+h,c-g],
              [c+g,f+h,i-a-e,d-b],[h-f,c-g,d-b,a+e+i]])/3
  _,V=np.linalg.eigh(K);q=V[:,-1]
  if q[3]<0:q=-q
  n=np.linalg.norm(q[:3]);out.append(q[:3]*(2*np.arctan2(n,q[3])/n if n else 2))
 return np.array(out)

def main():
 p=argparse.ArgumentParser();p.add_argument('root',type=pathlib.Path);a=p.parse_args();r=a.root;rows=[]
 for scene in ['dubrovnik-173','venice-52']:
  data=pathlib.Path('/workspace/bal')/(scene+'.txt');dims,obs=observations(data)
  for call in [1,4]:
   stem=r/'captures'/f'{scene}-{call}';meta=json.loads(stem.with_suffix('.json').read_text());d=FixedDirection(stem,obs)
   with stem.with_suffix('.state').open('rb') as f:
    assert f.read(8)==b'PRISMS01';nc,np_,no=struct.unpack('<QQQ',f.read(24))
    R=np.fromfile(f,'<f8',9*nc).reshape(nc,3,3);t=np.fromfile(f,'<f8',3*nc).reshape(nc,3)
    X=np.fromfile(f,'<f8',3*np_).reshape(np_,3);intr=np.fromfile(f,'<f8',3*nc).reshape(3,nc).T
   step=np.fromfile(stem.with_suffix('.step'),'<f8');dc=step[:9*nc].reshape(nc,9)
   Rnew=exp(dc[:,:3])@R;aa=log_rotation(Rnew)
   rotation_error=float(np.max(np.abs(exp(aa)-Rnew)));assert rotation_error<1e-12
   cams=np.column_stack((aa,t+dc[:,3:6],intr+dc[:,6:9]*np.array([1,1,0])))
   pts=X+step[9*nc:].reshape(np_,3);out=r/'data'/f'{scene}-post-{call}.txt'
   with out.open('x') as f:
    f.write(f'{nc} {np_} {no}\n');np.savetxt(f,obs,fmt=['%d','%d','%.17g','%.17g'])
    np.savetxt(f,cams.reshape(-1),fmt='%.17g');np.savetxt(f,pts.reshape(-1),fmt='%.17g')
   cpu=d.evaluate(1,1)['cost'];cost=score_initial(out)
   err=abs(cost-cpu)/max(1,cpu);capture_error=abs(cpu-meta['full_cost'])/max(1,cpu)
   assert err<1e-9 and capture_error<1e-9
   rows.append(dict(scene=scene,name=f'{scene}-post-{call}',data=str(out),initial_cost=cost,
                    lambda_=meta['lambda'],tau=meta['tau'],outer=meta['outer'],
                    rotation_error=rotation_error,roundtrip_cost_error=err,capture_cost_error=capture_error,
                    data_sha256=sha(out),capture_sha256=sha(stem.with_suffix('.state'))))
 (r/'restarts.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
