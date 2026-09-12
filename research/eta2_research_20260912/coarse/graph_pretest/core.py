"""Exact graph construction and bounded coefficient-space projection helpers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
import diagnostic as geometry

DEPENDENCY = json.loads((HERE / 'dependencies/manifest.json').read_text())
sys.path.insert(0, DEPENDENCY['install_path'])
import pymetis

SETTINGS = dict(ncuts=1, niter=10, ufactor=30, seed=20260912,
                contig=0, numbering=0, objtype=int(pymetis.ObjType.CUT))
GAUGE_RANK_RTOL = 1e-10
SENSITIVITY_RTOL = 1e-7  # extra disclosure, not a replacement for legacy null threshold


def array_sha(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def build_graph(ncam, npoint, ci, pi):
    ci = np.asarray(ci, dtype=np.int64)
    pi = np.asarray(pi, dtype=np.int64)
    if len(ci) != len(pi) or np.any(ci < 0) or np.any(ci >= ncam) or np.any(pi < 0) or np.any(pi >= npoint):
        raise ValueError('Invalid original observation incidence')
    # Conservative bound for dense CSR result/workspace plus sparse incidence.
    estimate = 48 * ncam * ncam + 64 * len(ci) + 32 * npoint
    if estimate > 1024 ** 3:
        raise MemoryError(f'Conservative exact-graph estimate {estimate} exceeds 1GiB; no sparsification allowed')
    start = time.perf_counter()
    incidence = sparse.csr_matrix((np.ones(len(ci), dtype=np.int64), (ci, pi)), shape=(ncam, npoint))
    incidence.sum_duplicates()
    incidence.data.fill(1)
    incidence.sort_indices()
    graph = incidence @ incidence.T
    graph.setdiag(0)
    graph.eliminate_zeros()
    graph.sum_duplicates()
    graph.sort_indices()
    assert graph.dtype == np.int64 and np.all(graph.data > 0)
    assert (graph != graph.T).nnz == 0
    count, components = connected_components(graph, directed=False)
    report = dict(ncam=ncam, npoint=npoint, original_observations=len(ci),
                  unique_incidences=incidence.nnz, collapsed_duplicate_incidences=len(ci)-incidence.nnz,
                  undirected_edges=graph.nnz//2, total_undirected_weight=int(graph.data.sum()//2),
                  connected_components=int(count), component_sizes=np.bincount(components).tolist(),
                  isolated_cameras=int(np.count_nonzero(np.diff(graph.indptr)==0)),
                  conservative_memory_estimate_bytes=int(estimate),
                  graph_storage_bytes=graph.data.nbytes+graph.indices.nbytes+graph.indptr.nbytes,
                  graph_build_seconds=time.perf_counter()-start,
                  graph_sha256={name:array_sha(getattr(graph,name).astype('<i8')) for name in ('indptr','indices','data')})
    return graph, report


def canonicalize(labels):
    labels = np.asarray(labels, dtype=np.int64)
    order = sorted(np.unique(labels), key=lambda k:int(np.flatnonzero(labels==k)[0]))
    mapping = {int(old):new for new,old in enumerate(order)}
    return np.asarray([mapping[int(k)] for k in labels], dtype=np.int64)


def partition(graph, requested_k):
    ncam = graph.shape[0]
    k = min(requested_k, ncam)
    start = time.perf_counter()
    if k == ncam:
        labels, native_cut = np.arange(ncam, dtype=np.int64), int(graph.data.sum()//2)
    else:
        dtype = pymetis.zero_copy_dtype()
        adjacency = pymetis.CSRAdjacency(np.asarray(graph.indptr,dtype=dtype), np.asarray(graph.indices,dtype=dtype))
        result = pymetis.part_graph(k, adjacency=adjacency,
            vweights=np.ones(ncam,dtype=dtype), eweights=np.asarray(graph.data,dtype=dtype),
            recursive=False, contiguous=False, options=pymetis.Options(**SETTINGS), warn_on_copies=True)
        labels, native_cut = canonicalize(result.vertex_part), int(result.edge_cuts)
    if len(labels)!=ncam or len(np.unique(labels))!=k or np.any(labels<0) or np.any(labels>=k):
        raise ValueError('Invalid or empty METIS partition; no manual repair')
    weighted_cut = 0
    for i in range(ncam):
        sl=slice(graph.indptr[i],graph.indptr[i+1])
        weighted_cut += int(graph.data[sl][labels[graph.indices[sl]] != labels[i]].sum())
    assert weighted_cut%2 == 0 and weighted_cut//2 == native_cut
    sizes=np.bincount(labels,minlength=k)
    return labels, dict(requested_k=requested_k, actual_k=k, labels_sha256=array_sha(labels.astype('<i8')),
        cluster_sizes=sizes.tolist(), size_min=int(sizes.min()), size_max=int(sizes.max()),
        size_median=float(np.median(sizes)), max_size_over_mean=float(sizes.max()/(ncam/k)),
        weighted_edge_cut=weighted_cut//2, partition_seconds=time.perf_counter()-start,
        settings=SETTINGS, recursive=False, contiguous=False, unit_vertex_weights=True)


def observation_counts(ci,pi,npoint,labels):
    ci,pi=np.asarray(ci),np.asarray(pi)
    first=np.full(npoint,len(ci),dtype=np.int64)
    np.minimum.at(first,pi,np.arange(len(ci)))
    point_label=np.full(npoint,-1,dtype=np.int64)
    seen=first<len(ci)
    point_label[seen]=labels[ci[first[seen]]]
    cross=int(np.count_nonzero(labels[ci]!=point_label[pi]))
    low=np.full(npoint,len(labels),dtype=np.int64)
    high=np.full(npoint,-1,dtype=np.int64)
    np.minimum.at(low,pi,labels[ci]);np.maximum.at(high,pi,labels[ci])
    multi=seen&(high!=low)
    return dict(first_observation_anchor_cross_observations=cross,
                observations_on_multicluster_tracks=int(np.count_nonzero(multi[pi])),
                multicluster_tracks=int(np.count_nonzero(multi)), observed_tracks=int(seen.sum()))


def coefficients(vector,blocks):
    return np.concatenate([block['Q'].T@vector[block['ids']].reshape(-1) for block in blocks])


def lift(coeff,blocks,shape):
    result=np.zeros(shape);offset=0
    for block in blocks:
        rank=block['Q'].shape[1]
        result[block['ids']]=(block['Q']@coeff[offset:offset+rank]).reshape(-1,9)
        offset+=rank
    assert offset==len(coeff)
    return result


def gauge_operator(blocks,global_blocks):
    G=global_blocks[0]['Q']
    nc=G.shape[0]//9
    T=np.column_stack([coefficients(G[:,j].reshape(nc,9),blocks) for j in range(G.shape[1])])
    U,s,_=np.linalg.svd(T,full_matrices=False)
    keep=s>GAUGE_RANK_RTOL*s[0] if len(s) and s[0]>0 else np.zeros(len(s),dtype=bool)
    retained=U[:,keep]
    containment=max(float(np.linalg.norm(G[:,j].reshape(nc,9)-
                        lift(T[:,j],blocks,(nc,9)))) for j in range(G.shape[1]))
    return dict(T=T,U=retained,G=G,rank=int(keep.sum()),singular=s,
                containment=containment,coarse_rank=T.shape[0])


def report_projection(delta,blocks,global_blocks,reference_scale,gauge):
    legacy=geometry.projection_report(delta,blocks,global_blocks,reference_scale)
    G,T,U=gauge['G'],gauge['T'],gauge['U']
    nonglobal=delta-(G@(G.T@delta.reshape(-1))).reshape(delta.shape)
    q=coefficients(nonglobal,blocks)
    free=q-U@(U.T@q)
    projected_norm=float(np.linalg.norm(free))
    total_norm=float(np.linalg.norm(nonglobal))
    ext_norm=float(np.linalg.norm(nonglobal[:,:6]))
    threshold=legacy['near_zero_threshold']
    relative=legacy['norm']/max(float(reference_scale),np.finfo(float).tiny)
    leakage=float(np.linalg.norm(T.T@free))
    return dict(legacy=legacy, explicit_gauge_free=dict(
        fraction=None if total_norm<=threshold else projected_norm/total_norm,
        projected_norm=projected_norm, denominator_norm=total_norm,
        extrinsic_only_fraction=None if ext_norm<=threshold else projected_norm/ext_norm,
        extrinsic_denominator_norm=ext_norm, removed_coarse_rank=gauge['rank'],
        remaining_coarse_rank=gauge['coarse_rank']-gauge['rank'],
        gauge_leakage_norm=leakage, relative_gauge_leakage=leakage/max(projected_norm,1e-300)),
        difference_over_reference_norm=relative,
        numerically_sensitive_difference=legacy['norm']<=SENSITIVITY_RTOL*max(reference_scale,1.0),
        sensitivity_threshold=SENSITIVITY_RTOL*max(reference_scale,1.0),
        secondary_total_extrinsic_only_fraction=(None if legacy['extrinsic_norm']<=threshold else
                                                 legacy['projected_norm']/legacy['extrinsic_norm']))
