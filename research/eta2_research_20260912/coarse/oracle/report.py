#!/usr/bin/env python3
"""Summarize every preregistered terminal-oracle repetition without selection."""
import csv
import json
from pathlib import Path
import statistics

P=Path(__file__).resolve().parent

def main():
    cells=[];flat=[]
    for witness in (0,5,6):
        runs=[json.loads((P/'results'/f'final-3068-{witness}-{rep}.json').read_text()) for rep in range(3)]
        assert len({r['protocol_sha256'] for r in runs})==1
        for r in runs:
            assert r['operator_parity_pass']
            assert all(a['model_identity_pass'] and a['full_objective_score_init_relative_error']<=1e-10 for a in r['arms'])
            assert min(r['coarse_eigenvalues'])>0
            for a in r['arms']:
                flat.append(dict(witness=witness,rep=r['rep'],arm=a['arm'],coarse_decrement=r['camera_coarse_decrement'],
                                 point_constant=r['point_only_damped_constant'],control_gain=a['eta2_native_gain'],
                                 gain=a['true_decrease'],rho=a['rho'],gain_over_control=a['true_gain_over_eta2'],
                                 raw_norm_over_radius=r['arms'][0]['camera_scaled_norm']/r['metadata']['radius'],
                                 clip_scale=a['clip_scale'],practical_gate=a['practical_gate']))
        raw=[next(a for a in r['arms'] if a['arm']=='raw') for r in runs]
        clip=[next(a for a in r['arms'] if a['arm']=='clipped') for r in runs]
        median=lambda name:statistics.median(r[name] for r in runs)
        cells.append(dict(witness=witness,N=3,coarse_decrement=median('camera_coarse_decrement'),
                          point_constant=median('point_only_damped_constant'),control_gain=clip[0]['eta2_native_gain'],
                          raw_gain_median=statistics.median(a['true_decrease'] for a in raw),
                          raw_rho_median=statistics.median(a['rho'] for a in raw),
                          clipped_gain_median=statistics.median(a['true_decrease'] for a in clip),
                          clipped_rho_median=statistics.median(a['rho'] for a in clip),
                          clipped_gain_over_control=statistics.median(a['true_gain_over_eta2'] for a in clip),
                          numerical_zero_all=all(r['decrement_numerically_zero'] for r in runs),
                          practical_gate=all(a['practical_gate'] for a in clip),
                          raw_beats_control=all(a['rho']>.1 and a['true_decrease']>a['eta2_native_gain'] for a in raw),
                          raw_norm_over_radius=raw[0]['camera_scaled_norm']/runs[0]['metadata']['radius'],
                          cpu_seconds=[r['total_cpu_seconds'] for r in runs],
                          deterministic_repetition_gain_spread=max(a['true_decrease'] for a in clip)-min(a['true_decrease'] for a in clip)))
    passed=sum(c['practical_gate'] for c in cells)
    result=dict(cells=cells,practical_gate_states=passed,required_states=2,continue_nonlinear_collective_rollout=passed>=2,
                original_all_zero_decrement_kill=all(c['numerical_zero_all'] for c in cells),
                raw_improves_over_eta2_states=sum(c['raw_beats_control'] for c in cells),
                verdict='Close this registered terminal oracle/correction branch.' if passed<2 else 'Continuation requires a new registration.',
                limitation='N3 repeats are deterministic fixed-state CPU evaluations; not endpoint, speed or optimizer hit-rate claims.')
    (P/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    with (P/'ledger.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
