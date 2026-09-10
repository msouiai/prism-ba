#!/usr/bin/env python3
"""Independent CPU FP64 objective of exact exported PRISM matrix states."""
import argparse,json,pathlib,struct
import numpy as np

def observations(path):
 with open(path) as f:
  dims=tuple(map(int,f.readline().split()))
  obs=np.loadtxt(f,max_rows=dims[2])
 return dims,obs

def audit(state,dims,obs):
 with open(state,'rb') as f:
  assert f.read(8)==b'PRISMS01','invalid state format'
  assert struct.unpack('<QQQ',f.read(24))==dims,'state/input dimension mismatch'
  nc,np_,no=dims
  R=np.fromfile(f,dtype='<f8',count=9*nc).reshape(nc,3,3)
  t=np.fromfile(f,dtype='<f8',count=3*nc).reshape(nc,3)
  X=np.fromfile(f,dtype='<f8',count=3*np_).reshape(np_,3)
  intr=np.fromfile(f,dtype='<f8',count=3*nc).reshape(3,nc)
  assert not f.read(1),'trailing state bytes'
 assert all(np.isfinite(v).all() for v in [R,t,X,intr]),'nonfinite state'
 assert np.all(intr[2]==0),'unexpected nonzero k2 in SIMPLE_RADIAL study'
 total=np.longdouble(0)
 for start in range(0,no,100000):
  o=obs[start:start+100000];ci=o[:,0].astype(np.int64);pi=o[:,1].astype(np.int64)
  q=np.einsum('nij,nj->ni',R[ci],X[pi])+t[ci]
  uv=-q[:,:2]/q[:,2,None];r2=np.sum(uv*uv,axis=1)
  scale=intr[0,ci]*(1+intr[1,ci]*r2+intr[2,ci]*r2*r2)
  residual=uv*scale[:,None]-o[:,2:4]
  total+=np.sum(residual*residual,dtype=np.longdouble)*.5
 assert np.isfinite(total),'nonfinite CPU objective'
 return float(total)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('bal',type=pathlib.Path);p.add_argument('state',type=pathlib.Path);p.add_argument('--reported',type=float);a=p.parse_args()
 score=audit(a.state,*observations(a.bal));r=dict(cpu_fp64_cost=score)
 if a.reported is not None:r['reported_relative_error']=abs(score-a.reported)/max(1,abs(score))
 print(json.dumps(r,indent=2))
