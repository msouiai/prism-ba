#!/usr/bin/env python3
"""Registered Final3068 graph-space coverage only; no optimizer or GPU."""
import csv
import json
import resource
import time
from pathlib import Path
import numpy as np
import core

P=Path(__file__).resolve().parent
C=core.CAMPAIGN
K_VALUES=(8,32,128)
CAPTURES=('final-3068-capture-0','final-3068-capture-5','final-3068-capture-6')


def write(path,value):
    if path.exists():raise FileExistsError(path)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def camera_prefix(path,ncam,npoint):
    assert path.stat().st_size==8*(9*ncam+3*npoint)
    value=np.fromfile(path,dtype='<f8',count=9*ncam).reshape(ncam,9)
    assert np.isfinite(value).all() and np.all(value[:,8]==0)
    return value


def old_labels(cell,ncam):
    labels=np.full(ncam,-1,dtype=np.int64)
    for index,block in enumerate(cell['basis']['clusters']):
        ids=np.asarray(block['camera_ids'],dtype=np.int64)
        assert np.all(labels[ids]==-1)
        labels[ids]=index
    assert np.all(labels>=0)
    return labels


def compact_basis(info,gauge):
    return dict(rank=info['rank'],rank_by_cluster=[b['rank'] for b in info['clusters']],
                max_fd_analytic_error=info['max_fd_analytic_error'],
                global_containment_error=gauge['containment'],
                global_constraint_rank=gauge['rank'],global_constraint_singular_values=gauge['singular'].tolist(),
                fd_step=core.geometry.FD_STEP,local_rank_rtol=core.geometry.RANK_RTOL,
                gauge_rank_rtol=core.GAUGE_RANK_RTOL)


def diagnose(name,ci,pi,dims,partition_rows,topology):
    start=time.perf_counter()
    baseline=core.geometry.verify_baseline()
    capture=C/'evidence/collect'/name
    oldpath=P.parent/'audits'/(name+'.json')
    old=json.loads(oldpath.read_text())
    # Preserve and verify the exact states behind the earlier comparison.
    input_hashes={key:core.geometry.sha256(capture/key) for key in old['input_sha256']}
    assert input_hashes==old['input_sha256'],'Original capture differs from preserved geometric audit'
    meta=core.geometry.read_metadata(capture/'metadata.txt')
    ncam,npoint,nobs=dims
    assert (int(meta['ncam']),int(meta['npt']),int(meta['nobs']))==dims
    R=core.geometry.read_array(capture/'R_state.f64',(ncam,3,3))
    t=core.geometry.read_array(capture/'t_state.f64',(ncam,3))
    E=core.geometry.read_array(capture/'E.f64',(ncam,9))
    intr=core.geometry.read_array(capture/'intr_state.f64',(3,ncam))
    assert np.all(E>0) and np.all(intr[2]==0)
    assert np.max(np.abs(R@R.transpose(0,2,1)-np.eye(3)))<1e-7
    eta=camera_prefix(capture/'eta2-0.step',ncam,npoint)
    raw=core.geometry.read_array(capture/'eta2_raw_scaled.f64',(ncam,9))
    records={}
    with (capture/'native_directions.csv').open() as stream:
        for row in csv.DictReader(stream):records[(row['arm'],int(row['rep']))]=row
    references=[]
    for rep in range(3):
        exact=camera_prefix(capture/f'exact-{rep}.step',ncam,npoint)
        clip=camera_prefix(capture/f'exact_clip-{rep}.step',ncam,npoint)
        scale=max(np.linalg.norm(exact/E),np.linalg.norm(clip/E),np.linalg.norm(eta/E),np.linalg.norm(raw))
        references.append(dict(rep=rep,scale=float(scale),record=records.get(('exact',rep)),
            deltas=dict(exact_minus_eta2=exact/E-eta/E,exact_clip_minus_eta2=clip/E-eta/E,
                        exact_minus_eta2_raw=exact/E+raw)))
    global_blocks,global_info=core.geometry.build_blocks(R,t,E,np.zeros(ncam,dtype=np.int64))
    cells=[]
    for k in K_VALUES:
        cell_start=time.perf_counter()
        labels,partition=partition_rows[k]
        oldcell=next(cell for cell in old['cells'] if cell['clustering']['requested_k']==k)
        geometric=old_labels(oldcell,ncam)
        rows={}
        for arm,membership in (('graph',labels),('geometric',geometric)):
            blocks,info=core.geometry.build_blocks(R,t,E,membership)
            gauge=core.gauge_operator(blocks,global_blocks)
            repeats=[]
            for ref in references:
                differences={kind:core.report_projection(delta,blocks,global_blocks,ref['scale'],gauge)
                             for kind,delta in ref['deltas'].items()}
                if arm=='geometric':
                    previous=next(r for r in oldcell['references'] if r['repeat']==ref['rep'])
                    for kind,metrics in differences.items():
                        for key in ('norm','projected_norm','fraction','after_global_removal_fraction'):
                            a,b=metrics['legacy'][key],previous['differences'][kind][key]
                            assert (a is None and b is None) or abs(a-b)<=1e-11*max(1,abs(b)),(name,k,kind,key,a,b)
                repeats.append(dict(reference_rep=ref['rep'],native_reduced_reference_record=ref['record'],differences=differences))
            counts=core.observation_counts(ci,pi,npoint,membership)
            rows[arm]=dict(basis=compact_basis(info,gauge),cluster_sizes=np.bincount(membership).tolist(),
                           labels_sha256=core.array_sha(membership.astype('<i8')),counts=counts,
                           rank_fraction_extrinsic=info['rank']/(6*ncam),references=repeats)
        cell=dict(requested_k=k,partition=partition,arms=rows,cell_cpu_seconds=time.perf_counter()-cell_start)
        cells.append(cell)
        raw_graph=[r['differences']['exact_minus_eta2_raw']['explicit_gauge_free']['fraction']
                   for r in rows['graph']['references']]
        raw_geo=[r['differences']['exact_minus_eta2_raw']['explicit_gauge_free']['fraction']
                 for r in rows['geometric']['references']]
        print('CELL',name,'K',k,'sizes',min(rows['graph']['cluster_sizes']),max(rows['graph']['cluster_sizes']),
              'graph_free',raw_graph,'geometric_free',raw_geo,flush=True)
    result=dict(capture=name,metadata=meta,baseline=baseline,input_sha256=input_hashes,
                prior_geometric_sha256=core.geometry.sha256(oldpath),
                global_basis_rank=global_info['rank'],graph_topology=topology,
                full_camera_metric='Euclidean norm in z=E^-1 dc; includes extrinsic and intrinsic rows',
                cells=cells,cpu_seconds_including_hashes=time.perf_counter()-start,
                peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                caveats=['Camera projection only, no step or scored objective altered',
                         'Reference reduced certification does not certify the full saved point step',
                         'Three arithmetic/reference repetitions are not independent nonlinear hit-rate runs',
                         'Near-zero threshold retained; extra numerical-sensitivity disclosure uses1e-7*max(reference_norm,1)',
                         'Global geometric similarity is not an exact damped-Schur null space',
                         'If disconnected, global-only removal does not remove all independent component similarities'])
    write(P/'results'/(name+'.json'),result)
    return result


def main():
    started=time.perf_counter()
    (P/'results').mkdir(exist_ok=True)
    expected=json.loads((P/'dependencies/api_verification.json').read_text())
    for name,digest in expected['installed_files_sha256'].items():
        assert core.geometry.sha256(Path(core.DEPENDENCY['install_path'])/name)==digest
    assert json.loads((P/'verification.json').read_text())['passed']
    baseline=core.geometry.verify_baseline()
    problem=Path('/workspace/bal/final-3068.txt')
    with problem.open() as stream:
        dims=tuple(map(int,stream.readline().split()))
        obs=np.loadtxt(stream,dtype=np.int64,usecols=(0,1),max_rows=dims[2])
    assert obs.shape==(dims[2],2)
    ci,pi=obs[:,0],obs[:,1]
    graph,topology=core.build_graph(dims[0],dims[1],ci,pi)
    print('GRAPH',json.dumps(topology),flush=True)
    partitions={k:core.partition(graph,k) for k in K_VALUES}
    graph_record=dict(input=str(problem),input_sha256=core.geometry.sha256(problem),topology=topology,
                      partitions=[dict(labels=labels.tolist(),**info) for labels,info in partitions.values()])
    write(P/'results/graph.json',graph_record)
    manifest=dict(baseline=baseline,protocol_sha256=core.geometry.sha256(C/'PROTOCOL_01_GRAPH.md'),
                  input_sha256=graph_record['input_sha256'],dependency=core.DEPENDENCY,
                  sources_sha256={str(path.relative_to(C)):core.geometry.sha256(path) for path in
                     (P/'core.py',P/'run.py',P.parent/'diagnostic.py')},
                  K=list(K_VALUES),captures=list(CAPTURES),N=3,replicate_scope='Saved arithmetic/reference repeats',
                  partition_settings=core.SETTINGS,one_cpu_thread=True,no_gpu=True)
    write(P/'results/manifest.json',manifest)
    del graph
    results=[diagnose(name,ci,pi,dims,partitions,topology) for name in CAPTURES]
    summary=[]
    for result in results:
        for cell in result['cells']:
            for kind in ('exact_minus_eta2_raw','exact_clip_minus_eta2','exact_minus_eta2'):
                row=dict(capture=result['capture'],K=cell['requested_k'],difference=kind)
                for arm in ('graph','geometric'):
                    metrics=[rep['differences'][kind] for rep in cell['arms'][arm]['references']]
                    row[arm]=dict(norms=[m['legacy']['norm'] for m in metrics],
                         total_fractions=[m['legacy']['fraction'] for m in metrics],
                         legacy_after_global=[m['legacy']['after_global_removal_fraction'] for m in metrics],
                         gauge_free_fractions=[m['explicit_gauge_free']['fraction'] for m in metrics],
                         gauge_free_extrinsic_fractions=[m['explicit_gauge_free']['extrinsic_only_fraction'] for m in metrics],
                         sensitive=[m['numerically_sensitive_difference'] for m in metrics],
                         rank=cell['arms'][arm]['basis']['rank'],cluster_sizes=cell['arms'][arm]['cluster_sizes'],
                         cross_observations=cell['arms'][arm]['counts']['first_observation_anchor_cross_observations'])
                summary.append(row)
    report=dict(rows=summary,cpu_seconds=time.perf_counter()-started,
                peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                all_geometric_legacy_checks_passed=True,no_optimizer_run=True)
    write(P/'results/summary.json',report)
    print('DONE CPU_SECONDS',report['cpu_seconds'],'PEAK_RSS_KIB',report['peak_rss_kib'],flush=True)


if __name__=='__main__':main()
