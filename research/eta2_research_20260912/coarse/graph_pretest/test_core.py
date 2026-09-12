#!/usr/bin/env python3
"""Synthetic graph/count/gauge checks; no BAL witness evaluation."""
import json
from pathlib import Path
import numpy as np
from scipy.linalg import null_space
from scipy.spatial.transform import Rotation
import core


def main():
    ci=[];pi=[]
    for point in range(20):
        cameras=(0,1,2) if point<10 else (3,4,5)
        ci.extend(cameras);pi.extend([point]*3)
    ci.extend((2,3,0));pi.extend((20,20,0)) # bridge plus duplicate incidence
    ci=np.asarray(ci);pi=np.asarray(pi)
    graph,meta=core.build_graph(6,21,ci,pi)
    direct=np.zeros((6,6),dtype=np.int64)
    for point in range(21):
        ids=np.unique(ci[pi==point])
        for a in ids:
            for b in ids:
                if a!=b:direct[a,b]+=1
    assert np.array_equal(graph.toarray(),direct)
    assert meta['collapsed_duplicate_incidences']==1
    parts=[core.partition(graph,2) for _ in range(3)]
    assert all(np.array_equal(parts[0][0],p[0]) for p in parts)
    labels,partition=parts[0]
    assert np.array_equal(labels,[0,0,0,1,1,1])
    assert partition['weighted_edge_cut']==1
    counts=core.observation_counts(ci,pi,21,labels)
    assert counts['first_observation_anchor_cross_observations']==1
    assert counts['observations_on_multicluster_tracks']==2
    disconnected,discmeta=core.build_graph(7,21,ci,pi)
    dl,dm=core.partition(disconnected,2)
    assert len(dl)==7 and discmeta['connected_components']==2 and discmeta['isolated_cameras']==1
    assert disconnected[6].nnz==0
    # Compare the blockwise intersection projector with an independent dense
    # null-space basis. Include arbitrary non-contained G, not just nested spans.
    rng=np.random.default_rng(52)
    R=Rotation.from_rotvec(rng.normal(size=(6,3))*.2).as_matrix()
    t=rng.normal(size=(6,3));E=np.exp(rng.normal(size=(6,9))*.2)
    blocks,info=core.geometry.build_blocks(R,t,E,np.repeat(np.arange(2),3))
    global_blocks,_=core.geometry.build_blocks(R,t,E,np.zeros(6,dtype=int))
    Q=np.column_stack([core.lift(v,blocks,(6,9)).reshape(-1) for v in np.eye(info['rank'])])
    errors=[]
    for G in (global_blocks[0]['Q'],np.linalg.qr(rng.normal(size=(54,5)))[0]):
        custom_global=[dict(ids=np.arange(6),Q=G)]
        gauge=core.gauge_operator(blocks,custom_global)
        N=null_space(G.T@Q,rcond=core.GAUGE_RANK_RTOL)
        dense=(Q@N)@(Q@N).T
        columns=[]
        for v in np.eye(54):
            q=core.coefficients(v.reshape(6,9),blocks)
            q-=gauge['U']@(gauge['U'].T@q)
            columns.append(core.lift(q,blocks,(6,9)).reshape(-1))
        projected=np.column_stack(columns)
        error=dict(dense_difference=float(np.linalg.norm(projected-dense)),
                   symmetry=float(np.linalg.norm(projected-projected.T)),
                   idempotence=float(np.linalg.norm(projected@projected-projected)),
                   gauge_orthogonality=float(np.linalg.norm(G.T@projected)))
        assert max(error.values())<2e-12,error
        errors.append(error)
    report=dict(passed=True,synthetic_only=True,baseline=core.geometry.verify_baseline(),
                graph=meta,partition=partition,counts=counts,disconnected_graph=discmeta,
                disconnected_partition=dm,gauge_projector_checks=errors,
                implementation_sha256=core.geometry.sha256(Path(core.__file__)))
    (Path(__file__).parent/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,graph_counts=counts,gauge_projector_checks=errors),indent=2))


if __name__=='__main__':main()
