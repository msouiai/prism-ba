#!/usr/bin/env python3
"""Read retained experiments and check small algebraic research examples; no GPU work."""
import argparse
import csv
import hashlib
import json
import pathlib
import re
import statistics

import numpy as np


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze(workspace):
    root = workspace / 'prism-camera-tr/ladybug1723-round3-full'
    rows = []
    for rep in (1, 2, 3):
        stem = root / f'on-{rep}'
        log = stem.with_suffix('.log').read_text()
        with stem.with_suffix('.csv').open() as f:
            trace = list(csv.DictReader(line for line in f if not line.startswith('#')))
        attempts = []
        for line in log.splitlines():
            if line.startswith('CAMERA_TR o='):
                attempts.append({k: float(v) for k, v in re.findall(r'(\w+)=([\d.e+-]+)', line)})
        for target in (456628., 452676.):
            hit = next(t for t in trace if float(t['cost']) <= target)
            n = int(hit['iter'])
            prefix = [a for a in attempts if int(a['o']) < n]
            accepted = [a for a in prefix if a['accept']]
            iteration = next(line for line in log.splitlines()
                             if re.match(r'  MFCG it\s+' + str(n) + r'\s+cost', line))
            rows.append(dict(arm='original_five_shift_TR', rep=rep, target=target,
                             seconds=float(hit['wall_s']), outer=n, cost=float(hit['cost']),
                             rejected_attempts=sum(not a['accept'] for a in prefix),
                             boundary_accepted=sum(a['norm'] >= .999*a['radius'] for a in accepted),
                             median_accepted_rho=statistics.median(a['rho'] for a in accepted),
                             cumulative_reported_matvecs=int(re.search(r'mv=(\d+)', iteration)[1]),
                             provenance=str(stem)))
    for rep in (1, 2, 3):
        path = workspace / f'caspar-1723/run{rep}.log'
        trace = []
        for line in path.read_text().splitlines():
            m = re.search(r'TRACE iter=(\d+) cost=([\d.e+-]+) seconds=([\d.e+-]+) accepted=(\d+) pcg=(\d+)', line)
            if m:
                trace.append(dict(iter=int(m[1]), cost=float(m[2]), seconds=float(m[3]),
                                  accepted=int(m[4]), reported_pcg=int(m[5])))
        for target in (456628., 452676.):
            hit_index = next(j for j, a in enumerate(trace) if a['cost'] <= target)
            hit = trace[hit_index]
            prefix = trace[:hit_index+1]
            rows.append(dict(arm='caspar_fp64', rep=rep, target=target,
                             seconds=hit['seconds'], attempts=hit_index+1, cost=hit['cost'],
                             rejected_attempts=sum(not a['accepted'] for a in prefix),
                             accepted=sum(a['accepted'] for a in prefix), provenance=str(path),
                             note='Native trace crossing; intermediate states were not exported/audited.'))
    historical = json.loads((workspace / 'prism-lm-point-rescue/caspar-pairs/results.json').read_text())
    historical_summary = []
    for scene in sorted({r['scene'] for r in historical}):
        for arm in sorted({r['arm'] for r in historical}):
            subset = [r for r in historical if r['scene'] == scene and r['arm'] == arm]
            times = [r['crossing'] for r in subset if r['hit']]
            historical_summary.append(dict(scene=scene, arm=arm, n=len(subset), hits=len(times),
                median_seconds=statistics.median(times) if times else None,
                time_range=[min(times), max(times)] if times else None,
                target=subset[0]['target'], cost_range=[min(r['cost'] for r in subset), max(r['cost'] for r in subset)]))
    paths = [workspace / 'prism-camera-tr/prism-tr', workspace / 'prism-camera-tr/source-tr.cu',
             workspace / 'prism-camera-tr-interior/prism-tr', workspace / 'prism-caspar-current/caspar64']
    return dict(ladybug=rows, historical_optimized_TR_pairs=historical_summary,
                hashes={str(p): digest(p) for p in paths})


def algebra_checks():
    rng = np.random.default_rng(20260909)
    max_gap_error = 0.
    max_quartic_error = 0.
    max_joint_error = 0.
    max_schur_error = 0.
    for _ in range(100):
        r, v, defect = rng.normal(size=(3, 20))
        trial = r + v + defect
        prediction = -r @ v - .5*(v @ v)
        actual = .5*(r @ r - trial @ trial)
        gap = (r+v) @ defect + .5*(defect @ defect)
        max_gap_error = max(max_gap_error, abs(prediction-actual-gap)/max(1., abs(gap)))
        coeff = [.5*(r@r), r@v, .5*(v@v)+r@defect, v@defect, .5*(defect@defect)]
        for alpha in (0., .125, .5, .875, 1.):
            direct = .5*np.linalg.norm(r+alpha*v+alpha*alpha*defect)**2
            polynomial = sum(c*alpha**i for i, c in enumerate(coeff))
            max_quartic_error = max(max_quartic_error, abs(direct-polynomial)/max(1., abs(direct)))
        J = rng.normal(size=(15, 7))
        H = J.T @ J
        g = rng.normal(size=7)
        D = rng.uniform(.5, 2., size=7)
        scale = np.diag(1/np.sqrt(D))
        A, b = scale @ H @ scale, -scale @ g
        for lam in (.01, 1., 100.):
            physical = np.linalg.solve(H+lam*np.diag(D), -g)
            transformed = scale @ np.linalg.solve(A+lam*np.eye(7), b)
            max_joint_error = max(max_joint_error, np.linalg.norm(physical-transformed)/np.linalg.norm(physical))
            C = H[4:, 4:] + lam*np.diag(D[4:])
            W = H[:4, 4:]
            S = H[:4, :4] + lam*np.diag(D[:4]) - W @ np.linalg.solve(C, W.T)
            rhs = -g[:4] + W @ np.linalg.solve(C, g[4:])
            dc = np.linalg.solve(S, rhs)
            dp = np.linalg.solve(C, -g[4:] - W.T @ dc)
            max_schur_error = max(max_schur_error, np.linalg.norm(np.r_[dc, dp]-physical)/np.linalg.norm(physical))
    # Perspective division along an affine camera-space path, without radial distortion.
    q = np.array([.3, -.2, 2.])
    errors = []
    for relative_depth_change in (.01, .1, -.1, -.5, -.9):
        dq = np.array([.07, .04, relative_depth_change*q[2]])
        linear = -(dq[:2]*q[2] - q[:2]*dq[2]) / q[2]**2
        actual = -(q+dq)[:2]/(q+dq)[2] + q[:2]/q[2]
        measured = np.linalg.norm(actual-linear)/np.linalg.norm(linear)
        formula = abs(relative_depth_change)/abs(1+relative_depth_change)
        assert abs(measured-formula) < 1e-12
        errors.append(dict(relative_depth_change=relative_depth_change, relative_linearization_error=measured))
    # Camera-only damping cannot remove the conditional point-only component.
    J = rng.normal(size=(20, 7)); H = J.T @ J; g = rng.normal(size=7)
    C = H[4:, 4:] + .1*np.eye(3); W = H[:4, 4:]
    dc = np.linalg.solve(H[:4,:4]+1e12*np.eye(4)-W@np.linalg.solve(C,W.T),
                         -g[:4]+W@np.linalg.solve(C,g[4:]))
    dp = np.linalg.solve(C, -g[4:]-W.T@dc)
    floor = np.linalg.solve(C,-g[4:])
    assert np.linalg.norm(dp-floor)/np.linalg.norm(floor) < 1e-9
    for error in (max_gap_error, max_quartic_error, max_joint_error, max_schur_error):
        assert error < 1e-11
    return dict(random_examples=100, maximum_relative_gap_identity_error=max_gap_error,
                maximum_relative_quartic_identity_error=max_quartic_error,
                maximum_joint_coordinate_solve_error=max_joint_error,
                maximum_joint_schur_solve_error=max_schur_error,
                perspective_examples=errors, camera_damping_1e12=dict(camera_norm=float(np.linalg.norm(dc)),
                point_norm=float(np.linalg.norm(dp)), point_only_limit_norm=float(np.linalg.norm(floor))),
                scope='Algebraic verification only. No BA speed measurement or curvature-model rollout.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', type=pathlib.Path, default=pathlib.Path('/workspace'))
    parser.add_argument('--output', type=pathlib.Path)
    args = parser.parse_args()
    result = analyze(args.workspace)
    result['algebra_checks'] = algebra_checks()
    result['scope'] = 'Retrospective trace analysis and CPU algebra only; no new solver runs.'
    result['script_sha256'] = digest(pathlib.Path(__file__))
    encoded = json.dumps(result, indent=2)+'\n'
    if args.output:
        with args.output.open('x') as f:
            f.write(encoded)
    print(encoded)


if __name__ == '__main__':
    main()
