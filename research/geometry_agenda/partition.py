"""Geometry-weighted partitions from normalized Schur coupling, no labels."""
import itertools
import numpy as np
from geometry import project
from reference_ba import accumulate

def automatic_partition(s, obs, groups=3, confidence=False):
    ci = obs[:, 0].astype(int); pi = obs[:, 1].astype(int)
    residual, _, jc, jp, _, _ = project(s, obs, 6, True)
    nc, np_ = len(s.R), len(s.X)
    B, C, E = accumulate(ci, pi, jc, jp, nc, np_)
    eigen, vectors = np.linalg.eigh(C)
    inv = np.zeros_like(eigen)
    good = eigen > np.maximum(1e-16, eigen[:, -1, None]*1e-10)
    inv[good] = 1/eigen[good]
    Cinv = (vectors*inv[:, None, :])@vectors.transpose(0, 2, 1)
    d = np.maximum(np.diagonal(B, axis1=1, axis2=2), np.maximum(1e-12, 1e-3*np.trace(B, axis1=1, axis2=2)[:, None]/6))
    W = E/np.sqrt(d.ravel())[:, None]
    CE = (Cinv@W.T.reshape(np_, 3, nc*6)).reshape(np_*3, nc*6)
    coupling = W@CE
    graph = np.linalg.norm(coupling.reshape(nc, 6, nc, 6).transpose(0, 2, 1, 3), axis=(2, 3))
    np.fill_diagonal(graph, 0)
    scale = np.sqrt(np.maximum(graph.sum(axis=1), 1e-300))
    normalized = graph/scale[:, None]/scale[None, :]
    _, v = np.linalg.eigh(normalized)
    features = v[:, -groups:]
    features /= np.maximum(1e-300, np.linalg.norm(features, axis=1))[:, None]
    chosen = [0]
    while len(chosen) < groups:
        distance = np.min(np.sum((features[:, None]-features[chosen][None])**2, axis=2), axis=1)
        distance[chosen] = -1
        chosen.append(int(np.argmax(distance)))
    centers = features[chosen].copy(); labels = np.zeros(nc, dtype=int)
    for _ in range(30):
        previous = labels.copy()
        labels = np.argmin(np.sum((features[:, None]-centers[None])**2, axis=2), axis=1)
        for group in range(groups):
            if np.any(labels == group): centers[group] = features[labels == group].mean(axis=0)
        if np.array_equal(previous, labels): break
    order = [labels[0]]+[g for g in range(groups) if g != labels[0]]
    relabel = np.argsort(order); labels = relabel[labels]
    pc_strength = np.linalg.norm(W.reshape(nc, 6, np_, 3).transpose(0, 2, 1, 3), axis=(2, 3))
    if confidence:
        weight = np.zeros((nc, np_))
        np.add.at(weight, (ci, pi), 1/(1+np.sum(residual*residual, axis=1)/4.))
        pc_strength *= weight
    vote = np.array([pc_strength[labels == g].sum(axis=0) for g in range(groups)])
    points = np.argmax(vote, axis=0); points[0] = 0
    return labels, points

def partition_agreement(found_c, found_p, true_c, true_p):
    best = None
    for order in itertools.permutations(range(3)):
        mapping = np.array(order)
        score = float(np.mean(mapping[found_c] == true_c))
        if best is None or score > best[0]:
            best = score, float(np.mean(mapping[found_p] == true_p))
    return {'camera_agreement': best[0], 'point_agreement': best[1]}
