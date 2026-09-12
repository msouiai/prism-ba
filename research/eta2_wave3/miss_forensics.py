"""E4 fresh accepted-step comparison with explicit bounded snapshot retention."""
from pathlib import Path
import json,os,shutil,sys,tempfile
import numpy as np
import run_native as N
import forensics as F
sys.path.insert(0,str(N.W));import lossless_float_archive as FA
P=N.P
def accepts(root):
 return sorted((p for p in root.iterdir() if (p/'accepted.step').exists()),key=lambda p:int(p.name))
def details(p):
 cam,X,m=F.load_capture_state(p);n=len(cam.R);E=F.read_array(p/'E.f64',(n,9));d=F.read_array(p/'accepted.step',(9*n+3*len(X),))
 return cam,X,m,E,d[:9*n].reshape(n,9),d[9*n:].reshape(-1,3)
def conditional(p,scene):
 cam,X,m,E,dc,dp=details(p);ci,pi,uv,_=F.CHART.load_observations('/workspace/bal/'+scene+'.txt');nc=len(cam.R)
 ch=F.CHART.make_chart(X,cam,'euclidean');r,jc,jp,_=F.CHART.observation_jacobians(cam,ch.H,ch.T,ci,pi,uv)
 yc=np.einsum('nri,ni->nr',jc,dc[ci]);yp=np.einsum('nri,ni->nr',jp,dp[pi]);new=cam.retract(dc)
 rc,_=F.S.residual(new,X[pi],ci,uv);rj,_=F.S.residual(new,X[pi]+dp[pi],ci,uv)
 def sums(x):return np.bincount(ci,weights=np.sum(x,axis=1),minlength=nc)
 camgain=-.5*sums((rc-r)*(rc+r));jointgain=-.5*sums((rj-r)*(rj+r));campred=-sums(r*yc+.5*yc*yc);jointpred=-sums(r*(yc+yp)+.5*(yc+yp)**2)
 norms=np.linalg.norm(dc/E,axis=1);ids=np.argsort(norms)[-5:][::-1]
 def ratio(a,b):return float(a/b) if abs(b)>1e-30 else None
 rows=[dict(camera=int(c),observations=int(np.count_nonzero(ci==c)),actual_scaled_step_norm=float(norms[c]),
    camera_only_gain=float(camgain[c]),camera_only_prediction=float(campred[c]),camera_only_rho=ratio(camgain[c],campred[c]),
    joint_gain_on_camera_observations=float(jointgain[c]),joint_prediction_on_camera_observations=float(jointpred[c]),joint_rho_on_camera_observations=ratio(jointgain[c],jointpred[c])) for c in range(nc)]
 return dict(scope='Camera-only holds old points fixed; joint terms include both actual camera and point moves and sum to full model/cost decrease',
   score_init=m['cost'],full_joint_gain=float(jointgain.sum()),full_joint_prediction=float(jointpred.sum()),full_joint_rho=ratio(jointgain.sum(),jointpred.sum()),
   top5_actual_camera_ids=ids.tolist(),top5=[rows[c] for c in ids],per_camera=rows)

def main():
 reg=N.register();bm=json.loads((P/'e4_build_manifest.json').read_text());assert F.sha(P/'build/prism-e4')==bm['binary_sha256']
 reg=dict(reg,native_binary=str(P/'build/prism-e4'),build_manifest=bm)
 out=P/'miss-forensics';out.mkdir(exist_ok=True);holder=Path(tempfile.mkdtemp(prefix='e4-pair-',dir='/dev/shm'))
 F.write(out/'staging.json',dict(root=str(holder),policy='E4_PROTOCOL.md'))
 selected={};runs=[];hashes=[]
 for rep in range(10):
  root=holder/str(rep);root.mkdir();row=N.run(reg,'e4-diagnostic',reg['cells']['final-3068'],'off',rep,dict(OCA_E4_CAPTURE=str(root)))
  paths=accepts(root);key='hit' if row['hit'] else 'miss'
  inventory={str(p.relative_to(root)):F.sha(p) for p in root.rglob('*') if p.is_file()};hashes.append(dict(rep=rep,hit=row['hit'],all_member_sha256=inventory,accepted_snapshots=len(paths)))
  runs.append(row);F.write(out/'runs.json',runs);F.write(out/'source-hashes.json',hashes)
  if key not in selected:selected[key]=dict(rep=rep,root=root,paths=paths,row=row)
  else:shutil.rmtree(root) # newly captured diagnostics covered by registered retention
  if rep>=4 and len(selected)==2:break
 if len(selected)<2:
  F.write(out/'decision.json',dict(reason='No hit/miss pair within registered budget',runs=len(runs),classes=list(selected),complete=False,scratch_retained=str(holder)));return
 hit,miss=selected['hit'],selected['miss'];comparisons=[];divergence=None
 for j,(hp,mp) in enumerate(zip(hit['paths'],miss['paths'])):
  hc,hx,hm,he,hd,hpstep=details(hp);mc,mx,mm,me,md,mpstep=details(mp)
  a=hd/he;b=md/he;relative=float(np.linalg.norm(b-a)/max(np.linalg.norm(a),np.linalg.norm(b),1e-300))
  row=dict(accepted_index=j,hit_attempt=int(hp.name),miss_attempt=int(mp.name),relative_direction_difference_common_hit_metric=relative,
    hit_cost=hm['cost'],miss_cost=mm['cost'],relative_cost_difference=abs(hm['cost']-mm['cost'])/max(1,hm['cost']))
  comparisons.append(row)
  if relative>.1 and divergence is None:divergence=j
 F.write(out/'comparison.json',dict(hit_rep=hit['rep'],miss_rep=miss['rep'],first_material_divergence=divergence,rows=comparisons))
 files={};selected_labels=[]
 for key,case in selected.items():
  keep={0,len(case['paths'])-1}
  if divergence is not None:keep.update([max(0,divergence-1),divergence])
  for j in sorted(keep):
   if j>=len(case['paths']):continue
   p=case['paths'][j];label=f'final-3068-{key}-accept{j}'
   for f in p.iterdir():
    if f.is_file():files[key+'/'+p.name+'/'+f.name]=f
   if divergence is not None and j in {max(0,divergence-1),divergence}:
    ans=F.audit(p,'final-3068',label,cap_screen=False);ans['accepted_step_camera_audit']=conditional(p,'final-3068')
    F.write(out/(label+'.json'),ans);selected_labels.append(label)
  # Every attempt's metadata/accept marker retained even when arrays omitted.
  for f in case['root'].rglob('*.txt'):files[key+'/'+str(f.relative_to(case['root']))]=f
 archive=Path(reg['states'])/'e4-selected-snapshots.xor.tar.xz';rawhash=FA.pack(archive,files);FA.verify(archive,rawhash)
 F.write(out/'decision.json',dict(complete=True,runs=len(runs),hit_rep=hit['rep'],miss_rep=miss['rep'],divergence=divergence,
   selected_audits=selected_labels,archive=str(archive),sha256=F.sha(archive),retained_member_sha256=rawhash,
   omitted_point_states='Other newly captured intermediate arrays omitted under E4_PROTOCOL.md; hashes cannot reconstruct them',
   causal_scope='Observed fresh pair, not a controlled miss-seed replay or hit-rate estimate'))
 shutil.rmtree(holder);print('E4 DONE',divergence,hit['rep'],miss['rep'],flush=True)
if __name__=='__main__':main()
