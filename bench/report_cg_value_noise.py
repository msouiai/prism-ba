#!/usr/bin/env python3
"""Paired seed-level summaries; never turn misses into finite speedups."""
import json,math,pathlib,statistics as st
ROOT=pathlib.Path('/tmp/prism-cg-value-noise')
REPO=pathlib.Path(__file__).parents[1]
def read(n):return json.loads((ROOT/n).read_text())
def median_range(values,digits=4):
    return f'{st.median(values):.{digits}f} [{min(values):.{digits}f}, {max(values):.{digits}f}]'
def main():
    assert read('completion.json')['complete']
    rows=read('rows.json');cases=read('cases.json');assert len(rows)==126
    pairs=[]
    for case in cases:
        arms={a:[r for r in rows if r['key']==case['key'] and r['arm']==a] for a in ['champion','conservative']}
        assert all(len(rr)==3 for rr in arms.values())
        ratio=None
        if all(r['hit'] for rr in arms.values() for r in rr):
            ratio=st.median(r['target_seconds'] for r in arms['champion'])/st.median(r['target_seconds'] for r in arms['conservative'])
        pairs.append(dict(key=case['key'],scene=case['scene'],level=case['level'],seed=case['seed'],speedup=ratio,
                          hits={a:sum(r['hit'] for r in rr) for a,rr in arms.items()}))
    eligible=[x['speedup'] for x in pairs if x['speedup'] is not None]
    metrics=dict(runs=len(rows),native_seconds=sum(r['seconds'] for r in rows),
        hits={a:sum(r['hit'] for r in rows if r['arm']==a) for a in ['champion','conservative']},
        maximum_endpoint_audit_error=max(r['audit_error'] for r in rows),
        maximum_initial_cost_error=max(r['initial_error'] for r in rows),complete_pairs=len(eligible),total_pairs=len(pairs),
        all_case_geometric_speedup=math.exp(st.mean(map(math.log,eligible))) if len(eligible)==len(pairs) else None,
        conditional_geometric_speedup=math.exp(st.mean(map(math.log,eligible))) if eligible else None,
        candidate_extra_stops=sum(r['value_summary'].get('stops',0) for r in rows if r['arm']=='conservative'),
        candidate_disabled_runs=sum(r['value_summary'].get('disabled',0)>0 for r in rows if r['arm']=='conservative'))
    summary=dict(metrics=metrics,pairs=pairs)
    (ROOT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    lines=['# Calibrated initialization-noise stress test','',
      'The frozen conservative CG marginal-value rule is compared with the sustained eta2 champion. Same binary, initial lambda 0.1, original L2 observations, intrinsics and prior quality targets. This phase changes starting cameras and points only; observation noise and Caspar are not tested. No solver tuning or default changes.','',
      f"Completed {metrics['runs']} runs: champion {metrics['hits']['champion']}/63 target hits; conservative {metrics['hits']['conservative']}/63. Both arms hit all three timing repeats on {len(eligible)}/21 matched starting states.",'',
      ('All-case geometric speedup: '+f"{metrics['all_case_geometric_speedup']:.4f}x." if metrics['all_case_geometric_speedup'] is not None else
       'All-case geometric speedup is withheld because at least one matched starting state has a target miss.'),'',
      '**Verdict: retain the existing champion.** The stress test exposes seed-dependent reversals. It does not show catastrophic numerical failure, and many missed endpoints are only a fraction of a percent above target. Nevertheless, there is a substantial same-target slowdown on a case where both arms succeed, independent of how near-target misses are classified.','',
      'Venice mild seed 43 is the clearest counterexample: candidate median 0.3544s versus champion 0.2022s, about 75% more time. CG matvecs fall 83 to 74, but outer iterations increase 8 to 20, with zero rejections in both arms. On mild seed 17, the candidate instead improves 0.3062s to 0.1953s. A cheap linear solve is not a reliable predictor of the best nonlinear trajectory.','',
      'Dubrovnik mild seed 17 gives another warning: the champion reaches the target in all 3 repeats, median 1.1975s with 25 outers/1 reject; the candidate misses all 3 at roughly 0.59% above target, with 74 outers/17 rejects. The small error gap should not be described as a catastrophic quality regression, but the extra outer work and rejection storm matter for convergence speed.','',
      'Trafalgar retains a 1.1046x speedup at stronger noise, but mild noise reverses the result to 0.9315x. Venice mild averages 1.0059x across seeds, hiding its large per-seed win and loss. The aggregate therefore cannot substitute for the paired-seed tables.','',
      '## Input calibration and its limits','',
      'Three fixed Gaussian directions per scene (seeds 17,29,43), scaled independently to initial full reprojection RMS ratios 1.10 and 1.50. The same seed direction is shared by the two severity levels. Rotation changes are additive angle-axis coordinates; camera centers and points use Gaussian coordinate changes relative to scene radius. Translation is reconstructed from the perturbed rotation and center. This is not isotropic SO(3) noise.','',
      'Calibration uses only the starting objective, never solver outcomes. All observation bytes and intrinsics are unchanged; all 18 serialized variants meet RMS tolerance 1e-6 with zero new observation depth-sign changes. The original objective is unchanged, so the previous targets remain applicable.','',
      'Full RMS is a poor proxy for uniform geometric disruption on these data. Trafalgar and Dubrovnik reach the requested cost increase through a few highly sensitive observations while most projected features barely move. Venice has much more distributed image displacement. Therefore this panel measures sensitivity to these particular initializations; it cannot establish robustness to general pose error. The contrast was identified during input calibration before solver measurements and the predeclared panel was retained.','',
      '| Scene | Level | Seed | Amplitude | RMS ratio | Projection displacement px: median / p95 / max |',
      '|---|---|---:|---:|---:|---:|']
    for c in cases:
        if c['level']=='clean':continue
        v=c['projection_displacement_px']
        lines.append(f"| {c['scene']} | {c['level']} | {c['seed']} | {c['amplitude']:.6g} | {c['rms_ratio']:.6f} | {v[0]:.6g} / {v[1]:.6g} / {v[2]:.6g} |")
    lines+=['','## Summary by scene and severity','',
      'Clean cells have three timing runs per arm; noisy cells have three seeds x three timing runs per arm. The speed column is the geometric mean of paired seed-median time ratios, and is shown only when every run in both arms hits. Noisy seeds are not timing repeats or independent scenes.','',
      '| Scene | Level | Champion hits | Conservative hits | Speedup (champion / conservative) |',
      '|---|---|---:|---:|---:|']
    for scene,level in dict.fromkeys((c['scene'],c['level']) for c in cases):
        pp=[x for x in pairs if x['scene']==scene and x['level']==level]
        n=3*len(pp);hits={a:sum(x['hits'][a] for x in pp) for a in ['champion','conservative']}
        ratio=math.exp(st.mean(math.log(x['speedup']) for x in pp)) if all(x['speedup'] is not None for x in pp) else None
        lines.append(f"| {scene} | {level} | {hits['champion']}/{n} | {hits['conservative']}/{n} | "+(f'{ratio:.4f}x' if ratio is not None else 'Withheld: miss')+' |')
    lines+=['','## Every matched input','',
      'Time-to-target median [min,max] uses successful runs only and is marked if any repeat missed. Cost and work are medians over all three runs, including misses. A miss may be an early stall or a cap exit; it is not assigned an invented target time.','',
      '| Input | Arm | Hits | Target seconds median [min,max] | Final audited cost | Cost gap to target | Outers | Rejects | Matvecs | Extra stops | Repair fallback runs |',
      '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for c in cases:
        for a in ['champion','conservative']:
            rr=[r for r in rows if r['key']==c['key'] and r['arm']==a]
            ts=[r['target_seconds'] for r in rr if r['hit']]
            tm=median_range(ts) if ts else 'MISS'
            if ts and len(ts)<3:tm+=' (hits only)'
            cost=st.median(r['audit_cost'] for r in rr)
            vals=[st.median(r[k] for r in rr) for k in ['outers','rejects','matvecs']]
            stops=st.median(r['value_summary'].get('stops',0) for r in rr)
            disabled=sum(r['value_summary'].get('disabled',0)>0 for r in rr)
            lines.append(f"| {c['key']} | {a} | {len(ts)}/3 | {tm} | {cost:.6f} | {100*(cost/c['target']-1):+.4f}% | {vals[0]:g} | {vals[1]:g} | {vals[2]:g} | {stops:g} | {disabled}/3 |")
    lines+=['','## Verification and reproducibility','',
      f"All 126 original-observation FP64 endpoint audits passed; maximum relative discrepancy {metrics['maximum_endpoint_audit_error']:.3g}. Maximum native/calibrated initial-cost discrepancy {metrics['maximum_initial_cost_error']:.3g}. Native solver work: {metrics['native_seconds']:.3f}s. Candidate extra stops across 63 runs: {metrics['candidate_extra_stops']:g}; repair disabled it on {metrics['candidate_disabled_runs']} runs.",'',
      'All timings are native solve times on host2237c6528e79, RTX2000 Ada, with locally serialized GPU runs. Input generation, loading/export and independent CPU audits are outside target time. A hit requires an actual TARGET event within 4s and an audited endpoint no greater than the fixed target. Arms are interleaved, with three timing repeats per identical input. No diagnostic GPU probes or learning logs were enabled.','',
      '[Registered protocol](cg_value_noise_protocol.md). Input builder/runner: `bench/cg_value_noise.py`; reporter: `bench/report_cg_value_noise.py`. Exact inputs, manifests, logs, traces and endpoint states: `/tmp/prism-cg-value-noise/`. Compact durable source/binary/trace package: `/workspace/prism-cg-value-noise-evidence.tar.xz`; raw inputs/endpoints remain under /tmp. Input seeds, amplitudes, original hashes and generator source permit reconstruction of the perturbations.']
    text='\n'.join(lines)+'\n'
    (ROOT/'RESULTS.md').write_text(text);(REPO/'docs/cg_value_noise_results.md').write_text(text)
    print(json.dumps(metrics,indent=2))
if __name__=='__main__':main()
