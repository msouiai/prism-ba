#!/usr/bin/env python3
"""Summarize all registered fixed-state repetitions without selecting an arm."""
import csv
import json
from pathlib import Path
import statistics as st

HERE=Path(__file__).resolve().parent
def main():
    results=[json.loads(p.read_text()) for p in sorted((HERE/'results').glob('final-3068-*.json'))]
    rows=[];summary=[]
    for witness in (0,5,6):
        cell=[r for r in results if Path(r['capture']).name==f'final-3068-capture-{witness}']
        if sorted(r['rep'] for r in cell)!=[0,1,2]:raise ValueError(f'incomplete witness {witness}')
        old=json.loads((HERE.parent/'oracle/results'/f'final-3068-{witness}-0.json').read_text())
        oldraw=next(a for a in old['arms'] if a['arm']=='raw')
        for r in cell:
            d=r['cumulative_displacement'];rows.append(dict(witness=witness,rep=r['rep'],rank=r['rank'],eta2_gain=r['eta2_native_gain'],
                initial_decrement=r['attempts'][0]['decrement'],coarse_gain=r['cumulative']['gain'],ratio_eta2=r['gain_over_eta2'],gate=r['mechanism_gate'],
                accepted=sum(x['accepted'] for x in r['attempts']),backtrack_halvings=sum(x['backtracking_halvings'] for x in r['attempts']),
                native_fine_radius=d['old_radius'],camera_norm_over_radius=d['camera_norm_over_old_radius'],point_max=d['point_displacement_max'],
                same_cluster_cost_drift=r['cumulative']['same_cluster_gain'],normal_assemblies=r['normal_assemblies'],full_scores=r['full_scores'],
                total_cpu_seconds=r['total_cpu_seconds'],setup_cpu_seconds=r['setup_cpu_seconds']))
        summary.append(dict(witness=witness,N=len(cell),rank=cell[0]['rank'],eta2_gain=cell[0]['eta2_native_gain'],
            initial_decrement=st.median(r['attempts'][0]['decrement'] for r in cell),
            passenger_gain_median=st.median(r['cumulative']['gain'] for r in cell),passenger_gain_range=[min(r['cumulative']['gain'] for r in cell),max(r['cumulative']['gain'] for r in cell)],
            passenger_gain_ratio=st.median(r['gain_over_eta2'] for r in cell),gate=all(r['mechanism_gate'] for r in cell),
            objective_gain_percent=100*st.median(r['cumulative']['gain']/r['metadata']['cost'] for r in cell),
            cross_cluster_observations=cell[0]['attempts'][0]['cross_observations'],total_observations=int(cell[0]['metadata']['nobs']),
            camera_cluster_sizes=cell[0]['clustering']['cluster_sizes'],
            camera_norm_over_radius=st.median(r['cumulative_displacement']['camera_norm_over_old_radius'] for r in cell),
            point_max=st.median(r['cumulative_displacement']['point_displacement_max'] for r in cell),
            cpu_seconds_median=st.median(r['total_cpu_seconds'] for r in cell),cpu_seconds_range=[min(r['total_cpu_seconds'] for r in cell),max(r['total_cpu_seconds'] for r in cell)],
            previous_eliminated_point_raw_gain=oldraw['true_decrease'],
            previous_eliminated_point_raw_ratio=oldraw['true_gain_over_eta2'],
            same_cluster_cost_drift_max=max(abs(r['cumulative']['same_cluster_gain']) for r in cell)))
    with (HERE/'ledger.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    passed=sum(s['gate'] for s in summary)
    result=dict(cells=summary,mechanism_gate_states=passed,native_continuation_allowed=passed>=2,
                max_score_init_relative_error=max(r['score_init_relative_error'] for r in results),
                max_whitening_error=max(b['whitening_error'] for r in results for b in r['basis']),
                max_coarse_solve_relative_residual=max(a['solve_relative_residual'] for r in results for a in r['attempts']),
                all_repetitions_recorded=True,limitation='N3 deterministic fixed-state CPU repetitions are not independent optimizer trajectories or GPU speed measurements.')
    (HERE/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['# Nonlinear passenger-cluster correction: registered witness pretest','',
        f'The actual passenger formulation passes the mechanism gate on **{passed}/3** witness states. '+('A native continuation can be separately registered.' if passed>=2 else 'Close this passenger formulation under the registered rule.'),'',
        'This experiment transforms each camera cluster and its assigned points together. It does not impose the old fine radius. Every original observation remains in the objective. The earlier eliminated-point oracle is a different model; its raw gains are shown for context, not pooled.','',
        '| Witness | Eta2 gain | Passenger gain (3 attempts) | / Eta2 | Initial decrement | Camera norm / old radius | CPU seconds | Prior eliminated-point raw gain |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for s in summary:lines.append(f"| Final3068-{s['witness']} | {s['eta2_gain']:.9g} | {s['passenger_gain_median']:.9g} | {s['passenger_gain_ratio']:.6g} | {s['initial_decrement']:.6g} | {s['camera_norm_over_radius']:.6g} | {s['cpu_seconds_median']:.3f} | {s['previous_eliminated_point_raw_gain']:.9g} |")
    lines+=['','All cells use three deterministic CPU repetitions of the same saved state, not three independent trajectories. These are mechanism observations, not endpoint wins, target hit rates, or evidence of GPU speed. Full CPU wall includes loading, clustering, metric factorization, normal assembly and backtracking objective scores.',
        '',f"Maximum score-init relative discrepancy: {result['max_score_init_relative_error']:.3g}; joint metric whitening error: {result['max_whitening_error']:.3g}; damped coarse solve relative residual: {result['max_coarse_solve_relative_residual']:.3g}.",
        '', 'The joint metric keeps all seven modes where passengers make them independent, including singleton-camera scale. The fixed episode metric and initial world centroids stay unchanged across three left-increment similarity steps. Intrinsics remain fixed. Analytically invariant same-cluster Jacobian rows are zero, but their full scores are still evaluated and numerical drift is reported.',
        '', 'The geometry materially limits interpretation: deterministic center clustering isolates a handful of distant cameras while one cluster holds 3058–3059 of 3068 cameras. Only 395–582 of 1,653,812 observations cross clusters. Six singleton clusters have no first-observation passenger points, explaining the measured joint rank 50. This is consistent with correcting a few outlying cameras; it does not demonstrate recovery of distributed long-wavelength modes. No clustering rule was changed after these outcomes.',
        '', 'All three full steps are accepted at witnesses 0 and 5 without backtracking. Witness 6 accepts after 0, 1, 5 halvings. Its full-step success alone is not evidence for more accurate quadratic modeling: nonlinear backtracking remains necessary. Same-cluster cumulative cost drift is at most 1.28e-7 objective units, far below the measured gains.',
        '', 'The best cumulative relative objective improvement is 0.04433% (witness 5); witness 6 improves 0.0000435% and witness 0 only0.000000106%. Thus large ratios against a nearly stopped fine step are not endpoint-quality wins under the 0.15% rule. The improvement also does not by itself establish that a full trajectory can reach the registered target. The frozen Eta2 champion remains the current winner until a separately registered native same-target continuation earns promotion.',
        '', 'Original source-normal/prediction mismatches remain in the campaign numerical audit. These coherent CPU coarse calculations do not repair or silently replace the frozen compact native operator.',
        '', 'See `ledger.csv` for all nine runs, `results/*.json` for every attempted alpha, rho, point motion and cost, `toy_checks.json` for pre-grid correctness, and `IMPLEMENTATION_NOTES.md` for frozen algebra choices.']
    (HERE/'FINDINGS.md').write_text('\n'.join(lines)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
