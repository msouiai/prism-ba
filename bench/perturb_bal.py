#!/usr/bin/env python3
"""Declared initialization perturbations; observations copied verbatim."""
import argparse,json,pathlib,numpy as np
from profile_iterations import sha
p=argparse.ArgumentParser();p.add_argument('--data',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);p.add_argument('--scenes',nargs='+',required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
for scene in a.scenes:
 src=a.data/(scene+'.txt')
 with src.open() as f:
  header=f.readline();nc,np_,no=map(int,header.split());observations=[f.readline() for _ in range(no)];values=np.loadtxt(f)
 cameras=values[:9*nc].reshape(nc,9);points=values[9*nc:].reshape(np_,3);radius=float(np.median(np.linalg.norm(points-np.median(points,axis=0),axis=1)))
 assert radius>0
 for seed in [17,29,43]:
  dest=a.out/f'{scene}-seed{seed}.txt'
  if dest.exists():raise RuntimeError(f'Refusing to replace {dest}')
  rng=np.random.default_rng(seed);c=cameras.copy();x=points.copy();c[:,:3]+=rng.normal(0,.001,(nc,3));c[:,3:6]+=rng.normal(0,.001*radius,(nc,3));x+=rng.normal(0,.001*radius,x.shape)
  with dest.open('w') as f:
   f.write(header);f.writelines(observations);np.savetxt(f,np.r_[c.ravel(),x.ravel()],fmt='%.17g')
  dest.with_suffix('.json').write_text(json.dumps(dict(source_sha256=sha(src),data_sha256=sha(dest),seed=seed,point_radius=radius,rotation='additive angle-axis coordinate perturbation std 0.001 rad',translation_point_std=.001*radius,observations='verbatim original',intrinsics='unchanged'),indent=2)+'\n')
  print(dest,flush=True)
