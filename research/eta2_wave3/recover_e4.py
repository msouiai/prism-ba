"""Finish the preserved E4 analysis/archive after the volume-quota interruption."""
from pathlib import Path
import json,shutil
import numpy as np
import miss_forensics as M
P=M.P;F=M.F;FA=M.FA
out=P/'miss-forensics';comp=json.loads((out/'comparison.json').read_text());root=Path(json.loads((out/'staging.json').read_text())['root'])
assert root.exists();div=comp['first_material_divergence'];files={};labels=[]
selected={key:dict(rep=comp[key+'_rep'],paths=M.accepts(root/str(comp[key+'_rep']))) for key in ['hit','miss']}
# Exploratory follow-up: where is the full cost gap on the preceding step?
if div is not None and div>0:
 ci,pi,uv,dims=F.CHART.load_observations('/workspace/bal/final-3068.txt');costs={};before={}
 for key,case in selected.items():
  cam,X,meta,E,dc,dp=M.details(case['paths'][div-1]);costs[key]=F.S.block_cost(cam.retract(dc),X+dp,ci,pi,uv);before[key]=F.S.block_cost(cam,X,ci,pi,uv)
 delta=costs['miss']-costs['hit'];pre=before['miss']-before['hit'];absorder=np.argsort(abs(delta))[::-1];nobs=np.bincount(pi,minlength=dims[1]);absolute=float(np.sum(abs(delta)))
 F.write(out/'preceding_point_gap.json',dict(scope='Exploratory attribution of joint post-step residual-cost gap by point; not proof that point updates alone caused it',accepted_index=div-1,
   signed_gap=float(delta.sum()),initial_signed_gap=float(pre.sum()),absolute_gap=absolute,top200_absolute_fraction=float(np.sum(abs(delta[absorder[:200]]))/absolute),
   top20=[dict(point=int(j),observations=int(nobs[j]),signed_gap=float(delta[j]),initial_gap=float(pre[j]),cameras=np.unique(ci[pi==j]).tolist()) for j in absorder[:20]]))
for key,case in selected.items():
 keep={len(case['paths'])-1}
 if div is not None:keep.update([max(0,div-1),div])
 for j in sorted(keep):
  p=case['paths'][j]
  for f in p.iterdir():
   if f.is_file():files[key+'/'+p.name+'/'+f.name]=f
  if div is not None and j in {max(0,div-1),div}:labels.append(f'final-3068-{key}-accept{j}')
 for f in (root/str(case['rep'])).rglob('*.txt'):files[key+'/'+str(f.relative_to(root/str(case['rep'])))]=f
archive=Path('/workspace/eta2-wave3-evidence/e4-selected-snapshots.xor.tar.xz');assert not archive.exists()
hashes=FA.pack(archive,files);FA.verify(archive,hashes)
F.write(out/'decision.json',dict(complete=True,runs=len(json.loads((out/'runs.json').read_text())),hit_rep=comp['hit_rep'],miss_rep=comp['miss_rep'],divergence=div,
 selected_audits=labels,archive=str(archive),sha256=F.sha(archive),retained_member_sha256=hashes,
 omitted_point_states='Other newly captured intermediate arrays omitted under E4_PROTOCOL.md; hashes cannot reconstruct them',
 causal_scope='Observed fresh pair, not controlled miss-seed replay or hit-rate estimate',storage_recovery='No native reruns; reduced to the registered three selected full states per arm after failed partial archive removed'))
shutil.rmtree(root);print('E4 VERIFIED ARCHIVE',archive.stat().st_size,'divergence',div,flush=True)
