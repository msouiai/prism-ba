"""Exploratory E4 two-state swap diagnostic on the identified gap point only."""
from pathlib import Path
import json,tempfile
import numpy as np
import miss_forensics as M
F=M.F;P=M.P
record=json.loads((P/'miss-forensics/decision.json').read_text());wanted={'hit/6','miss/6'}
with tempfile.TemporaryDirectory(prefix='e4-point-gap-',dir='/dev/shm') as tmp:
 tmp=Path(tmp)
 for name,raw in M.FA.decoded(record['archive']):
  if str(Path(name).parent) in wanted:
   p=tmp/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
 ci,pi,uv,_=F.CHART.load_observations('/workspace/bal/final-3068.txt');point=250233;obs=np.flatnonzero(pi==point);camids=ci[obs]
 states={};description={}
 for key in ['hit','miss']:
  cam,X,meta,E,dc,dp=M.details(tmp/key/'6');new=cam.retract(dc);states[key]=(new,X[point]+dp[point])
  oldY=np.einsum('nij,j->ni',cam.R[camids],X[point])+cam.t[camids]
  newY=np.einsum('nij,j->ni',new.R[camids],X[point]+dp[point])+new.t[camids]
  centers=cam.centers();radius=np.linalg.norm(centers-centers.mean(axis=0),axis=1).max()
  description[key]=dict(point_before=X[point].tolist(),point_step=dp[point].tolist(),point_displacement=float(np.linalg.norm(dp[point])),scene_radius=float(radius),
   point_kept=bool(np.all(dp[point]==0)),camera_physical_steps=dc[camids].tolist(),old_depth=oldY[:,2].tolist(),new_depth=newY[:,2].tolist(),depth_ratio=(newY[:,2]/oldY[:,2]).tolist())
 scores=[]
 for cams in ['hit','miss']:
  for pts in ['hit','miss']:
   c=states[cams][0];x=np.repeat(states[pts][1][None,:],len(obs),axis=0);r,_=F.S.residual(c,x,camids,uv[obs]);scores.append(dict(camera_state=cams,point_state=pts,track_cost=float(.5*np.sum(r*r))))
 F.write(P/'miss-forensics/point_swap_audit.json',dict(point=point,observing_cameras=camids.tolist(),accepted_index=6,states=description,swaps=scores,
  scope='Exploratory diagnostic on one selected point. Cross-state swaps are not optimizer trajectories or a registered solver intervention; no basin rescue inferred.'))
 print('POINT SWAP',scores,flush=True)
