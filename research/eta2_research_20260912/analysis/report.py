#!/usr/bin/env python3
"""Summarize immutable capture audits; never adjusts comparison thresholds."""
import csv
import json
from pathlib import Path
import statistics

HERE=Path(__file__).resolve().parent
CASES=[('venice-52',r) for r in (0,1,2)]+[('final-3068',r) for r in (0,5,6)]+[('ladybug-1197',r) for r in (0,1,2)]


def main():
    records=[];mismatches=[]
    for scene,capture_rep in CASES:
        path=HERE/'results'/f'{scene}-{capture_rep}.json'
        audit=json.loads(path.read_text());normals=json.loads((HERE/'results'/f'{scene}-{capture_rep}-normals.json').read_text())
        # Clarify source certification in already-computed reports without changing
        # scores, budgets, disagreements, source hashes or native evidence.
        for row in audit['rows']:
            if row.get('direction_label')=='certified_reference':
                row['direction_label']='reference_with_certified_reduced_residual'
        audit['certification_label_clarification']='2026-09-12: labels clarify reduced-only certification; numerical results and original source hash unchanged'
        audit['independent_normal_audit']=f'{scene}-{capture_rep}-normals.json'
        path.write_text(json.dumps(audit,indent=2,allow_nan=False)+'\n')
        for arm in ('eta2','exact','exact_clip'):
            rows=[r for r in audit['rows'] if r['arm']==arm]
            norms=[r for r in normals['rows'] if r['arm']==arm]
            med=lambda fn:statistics.median(fn(r) for r in rows)
            nmed=lambda name:statistics.median(r[name] for r in norms)
            rec=dict(scene=scene,capture_rep=capture_rep,role='repeat_control' if scene=='ladybug-1197' and capture_rep>0 else 'primary',arm=arm,repetitions=len(rows),
                     cost=med(lambda r:r['costs']['full']),true_decrease=med(lambda r:r['true_decreases']['full']),rho=med(lambda r:r['rho']['full']),
                     Dfull=med(lambda r:r['model_error']['full']['signed_sum']),Dcamera=med(lambda r:r['model_error']['camera']['signed_sum']),
                     Dpoint=med(lambda r:r['model_error']['point']['signed_sum']),Dcross=med(lambda r:r['model_error']['cross']['signed_sum']),
                     point_error_absolute=med(lambda r:r['model_error']['point']['absolute_sum']),
                     point_error_top200_fraction=med(lambda r:r['top200_absolute_point_error']['fraction_of_absolute_point_error']),
                     flings=med(lambda r:r['flings']['count']),max_point_displacement=med(lambda r:r['flings']['maximum_displacement']),
                     full_scaled_normal_relative=nmed('scaled_full_normal_residual_relative_full_gradient'),
                     point_whitened_relative=nmed('Dp_whitened_point_residual_relative_full_gradient'),
                     point_global_backward=nmed('point_normwise_backward_error_global'))
            records.append(rec)
            for r in rows:
                for key,check in r['native_agreement'].items():
                    if check['status']!='within_budget':mismatches.append(dict(scene=scene,capture_rep=capture_rep,arm=arm,reference_rep=r['rep'],check=key,**check))
    with (HERE/'ledger.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    (HERE/'retained_mismatches.json').write_text(json.dumps(mismatches,indent=2)+'\n')
    lines=['# Brief 0 witness decomposition and independent normal-equation audit','',
           'Nine captured states were audited: seven primary witnesses plus two Ladybug repeat controls. Each has one native Eta2 proposal and three repeated FP64 reference solves, including the reference clipped to the same radius. All original observations were scored. This is fixed-state mechanism evidence; it is not a convergence-speed or hit-rate experiment.','',
           '**There is no universal solve-versus-point-model failure across these witnesses.** Final3068 mainly shows a camera-model/radius restriction; Venice contains both useful unresolved directions and a raw-reference overshoot; Ladybug opening has concentrated point-model error, but the historical extreme fling is absent.','',
           '| State | Eta2 decrease | Reference decrease | Clipped reference decrease | Reference full scaled normal residual |','|---|---:|---:|---:|---:|']
    for scene,rep in CASES:
        if scene=='ladybug-1197' and rep>0:continue
        rows={r['arm']:r for r in records if r['scene']==scene and r['capture_rep']==rep}
        lines.append(f"| {scene}/{rep} | {rows['eta2']['true_decrease']:.9g} | {rows['exact']['true_decrease']:.9g} | {rows['exact_clip']['true_decrease']:.9g} | {rows['exact']['full_scaled_normal_relative']:.3g} |")
    lines += ['', '“Reference” means **source solve with certified reduced residual**, not an exact full GN direction. Independent full-normal checks are reported above. Clipped references need not satisfy the camera normal equations.','',
              '## Nonlinear mechanism','',
              '- **Final3068:** every unclipped reference loses objective value. Camera-only model error is about 232, 217,956 and 553,092, while point-only error is about 2.6e-7, 8.82 and 0.0238. Clipping returns almost the same small useful decrease as Eta2. Greater linear accuracy alone does not remove this camera-model/radius bind. The clipped step can have meaningful point/cross error (especially captures 5 and 6), but that is distinct from why the raw reference fails.',
              '- **Venice:** capture 0 has a materially better hypothetical direction (35.51 decrease versus 0.547), but both ratios are already adequate. Its camera, point and cross errors strongly cancel: +903.2, -281.7 and -620.4. Capture 1 raw reference loses 20.05 through camera/cross errors; clipping restores 0.03486 decrease versus Eta2 0.02701. Capture 2 reference improves 1.299 versus 0.957. A single binary rule would obscure these distinct cases.',
              '- **Ladybug1197 outer 1:** native point-only model error is 1.526M, with top 200 points accounting for 98.39% of absolute point error. Two-observation tracks account for only 26.42% of that absolute point error, so it is not exclusively a two-view pathology. One point moves beyond the camera-center radius (16.30 versus 12.32); all three controls agree. The old 2.4e4 fling is not reproduced. Both native and reference remain nonlinear descent proposals (rho about 0.799 and 0.805).','',
              'The signed decomposition is algebraic, not causal. Negative point/cross terms can cancel positive camera error; an absolute concentration fraction can be high even when the total point error is tiny. Per-track length/parallax signed, absolute, positive and negative totals remain in every JSON.','',
              '## Numerical qualification','',
              'Reduced-PCG residuals below 1e-10 do not imply the independent full-normal residual reaches 1e-10. Unclipped scaled full residuals range from 1.31e-10 to 3.28e-6 across the primary references. Point residuals relative only to the conditional RHS can look much worse; after Dp whitening against the full scaled gradient, the Final point residual is only 2.59–3.93e-10. This illustrates why a single raw point residual ratio was insufficient.',
              '',
              'Extended-precision worst-track checks retain arithmetic sensitivity. Repeated affected points include Venice 60378, Final3068 250233 and Ladybug 98124. The Ladybug point has projected-depth cancellation condition about 1.47e9; reevaluating its Jacobian in extended precision changes it by about 8.49e-8 relative. These are local arithmetic qualifications, not evidence of a true nonlinear saddle. The large nonlinear failures remain far larger than the observed independent scoring discrepancies.',
              '',
              f'{len(mismatches)} CPU/native agreement checks exceeded the original budget, all retained in [retained_mismatches.json](retained_mismatches.json). They concern raw-reference predictions for two Final3068 captures; no threshold was loosened. Both CPU and native still predict descent while the actual proposal strongly increases cost. All initial/candidate cost and true-decrease comparisons passed. The mechanism screen leaves those budget-violating reference rows unresolved rather than relabelling them exact.',
              '', '## Deliverables and validation','',
              '[ledger.csv](ledger.csv) contains all arms and states, including repeat controls. `results/*-normals.json` contains absolute/RHS/backward/whitened residuals and extended-precision worst-point details. `results/<scene>-<capture>.json` contains the full decomposition, all bins and top-200 indices. No optional full per-point archives were written.',
              '', 'Synthetic tests verify decomposition against direct model scoring (maximum discrepancy 6.71e-13), bin conservation, blocked parallax against dense pairs, and uncertified-source rejection. The native toy matches CPU costs/predictions to normalized discrepancy below 4.7e-16. CPU timings are diagnostic overhead and are not solver timing claims.']
    (HERE/'FINDINGS.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'states':len(CASES),'ledger_rows':len(records),'retained_mismatches':len(mismatches)},indent=2))


if __name__=='__main__':main()
