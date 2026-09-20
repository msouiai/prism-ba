#!/usr/bin/env python3
"""Audit recovery-rule traces and produce a complete, failure-inclusive report."""
import argparse
import json
import math
import pathlib
import re
import statistics

from schur_recovery_study import ROOT, summarize, write

LABELS={'off':'Prism, guard off','rayleigh':'Prism, curvature + floor','x4':'Prism, ×4 transient',
        'x4_floor':'Prism, ×4 + floor','caspar32':'Caspar FP32','caspar64':'Caspar FP64'}

def fmt(cell):
    if not cell:return '—'
    if cell['hits']!=cell['runs']:
        return f"{cell['hits']}/{cell['runs']} hits"
    return f"{cell['median']:.3f} [{cell['range'][0]:.3f}, {cell['range'][1]:.3f}]"

def cells_table(rows,arms):
    cells={(r['scene'],r['arm']):r for r in summarize(rows)}
    text=['| Scene | '+' | '.join(LABELS.get(a,a) for a in arms)+' |',
          '|---|'+'---:|'*len(arms)]
    for scene in dict.fromkeys(r['scene'] for r in rows):
        text.append('| '+scene+' | '+' | '.join(fmt(cells.get((scene,a))) for a in arms)+' |')
    return '\n'.join(text)

def recovery_checks(rows):
    out=[]
    for r in rows:
        if r['arm'].startswith('caspar') or r['returncode']!=0:continue
        floor=1e-16;repairs=0;bounds=[]
        log=pathlib.Path(r['artifact']+'.log').read_text()
        for line in log.splitlines():
            if line.startswith('NUMERIC_REPAIR o='):
                v={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)}
                raw=4*v['lambda'] if r['arm'] in ('x4','x4_floor') else 4*max(v['lambda'],v['lambda']-v['rayleigh'])
                expected=min(1e16,max(1e-14,raw))
                if r['arm']!='x4':floor=max(floor,expected)
                assert math.isclose(v['next_lambda'],expected if r['arm']=='x4' else floor,rel_tol=1e-12),r
                bounds.append(v['rayleigh']+v['next_lambda']-v['lambda'])
                repairs+=1
                assert v['rebuild']==repairs
            elif line.startswith('ATTR_RADIUS o='):
                v={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)}
                assert v['next_lambda']>=floor*(1-1e-12),r
        assert repairs==r.get('numeric_rebuilds',repairs),r
        assert repairs<=32
        if r['arm']=='x4':assert r['numeric_floor']==1e-16
        out.append(dict(scene=r['scene'],arm=r['arm'],rep=r['rep'],rebuilds=repairs,
                        rebuild_limit_reached=repairs==32,directional_bounds=bounds,all_passed=True))
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--partial',action='store_true');a=ap.parse_args()
    if not a.partial:assert (ROOT/'COMPLETE.json').exists()
    phases={p.parent.name:json.loads(p.read_text()) for p in sorted(ROOT.glob('*/results.json'))}
    rows=[r for rr in phases.values() for r in rr]
    checks=recovery_checks(rows)
    write(ROOT/'recovery-validation.json',checks)
    failures=[r for r in rows if not r['valid']]
    compat=phases.get('compatibility',[])
    if len(compat)==4:
        for left,right in [('off','rebuilt_off'),('rayleigh','rebuilt_rayleigh')]:
            l=next(r for r in compat if r['arm']==left);r=next(r for r in compat if r['arm']==right)
            assert l['valid'] and r['valid']
            assert all(l[k]==r[k] for k in ('accepts','rejects','matvecs'))
            assert math.isclose(l['cost'],r['cost'],rel_tol=1e-12)
    measurement=[r for p,rr in phases.items() if p not in ('calibration','compatibility') for r in rr]
    totals=dict(complete=not a.partial,runs=len(rows),measurement_runs=len(measurement),
                valid_measurements=sum(r['valid'] for r in measurement),audit_or_execution_failures=len(failures),
                native_seconds=sum(r.get('seconds',0) for r in rows),process_wall=sum(r['process_wall'] for r in rows),
                max_valid_audit_error=max((r.get('audit_error',0) for r in rows if r['valid']),default=0),
                rebuilt_limit_runs=sum(c['rebuild_limit_reached'] for c in checks))
    write(ROOT/'totals.json',totals)
    plan=json.loads((ROOT/'plan.json').read_text())
    new=json.loads((ROOT/'new-anchors.json').read_text())
    historical=pathlib.Path('/workspace/prism-model-followup/final-caspar-pairs/results.json')
    combined=[]
    for r in json.loads(historical.read_text()):
        combined.append(dict(r,arm='rayleigh' if r['arm']=='candidate' else r['arm'],
                             valid=r['audit_error']<1e-7,origin=str(historical)))
    combined.extend(dict(r,origin=str(ROOT/'extension/results.json')) for r in phases.get('extension',[])
                    if r['arm'] in ('rayleigh','caspar32','caspar64'))
    cc={(c['scene'],c['arm']):c for c in summarize(combined)}
    comparisons=[]
    for scene in dict.fromkeys(r['scene'] for r in combined):
        for arm in ('caspar32','caspar64'):
            p=cc.get((scene,'rayleigh'));b=cc.get((scene,arm))
            if not p or not b or p['runs']!=3 or b['runs']!=3:continue
            comparisons.append(dict(scene=scene,baseline=arm,prism_hits=p['hits'],baseline_hits=b['hits'],
                speedup=b['median']/p['median'] if p['median'] and b['median'] else None,
                prism_median=p['median'],baseline_median=b['median']))
    combined_stats={arm:dict(runs=sum(r['arm']==arm for r in combined),
        hits=sum(r['arm']==arm and r['hit'] for r in combined)) for arm in ('rayleigh','caspar32','caspar64')}
    write(ROOT/'comparisons.json',dict(scope='Previous four scenes plus this six-scene extension; same frozen Prism/Caspar binaries and host, separate timing batches and declared audit tolerances. Not ten independent recordings.',
                                    counts=combined_stats,comparisons=comparisons))
    decision=dict(selected_arm='rayleigh',changed=False,
        reason='Retain the frozen incumbent. A persistent x4 floor matches it on Ladybug within the observed spread, but neither retained-floor variant is consistently superior on variable Final3068. The incumbent retains a directional damping bound at negligible scalar cost; this is a mathematical safeguard, not an originality claim.',
        simpler_control='Credible alternative; no consistent improvement or reliable global equivalence established by this small panel.',
        novelty='Roundoff-induced Schur indefiniteness and damping recovery are prior art. These results support a useful numerical safeguard, not a new trust-region algorithm.',
        next_issue='Investigate amplification of small numerical perturbations and nonlinear camera-radius collapse on Final3068/Dubrovnik before selecting another controller from timing noise.')
    if not a.partial:
        write(ROOT/'decision.json',decision)
        selected=json.loads(pathlib.Path('/workspace/prism-model-followup/selected_candidate.json').read_text())
        selected['scope']='Frozen incumbent retained after recovery ablations and six additional scenes. Combined primary useful-target hits: 26/30 across ten scenes; correlated BAL groups, not ten independent recordings. The new guard benefit is not a universal speedup and publication novelty is unproven.'
        selected['validation_report']=str(ROOT/'REPORT.md')
        selected['decision']=decision
        write(ROOT/'selected_candidate.json',selected)
    stalls=[]
    for r in phases.get('extension',[]):
        if r['arm']!='rayleigh' or r['hit'] or not r['valid']:continue
        log=pathlib.Path(r['artifact']+'.log').read_text()
        last=[line for line in log.splitlines() if line.startswith('ATTR_RADIUS o=')][-1]
        v={k:float(value) for k,value in re.findall(r'(\w+)=([^ ]+)',last)}
        scoring=re.search(r'\[scoring\] menu_evals=(\d+) alpha_evals=(\d+) backtrack_evals=(\d+) total_scored=(\d+)',log)
        stalls.append(dict(scene=r['scene'],rep=r['rep'],lambda_last=v['lambda'],radius_last=v['radius'],
            raw_camera_norm=v['raw_norm'],raw_over_radius=v['raw_norm']/v['radius'],
            numerical_floor=r['numeric_floor'],rebuilds=r['numeric_rebuilds'],
            nonlinear_rejects=r['rejects'],backtrack_evals=int(scoring[3]),total_scored=int(scoring[4]),
            ftol_stop='converged (OCA_FTOL' in log,cost=r['cost'],target=r['target'],
            excess_target_percent=100*(r['cost']/r['target']-1),artifact=r['artifact']))
    write(ROOT/'stall-analysis.json',stalls)
    lines=['# Numerical recovery controls and six-scene validation',
           '',f"Status: {'partial' if a.partial else 'complete'}. Frozen same-host study on `{plan['host']}`, RTX 2000 Ada 16 GB. All tables use native time to an independently audited common target; values are median [min, max] seconds. Misses and invalid endpoints remain in denominators. Three repeats are executions, not independent datasets.",
           '', 'The current curvature-plus-floor candidate remains the incumbent. The simple ×4-with-floor control matches its Ladybug time within the observed spread; transient ×4 recovery requires more rebuilds and is slower there. Final-3068 does not give a consistent recovery-rule ranking. The experiments support retaining a safe numerical damping floor, but do not demonstrate a general advantage for estimating its value from curvature or establish a novel TR algorithm.',
           '', '## Primary extension: 1% above fixed useful-quality anchors','',
           cells_table(phases.get('extension',[]),plan['primary_arms']),
           '', '## Combined context: previous four scenes plus this extension','',
           'The previously reported four-scene comparison and the new six-scene comparison use the same frozen candidate and Caspar binaries on the same host. They are separate timing batches, and the new study declares a different scoring-consistency tolerance. The previous results were not rerun for this table. Related BAL subsets are not independent recordings.',
           '',cells_table(combined,['rayleigh','caspar32','caspar64']),
           '',f"Target-hit counts: `{json.dumps(combined_stats,sort_keys=True)}`. Per-scene finite speed ratios are recorded in comparisons.json only when both arms reach all three targets. There is no finite speedup assigned to a failed target and no broad average over a selectively successful subset.",
           '', '## Recovery ablations','',cells_table(phases.get('controls',[]),plan['controls'])]
    if 'extension-controls' in phases:
        lines.extend(['','Additional scenes selected by the predeclared negative-curvature/guard-activation rule:','',
                      cells_table(phases['extension-controls'],plan['controls'])])
        pooled=[r for r in phases.get('extension',[]) if r['scene']=='final-3068' and r['arm'] in ('off','rayleigh')]
        pooled.extend(phases['extension-controls'])
        lines.extend(['','Both Final-3068 batches retained together: guard-off and curvature now have six runs, while each ×4 control has three. The changing outcomes of the identical guard-off configuration demonstrate why the latest batch alone is insufficient for attribution.','',
                      cells_table(pooled,plan['controls'])])
    lines.extend(['','## Remaining stalls','',
        'These are directly observed terminal states of the primary guarded runs. They distinguish the persistent numerical floor from the much larger controller damping and collapsed camera radius at termination.','',
        '| Scene / repeat | Excess above target | Final lambda | Numeric floor | Raw camera norm / radius | Backtrack evaluations |',
        '|---|---:|---:|---:|---:|---:|'])
    for r in stalls:
        lines.append(f"| {r['scene']} / {r['rep']} | {r['excess_target_percent']:.5f}% | {r['lambda_last']:.3g} | {r['numerical_floor']:.3g} | {r['raw_over_radius']:.1f} | {r['backtrack_evals']} |")
    lines.extend(['', 'These runs stop on the inherited eight-outer relative-improvement criterion (OCA_FTOL=1e-5), before the native cap. In the recorded terminal states, controller damping is far above the numerical floor and the camera step is strongly clipped. This points to poor nonlinear progress and excessive contraction as the next issue to investigate; it does not establish which tracks or model errors cause it. Merely increasing the numerical repair floor would not directly address this observed regime. Full counters and source traces are in stall-analysis.json.',
        '', 'A same-target Final-3068 guard-off pair has identical binary, input and solver flags. Initial rho differs by roughly 5e-16, but by outer 13 the two runs report rho=0.02113 and rho=0.10127, on opposite sides of the 0.1 acceptance threshold. The decision differs before any numerical repair can act (both guards are off). This is consistent with amplification of numerical perturbations, but the trace alone does not establish the source of the perturbations or which observations amplify them. The paired prefix is preserved in final3068-repeatability.json.'])
    lines.extend(['','## Target sensitivity','',
                  'The 0.5% and 2% targets are declared alternatives; the primary 1% target is unchanged. Ladybug-1723 and Trafalgar-126 were specified in advance. Additional scenes follow the recorded ambiguity rule, not a search for favorable results.'])
    for phase,rr in phases.items():
        if phase.endswith(('half-percent','two-percent')):
            proto=json.loads((ROOT/phase/'protocol.json').read_text())
            lines.extend(['',f"### {phase}",'',cells_table(rr,proto['arms'])])
    lines.extend(['','## Counters and endpoints','',
                  '| Phase | Scene | Arm | Hits | Median cost | Rebuilds across repeats | Rejects across repeats |',
                  '|---|---|---|---:|---:|---|---|'])
    for phase,rr in phases.items():
        if phase in ('calibration','compatibility'):continue
        for c in summarize(rr):
            costs=[v for v in c['costs'] if v is not None]
            lines.append(f"| {phase} | {c['scene']} | {c['arm']} | {c['hits']}/{c['runs']} | {statistics.median(costs) if costs else float('nan'):.6f} | {c['rebuilds']} | {c['rejects']} |")
    lines.extend(['','## Protocol and reproducibility','',
        'All arms share the original observation set, FP64 endpoint evaluator and SIMPLE_RADIAL objective with k2 fixed to zero. Guard-off and curvature arms use the unchanged previously selected binary. The two ×4 controls are an isolated derivative; they differ only in the repair size and whether the repair persists as a lower damping bound. All repairs rebuild point factors/RHS with camera and point damping coupled, retain the linearization and restart CG. Each arm has the same total 32-rebuild limit, original nonlinear acceptance and radius checks, and native cap. The transient control permits later controller damping to fall again. The retained ×4 control isolates persistence from measured-curvature selection.',
        '', '| Scene | Anchor | Primary target | Native cap (s) |','|---|---:|---:|---:|'])
    for scene,s in plan['scenes'].items():
        anchor=s['anchor'] if s['anchor'] is not None else new[scene]
        lines.append(f"| {scene} | {anchor:.9f} | {anchor*1.01:.9f} | {s['cap']} |")
    lines.extend(['',
        'Ladybug-810/1469 anchors come from the minimum valid exported endpoint of three guard-off and three Caspar FP64 calibration runs at the same budget. Calibration is excluded from speed comparisons. Other anchors are historical and their sources and input hashes are frozen in plan.json. These are useful reference costs, not certified optima. Ladybug subsets are correlated; scene count does not imply that many independent recordings.',
        '',plan['clocks'], '',plan['caps'],
        '', 'Caspar is the pinned standalone generated backend with the existing COLMAP-style default parameter profile, not a full COLMAP reconstruction run. No baseline parameters were tuned in this study.',
        '', 'The scoring-consistency tolerance for this new study is 1e-6 relative (0.0001%), declared before measurements based on the earlier 2.25e-7 arithmetic-order discrepancy. This is distinct from the previous report’s 1e-7 rule. No threshold was changed after seeing this study’s endpoints. A failed consistency check excludes a timing claim even if the endpoint appears close to target. Caspar FP32 native stopping retains the existing 0.1% empirical margin; qualification always uses the original-observation FP64 audit.',
        '',f"Totals: {json.dumps(totals,sort_keys=True)}.",
        '',f"Recovery formula, retained-floor and rebuild-accounting checks passed for {len(checks)} runs. Compatibility checks compare a single visited Final-1936 trajectory: accepted/rejected counts, products and audited objective match the frozen binary with the new controls disabled/defaulted. The CUDA fatbinary sections of the frozen and control executables are byte-identical (device-code-check.json), confirming that these controls change host-side recovery logic, not GPU kernels. This is not a general claim of GPU bitwise repeatability. The existing 100-case dense monotonicity and energy-identity check passed; it is an exact-arithmetic directional argument, not an all-directions or nonlinear convergence certificate.",
        '', 'One Final-13682 launch returned ETXTBSY before executing the solver: an objcopy section inspection briefly reopened the executable, without changing its hash. The unexecuted launch and original phase record are retained in infrastructure/blocked-launch/. That cell was repeated after the original scene batch, with all successful trials retained. infrastructure-incident.json records the event and recovery. It supplies no solver outcome or timing sample.',
        '', '### Excluded or failed runs',''])
    if failures:
        for r in failures:lines.append(f"- `{r['artifact']}`: {r.get('error')}; cost={r.get('cost')}, reported={r.get('reported')}, audit_error={r.get('audit_error')}.")
    else:lines.append('None.')
    lines.extend(['','## Novelty boundary','',
        'Roundoff-induced Schur indefiniteness and the resulting need for additional LM damping are explicit prior art: Demmel et al., Square Root Bundle Adjustment (CVPR 2021), section 6.4, reports the issue on 84/97 explicit-FP32 problems and seven FP64 problems. Its square-root formulation is a stability alternative. [Primary paper](https://cvg.cit.tum.de/_media/spezial/bib/demmel2021rootba.pdf).',
        '', 'Ceres already treats invalid LM steps as rejected steps that shrink the trust region and improve conditioning. The ×4 controls here are generic recovery baselines, not a full reproduction of Ceres or RootBA. [Official source](https://github.com/ceres-solver/ceres-solver/blob/master/internal/ceres/levenberg_marquardt_strategy.h).',
        '', 'The candidate contribution is the measured-curvature repair coupled to point elimination and a persistent floor in this mixed-storage GPU implementation. The monotonicity inequality alone is standard algebra. These experiments evaluate whether the quantitative measurement contributes beyond simple damping recovery; they cannot establish uniqueness in the literature. No multishift menu or improved residual-Hessian model is active in this candidate.',
        '', 'For a failed Rayleigh quotient q, the simple ×4 update already has the same directional positivity guarantee whenever q + 3 lambda > 0. The measured rule is more conservative and may add no benefit in that regime. Moreover, with frozen Schur blocks and u=(C+lambda Dp)^(-1) W^T E p, the directional derivative is q\'(lambda)=1+u^T Dp u/(p^T p), so coupled point damping can improve the direction by more than the camera-only lower bound predicts. These identities explain why a simple recovery rule can suffice; they are standard fixed-state algebra, not a new convergence result. Per-repair directional lower bounds are retained in recovery-validation.json.',
        '', 'The frozen candidate, control source/binary/headers, exact commands, input and binary hashes, logs, result JSON and losslessly compressed exported states are under `/workspace/prism-schur-recovery/`. The original candidate and production defaults remain unchanged. Builders and runners: `bench/build_schur_recovery.py`, `bench/schur_recovery_study.py`, `bench/run_schur_recovery.py`, and this report generator.',
        '', 'To reproduce after calibration: `python3 bench/run_schur_recovery.py`. Completed result cells are resumed. Regenerate the report with `python3 bench/report_schur_recovery.py`.'])
    report='\n'.join(lines)+'\n'
    (ROOT/'REPORT.md').write_text(report)
    pathlib.Path('/workspace/prism-ba/docs/schur_recovery_results.md').write_text(report)
    print(json.dumps(totals,indent=2))

if __name__=='__main__':main()
