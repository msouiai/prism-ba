"""Independent projected normal-equation check on native gated opening states."""
import json,re,tempfile
from pathlib import Path
import numpy as np
import run_native as N
import forensics as F
P=N.P;reg=N.register();rows=[]
with tempfile.TemporaryDirectory(prefix='e3-audit-',dir='/dev/shm') as tmp:
 tmp=Path(tmp);run=N.run(reg,'gate-audit',reg['cells']['venice-52'],'intrinsic',0,dict(OCA_E1_CAPTURE=str(tmp)))
 folder=P/run['source'];waves=json.loads((folder/'wave.json').read_text());events={}
 for line in (folder/'stdout.log').read_text().splitlines():
  if line.startswith('E3_GATE '):
   v=dict(re.findall(r'(\w+)=(\S+)',line));events[(int(v['o']),int(v['retry']))]=[int(i) for i in v.get('ids','').split(',') if i]
 ci,pi,uv,_=F.CHART.load_observations('/workspace/bal/venice-52.txt')
 for path in sorted(tmp.iterdir(),key=lambda p:int(p.name)):
  cam,X,meta=F.load_capture_state(path);nc,np_=len(cam.R),len(X);wave=waves[int(path.name)]
  E=F.read_array(path/'E.f64',(nc,9));raw=-F.read_array(path/'eta2_raw_scaled.f64',(nc,9));cd=F.read_array(path/'Cdiag.f64',(np_,3));ids=events[(wave['outer'],wave['retry'])]
  assert np.all(raw[ids,6:8]==0) and np.all(raw[:,8]==0)
  chart=F.CHART.make_chart(X,cam,'euclidean');r,jc,jp,Y=F.CHART.observation_jacobians(cam,chart.H,chart.T,ci,pi,uv)
  diag=np.maximum(cd,.001*np.maximum(cd.mean(axis=1),1e-32)[:,None]);_,Ri,_=F.point_qr(jp,pi,meta['tau']*diag)
  gp=F.aggregate(np.einsum('nri,nr->ni',jp,r),pi,np_)
  up=F.point_inverse(Ri,gp);b=-E*F.aggregate(np.einsum('nri,nr->ni',jc,r-np.einsum('nri,ni->nr',jp,up[pi])),ci,nc)
  yc=np.einsum('nri,ni->nr',jc,(E*raw)[ci]);v=F.point_inverse(Ri,F.aggregate(np.einsum('nri,nr->ni',jp,yc),pi,np_))
  product=E*F.aggregate(np.einsum('nri,nr->ni',jc,yc-np.einsum('nri,ni->nr',jp,v[pi])),ci,nc)
  count=np.bincount(ci,minlength=nc);r2=np.sum((Y[:,:2]/Y[:,2,None])**2,axis=1);avg=np.maximum(np.bincount(ci,weights=r2,minlength=nc)/np.maximum(count,1),1e-12)
  prior=np.zeros((nc,9));prior[:,6]=np.where(count>0,1/(.5*np.abs(cam.intrinsics[:,0])+1e-3)**2,0);prior[:,7]=np.where(count>0,avg**2,0)
  product+=prior*E*E*raw+meta['lambda']*raw;b[ids,6:8]=0;product[ids,6:8]=0
  relative=float(np.linalg.norm(product-b)/np.linalg.norm(b));certified=relative<=1.02*meta['eta']+1e-6
  rows.append(dict(attempt=int(path.name),gated_cameras=ids,relative_projected_normal_residual=relative,eta=meta['eta'],certified=certified,masked_coordinates_exactly_zero=True,
    source_sha256={p.name:F.sha(p) for p in path.iterdir() if p.is_file()}))
 # Keep the independently audited snapshots, small first-three-accept cohort.
 archive=P/'durable_states/gate-audit-snapshots.xor.tar.xz';archive.parent.mkdir(exist_ok=True)
 hashes=F.FA.pack(archive,{str(p.relative_to(tmp)):p for p in tmp.rglob('*') if p.is_file()});F.FA.verify(archive,hashes)
 F.write(P/'intrinsic_operator_audit.json',dict(rows=rows,passed=all(r['certified'] for r in rows),archive=str(archive),sha256=F.sha(archive),
   retained_member_sha256=hashes,scope='Independent coherent CPU projected normal equations at native states, including intrinsic prior; tolerance reflects the intentionally inexact native solve'))
 assert all(r['certified'] for r in rows),rows
 print('PROJECTED OPERATOR AUDIT',[(r['relative_projected_normal_residual'],r['eta']) for r in rows],flush=True)
