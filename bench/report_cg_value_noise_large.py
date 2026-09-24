#!/usr/bin/env python3
"""Final13682 fixed-target noise results and convergence curves."""
import json,math,pathlib,statistics as st
ROOT=pathlib.Path('/tmp/prism-cg-value-noise-large')
REPO=pathlib.Path(__file__).parents[1]
def read(n):return json.loads((ROOT/n).read_text())
def mr(values,digits=4):
    return f'{st.median(values):.{digits}f} [{min(values):.{digits}f}, {max(values):.{digits}f}]'
def main():
    assert read('completion.json')['complete']
    rows=read('rows.json');cases=read('cases.json');assert len(rows)==24 and len(cases)==4
    pairs=[]
    for c in cases:
        arms={a:[r for r in rows if r['key']==c['key'] and r['arm']==a] for a in ['champion','conservative']}
        assert all(len(rr)==3 for rr in arms.values())
        ratio=None
        if all(r['hit'] for rr in arms.values() for r in rr):
            ratio=st.median(r['target_seconds'] for r in arms['champion'])/st.median(r['target_seconds'] for r in arms['conservative'])
        pairs.append(dict(key=c['key'],seed=c['seed'],speedup=ratio,
            hits={a:sum(r['hit'] for r in rr) for a,rr in arms.items()}))
    good=[p['speedup'] for p in pairs if p['speedup'] is not None]
    metrics=dict(runs=24,native_seconds=sum(r['seconds'] for r in rows),
        hits={a:sum(r['hit'] for r in rows if r['arm']==a) for a in ['champion','conservative']},
        maximum_endpoint_audit_error=max(r['audit_error'] for r in rows),
        maximum_initial_cost_error=max(r['initial_error'] for r in rows),
        all_case_geometric_speedup=math.exp(st.mean(map(math.log,good))) if len(good)==4 else None,
        complete_pairs=len(good),candidate_extra_stops=sum(r['value_summary'].get('stops',0) for r in rows),
        candidate_disabled_runs=sum(r['value_summary'].get('disabled',0)>0 for r in rows))
    (ROOT/'summary.json').write_text(json.dumps(dict(metrics=metrics,pairs=pairs),indent=2)+'\n')
    lines=['# Final-13682: calibrated initialization stress','',
      '13,682 cameras, 4,456,117 points, 28,987,644 observations. The user requested this largest-scene extension after the small-scene stress test; it does not override those counterexamples or automatically promote a solver.','',
      f"Completed 24 runs. Fixed-target hits: champion {metrics['hits']['champion']}/12; conservative CG-value rule {metrics['hits']['conservative']}/12. Both arms hit all repeats on {len(good)}/4 inputs.",'',
      ('Geometric speedup over the four matched inputs: '+f"{metrics['all_case_geometric_speedup']:.4f}x." if metrics['all_case_geometric_speedup'] is not None else
       'An all-input geometric speedup is withheld because at least one case has a target miss.'),'',
      'Both arms use the same frozen binary, lambda 0.1 and sustained eta multiplier 2. Candidate adds OCA_CGV=3. No Caspar or pixel-observation-noise runs. All input observation bytes and initial intrinsic values were preserved; the objective and fixed target 27,591,576.557625167 remain the same. SIMPLE_RADIAL, k2 fixed zero, half sum of squared original pixel residuals.','',
      '## Input calibration','',
      'Clean input plus three seeded perturbations (17,29,43), each calibrated to 1.10x initial full reprojection RMS, or 1.21x initial cost. Additive angle-axis coordinate noise, camera-center and point-coordinate noise; translations reconstructed as t=-R*C. Calibration uses all observations in chunks, before any solver run. It is not isotropic SO(3) noise.','',
      'Full-RMS matching controls starting cost, not uniform pose displacement, conditioning or attraction basin. Here the median projected displacement is only about 2–3 micro-pixels, despite maximum displacements of 237–289 pixels. A few extreme observations dominate this calibration. This is a cost-sensitivity test, not evidence of recovery from broadly displaced poses. No seed was resampled based on solver outcomes.','',
      '| Input | Initial cost | RMS ratio | Amplitude | Projection displacement px: median / p95 / max | Depth-sign changes |',
      '|---|---:|---:|---:|---:|---:|']
    for c in cases:
        v=c.get('projection_displacement_px',[0,0,0])
        lines.append(f"| {c['key']} | {c['initial_cost']:.6f} | {c['rms_ratio']:.7f} | {c['amplitude']:.7g} | {v[0]:.6g} / {v[1]:.6g} / {v[2]:.6g} | {c.get('depth_sign_changes',0)} |")
    lines+=['','## Paired results','',
      'N3 timing repeats for each identical input/arm. Seeds are separate initializations, not timing repeats or independent scenes. Each run has 20 native seconds and 600 outers. Target hits require an actual TARGET event within the cap and an independently audited endpoint <=target. No interpolated crossing times.','',
      '| Input | Arm | Hits | Target seconds median [min,max] | Final audited cost | Gap to target | Outers | Rejects | Matvecs | Extra stops |',
      '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for c in cases:
        for a in ['champion','conservative']:
            rr=[r for r in rows if r['key']==c['key'] and r['arm']==a]
            ts=[r['target_seconds'] for r in rr if r['hit']];tm=mr(ts) if ts else 'MISS'
            if ts and len(ts)<3:tm+=' (hits only)'
            cost=st.median(r['audit_cost'] for r in rr)
            work=[st.median(r[k] for r in rr) for k in ['outers','rejects','matvecs']]
            stops=st.median(r['value_summary'].get('stops',0) for r in rr)
            lines.append(f"| {c['key']} | {a} | {len(ts)}/3 | {tm} | {cost:.6f} | {100*(cost/c['target']-1):+.4f}% | {work[0]:g} | {work[1]:g} | {work[2]:g} | {stops:g} |")
    lines+=['','Endpoint and work columns summarize all three runs, including misses; hit-only times are marked.','',
      '| Input | Speedup (champion time / candidate time) |','|---|---:|']
    for pair in pairs:lines.append(f"| {pair['key']} | "+(f"{pair['speedup']:.4f}x" if pair['speedup'] is not None else 'Withheld: miss')+' |')
    if metrics['candidate_extra_stops']==0:
        lines+=['','## Interpretation','',
          'The sustained-eta2 champion remains the selected configuration. The candidate made zero additional CG stops across all 12 runs, so these timings provide no evidence of a convergence improvement from marginal-value stopping. Tiny timing differences cannot establish a controller benefit when it never changes a stopping decision.','',
          'The existing solves are shallow at this target. The new rule requires two consecutive eligible three-increment windows, so it cannot stop before CG depth four; it also requires a residual between the incumbent tolerance and 0.5 and a sufficiently low marginal model-gain rate. Aggregate logs show zero proposals, but do not identify which condition prevented each proposal. This experiment does not isolate a single blocking condition.','',
          'These are four initializations of one scene, not four independent large scenes. The prior small-scene counterexamples still prevent promotion. A useful subsequent stress test would pre-register distributed image-displacement or pose-noise scales and a stricter fixed quality target; increasing problem size alone did not exercise this controller.']
    lines+=['','## Convergence curves','',
      'All three repeats are drawn per arm and mostly overlap. Curves show recorded outer-iteration costs as steps; the horizontal line is the fixed target. The CSV timer starts after some solver setup, so its time axis is slightly shorter than the TARGET timer used in the table. Crossings are scored from native TARGET events, not from interpolation of the plot.','',
      '![Final13682 initialization stress](figures/convergence/final13682_cg_value_noise.png)','',
      '## Verification and evidence','',
      f"All 24 original-observation CPU FP64 endpoint audits passed, maximum relative discrepancy {metrics['maximum_endpoint_audit_error']:.3g}; maximum native/calibrated initial-cost discrepancy {metrics['maximum_initial_cost_error']:.3g}. Native solver work: {metrics['native_seconds']:.3f}s. Candidate extra stops: {metrics['candidate_extra_stops']:g}; numerical repair disabled the controller in {metrics['candidate_disabled_runs']} runs.",'',
      'Same host2237c6528e79 and RTX2000 Ada, serialized GPU runs and alternating arm order. Input preparation, loading/export and independent CPU audits are outside native target time. Solver defaults unchanged. Existing small-scene counterexamples still apply regardless of this one scene\'s outcome.','',
      '[Protocol](cg_value_noise_large_protocol.md). Driver: `bench/cg_value_noise_large.py`; reporter: `bench/report_cg_value_noise_large.py`. Exact input files, states, manifests, logs and traces: `/tmp/prism-cg-value-noise-large/`. Compact durable package: `/workspace/prism-cg-value-noise-large-evidence.tar.xz`; raw inputs and endpoint states remain under /tmp.']
    text='\n'.join(lines)+'\n';(ROOT/'RESULTS.md').write_text(text);(REPO/'docs/cg_value_noise_large_results.md').write_text(text)
    plot(rows,cases)
    print(json.dumps(dict(metrics=metrics,pairs=pairs),indent=2))
def plot(rows,cases):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    fig,axes=plt.subplots(2,2,figsize=(11,7),constrained_layout=True,sharey=True)
    colors={'champion':'#2864b4','conservative':'#d97420'}
    for ax,c in zip(axes.flat,cases):
        for r in [r for r in rows if r['key']==c['key']]:
            trace=read('runs/'+r['name']+'/result.json')['trace']
            ax.step([x['wall_s'] for x in trace],[x['cost']/c['target'] for x in trace],where='post',color=colors[r['arm']],alpha=.65,lw=1.4)
        ax.axhline(1,color='black',ls='--',lw=1)
        ax.set_title('Clean' if c['seed'] is None else f"Mild noise, seed {c['seed']}")
        ax.set_xlabel('Native iteration-trace seconds');ax.set_ylabel('Cost / fixed target');ax.set_yscale('log');ax.grid(alpha=.2)
    fig.suptitle('Final-13682: champion vs conservative CG-value stopping (N=3)')
    fig.legend(handles=[Line2D([0],[0],color=colors['champion'],label='Champion'),Line2D([0],[0],color=colors['conservative'],label='Conservative CG rule')],loc='outside lower center',ncol=2)
    dest=REPO/'docs/figures/convergence';dest.mkdir(exist_ok=True,parents=True)
    for suffix in ['png','pdf']:fig.savefig(dest/f'final13682_cg_value_noise.{suffix}',dpi=170)
    plt.close(fig)
if __name__=='__main__':main()
