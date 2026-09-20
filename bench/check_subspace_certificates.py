#!/usr/bin/env python3
"""Check why the projected optimum stays full/uniform on saved BA models."""
import pathlib,re,json,math
root=pathlib.Path('/workspace/prism-subspace-rescue');out={}
for stage in ['diagnostic','calibrated']:
 for p in (root/stage).glob('*.log'):
  n=corner=uniform=nonuniform=0
  for line in p.read_text().splitlines():
   if not line.startswith('SUBSPACE o='):continue
   x={k:float(v) for k,v in re.findall(r'(\w+)=(\S+)',line)}
   if stage=='calibrated' and x['mode']!=5:continue
   n+=1;gc,gp,A,B,C=[x[k] for k in ['gc','gp','cc','cp','pp']];scale=max(1,abs(gc),abs(gp),A,abs(B),C)
   if gc+A+B<=1e-10*scale and gp+B+C<=1e-10*scale:corner+=1
   if stage=='calibrated' and math.isfinite(x['error']):
    E=x['error'];den=A+2*B+C+2*E;t=min(1,max(0,-(gc+gp)/den)) if den>0 else 0
    u=gc+t*(A+B);v=gp+t*(B+C)
    # Interior uniform optimum: allocate infinity-norm subgradient between the blocks.
    certified=(0<t<1 and E>0 and u<=1e-10*scale and v<=1e-10*scale and abs(u+v+2*E*t)<=1e-9*max(scale,E))
    if certified:
     uniform+=1
     assert abs(x['a']-t)+abs(x['b']-t)<1e-6
    if abs(x['a']-x['b'])>1e-8:nonuniform+=1
  if n:out[stage+'/'+p.stem]=dict(models=n,full_corner_kkt=corner,uniform_calibrated_kkt=uniform,nonuniform=nonuniform)
(root/'certificates.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
