#!/usr/bin/env python3
"""Descriptive replay of registered cells; distinguish inward and outward moves.

No new chart, camera direction, anchor, damping choice, or acceptance policy.
"""
from pathlib import Path
import sys,json,time
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'charts'));sys.path.insert(0,str(ROOT/'analysis'))
import reference
from audit_capture import load_capture_state,map_f64,sanitize


def main():
    start=time.perf_counter();out=[]
    for scene in ('venice-52','ladybug-1197'):
        for rep in (0,1,2):
            p=ROOT/'evidence/collect'/f'{scene}-capture-{rep}'
            c,X,m=load_capture_state(p);ci,pi,uv,dims=reference.load_observations(Path('/workspace/bal')/f'{scene}.txt')
            dc=map_f64(p/'eta2-0.step',(9*dims[0]+3*dims[1],))[:9*dims[0]].reshape(dims[0],9)
            center=np.mean(c.centers(),axis=0);radius=float(np.max(np.linalg.norm(c.centers()-center,axis=1)))
            proposed=c.retract(dc)
            olddepth=(np.einsum('nij,nj->ni',c.R[ci],X[pi])+c.t[ci])[:,2]
            euclidean_cost=None
            for chart in ('euclidean','homogeneous','inverse_depth'):
                ans=reference.conditional_point_solve(c,X,ci,pi,uv,dc,m['lambda'],chart=chart)
                H=ans['H_candidate'];new=reference.euclidean_from_homogeneous(H)
                d=np.linalg.norm(new-X,axis=1);oldr=np.linalg.norm(X-center,axis=1);newr=np.linalg.norm(new-center,axis=1);large=d>radius
                Y=np.einsum('nij,nj->ni',proposed.R[ci],H[pi,:3])+proposed.t[ci]*H[pi,3,None]
                depthsign=np.sign(Y[:,2])*np.sign(H[pi,3])
                residual=reference.project_jacobian(Y,proposed.intrinsics[ci])[0]-uv
                cost=np.bincount(pi,weights=.5*np.einsum('ni,ni->n',residual,residual),minlength=len(X))
                if chart=='euclidean':euclidean_cost=cost.copy()
                gain=euclidean_cost-cost;inward=large&(newr<oldr);outward=large&~inward
                ids=np.argsort(-d)[:10]
                out.append(dict(scene=scene,capture_rep=rep,chart=chart,large_displacement_count=int(large.sum()),large_moves_inward=int(inward.sum()),
                                large_moves_outward=int(outward.sum()),front_to_behind_observations=int(np.count_nonzero((olddepth<0)&(depthsign>0))),
                                behind_to_front_observations=int(np.count_nonzero((olddepth>0)&(depthsign<0))),maximum_old_distance=float(oldr.max()),
                                maximum_new_distance=float(newr.max()),gain_vs_euclidean=float(np.sum(gain,dtype=np.longdouble)),
                                gain_on_large_inward_tracks=float(np.sum(gain[inward],dtype=np.longdouble)),gain_on_large_outward_tracks=float(np.sum(gain[outward],dtype=np.longdouble)),
                                gain_on_other_tracks=float(np.sum(gain[~large],dtype=np.longdouble)),
                                largest_moves=[dict(point=int(j),displacement=float(d[j]),old_distance=float(oldr[j]),new_distance=float(newr[j])) for j in ids]))
                del ans
    report=dict(scope='Descriptive replay of unchanged registered primary-camera cells to interpret displacement, flip directions and objective contributions; no altered configuration and no performance claim',
                rows=out,cpu_seconds=time.perf_counter()-start)
    path=Path(__file__).with_name('displacement_forensics_v2.json');path.write_text(json.dumps(sanitize(report),indent=2,allow_nan=False)+'\n')
    for r in out:print(r['scene'],r['capture_rep'],r['chart'],'inward/outward',r['large_moves_inward'],r['large_moves_outward'],'front->back/back->front',r['front_to_behind_observations'],r['behind_to_front_observations'],'gain',r['gain_vs_euclidean'],'large-inward gain',r['gain_on_large_inward_tracks'],flush=True)


if __name__=='__main__':main()
