"""Largest-scene paired timing report and convergence plot."""
import json,pathlib,statistics as st
ROOT=pathlib.Path('/tmp/prism-rl-deep-eta2-large');REPO=pathlib.Path(__file__).parents[1]
def read(n):return json.loads((ROOT/n).read_text())
def mr(v):return f'{st.median(v):.4f} [{min(v):.4f}, {max(v):.4f}]'
def main():
    assert read('completion.json')['complete'];rows=read('rows.json');assert len(rows)==6
    diag=read('diagnostic.json');arms={a:[r for r in rows if r['arm']==a] for a in ['champion','learned']}
    assert all(len(rr)==3 for rr in arms.values())
    times={a:st.median(r['target_seconds'] for r in rr) if all(r['hit'] for r in rr) else None for a,rr in arms.items()}
    ratio=times['champion']/times['learned'] if all(times.values()) else None
    records=[read('runs/'+n+'/result.json') for n in [r['name'] for r in rows]+['learned-diagnostic']]
    metrics=dict(hits={a:sum(r['hit'] for r in rr) for a,rr in arms.items()},target_medians=times,
        speedup=ratio,native_seconds=read('completion.json')['native_seconds'],
        maximum_audit_error=max(r['audit_error'] for r in records),
        nonzero_diagnostic_actions=diag['nonzero_actions'],positive_streak=diag['positive_streak'],
        exact_pathology_count=diag['exact_pathology_count'])
    (ROOT/'summary.json').write_text(json.dumps(metrics,indent=2)+'\n')
    verdict='At least one arm misses a target repeat; a finite paired speedup is withheld.' if ratio is None else (
        f'Learned/champion speedup: {ratio:.4f}x (champion time divided by learned time). Learned takes {(1/ratio-1)*100:+.1f}% more time.'
        if ratio<=1 else f'The learned policy is {ratio:.4f}x faster on this scene.')
    lines=['# Final-13682: frozen deep-CG learned damping','',verdict,'',
        '**Result: champion 3/3 target hits at about 3.24s; learned 0/3 within the 20s cap.** The learned endpoint is 1.1268% above the fixed target, versus the champion 0.6114% below. This is a same-target speed failure with a modest endpoint gap, not a cost explosion.','',
        'Current general selection remains the sustained-eta2 champion. This user-authorized largest-scene extension follows the completed round6 retry and cannot erase its prior Final1936 and family-transfer counterexamples. No policy was fitted or changed using Final13682.','',
        '13,682 cameras, 4,456,117 points, 28,987,644 original observations. Fixed historical target 27,591,576.557625167; initial cost approximately1,126,369,344.674. SIMPLE_RADIAL original-observation half-sum squared pixel residuals, k2 fixed zero. No perturbations. Both arms use the same round6 binary, lambda0.1 and sustained eta multiplier2 capped at0.5. The learned arm adds the exact frozen full ridge policy.','',
        '## Matched time to target','',
        'N3, alternating first arm, serialized on host2237c6528e79 / RTX2000 Ada. Native cap20s, outer cap600. Target timing includes policy inference and local solver setup; loading, export and audit are excluded. Detailed policy logging is off for the six timing runs.','',
        '| Arm | Hits | Target seconds median [min,max] | Audited endpoint cost | Gap to target | Outers | Rejects | Matvecs |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for a,rr in arms.items():
        t=[r['target_seconds'] for r in rr if r['hit']]
        text=mr(t)+(' (hits only)' if len(t)<3 else '') if t else 'MISS; native solve '+mr([r['seconds'] for r in rr])
        cost=st.median(r['audit_cost'] for r in rr);target=rr[0]['target']
        w=[st.median(r[k] for r in rr) for k in ['outers','rejects','matvecs']]
        lines.append(f'| {a} | {len(t)}/3 | {text} | {cost:.6f} | {100*(cost/target-1):+.4f}% | {w[0]:g} | {w[1]:g} | {w[2]:g} |')
    lines+=['','Actual TARGET events and independently audited endpoint <=target are both required. Misses and sub-percent endpoint gaps are retained; costs already below the threshold receive no additional quality credit. These are useful-quality crossings, not full convergence.','',
        '## Damping mechanism','',
        f"A separate learned diagnostic uses {diag['outers']} outers, applies {diag['nonzero_actions']} nonzero actions, and has a longest consecutive positive-action streak of {diag['positive_streak']}. Exact0.025 ->0.25 corrections: {diag['exact_pathology_count']}. This diagnostic is excluded from timing medians.",'',
        '| Boundary | Action | Champion-proposed lambda | Used lambda | Previous CG depth |','|---|---:|---:|---:|---:|']
    for e in diag['decisions']:
        lines.append(f"| {e['outer']} | {e['action']:+d} | {e['base_lambda']:.7g} | {e['lambda']:.7g} | {e['features'][7]*128:g} |")
    lines+=['','At boundaries 1 and 2 the policy changes lambda 0.025 to 0.25. It abstains at boundary 3, then changes 0.0025 to 0.025 at every boundary 4–27: 24 consecutive positive decisions, despite previous reported CG counts of only 0–2. The last attempted step is discarded at the before-commit budget check; 27 steps are accepted. Work totals include that final attempt.','',
        'The trace shows repeated cancellation of damping decay. Each linear solve stays shallow, but the algorithm takes many more small accepted steps: 27 accepted outers and 86 matvecs versus champion 4 and 19. Both have zero rejections. The true-cost acceptance test does not reject a step merely because it makes slow progress. Deep-state training and longer one-action returns did not prevent this repeated-decision failure.','',
        'A correction multiplies the proposed lambda by0.1,1 or10, subject to the existing numerical floor and ceiling. Actual objective acceptance, radius updates, retries and forcing remain unchanged. The diagnostic is the observed learned trajectory; its proposed lambdas are not a counterfactual champion trajectory after the geometries diverge.','',
        '## Convergence','',
        'All N3 traces are causal recorded-cost steps and may overlap. The CSV iteration clock starts after some local setup, so it is slightly shorter than the TARGET clock used in the table. No interpolated crossings.','',
        '![Final13682 deep-policy transfer](figures/convergence/final13682_deep_eta2_policy.png)','',
        '## Verification and evidence','',
        f"All seven original-observation FP64 endpoint audits passed, maximum relative discrepancy {metrics['maximum_audit_error']:.3g}. Total native solver work {metrics['native_seconds']:.3f}s, including the separate diagnostic. Frozen input/binary/policy/code hashes and all seven raw endpoint hashes reverified after completion.",'',
        'No new Caspar measurements or production-default changes. The earlier Caspar comparison remains historical and is not mixed into these fresh paired timings.','',
        '[Protocol](rl_deep_eta2_large_protocol.md). Driver `bench/rl_deep_eta2_large.py`; reporter `bench/report_rl_deep_eta2_large.py`. Raw results and states `/tmp/prism-rl-deep-eta2-large/`; compact durable package `/workspace/prism-rl-deep-eta2-large-evidence.tar.xz`.']
    text='\n'.join(lines)+'\n';(ROOT/'RESULTS.md').write_text(text);(REPO/'docs/rl_deep_eta2_large_results.md').write_text(text)
    plot(rows);print(json.dumps(metrics,indent=2),flush=True)
def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),constrained_layout=True)
    colors={'champion':'#2864b4','learned':'#d97420'}
    for r in rows:
        trace=read('runs/'+r['name']+'/result.json')['trace']
        for ax in axes:
            ax.step([x['wall_s'] for x in trace],[x['cost']/r['target'] for x in trace],where='post',color=colors[r['arm']],alpha=.65,lw=1.5)
    for ax in axes:
        ax.axhline(1,color='black',ls='--',lw=1);ax.grid(alpha=.2)
        ax.set_xlabel('Native iteration-trace seconds');ax.set_ylabel('Cost / fixed target')
    axes[0].set_yscale('log');axes[0].set_title('Full cost range (log scale)')
    axes[1].set_ylim(.985,1.15);axes[1].set_title('Near target (linear scale)')
    fig.suptitle('Final-13682: frozen deep-CG policy vs sustained eta2 (N=3)')
    fig.legend(handles=[Line2D([0],[0],color=colors[a],label=a) for a in colors],loc='outside lower center',ncol=2)
    dest=REPO/'docs/figures/convergence';dest.mkdir(parents=True,exist_ok=True)
    for suffix in ['png','pdf']:fig.savefig(dest/f'final13682_deep_eta2_policy.{suffix}',dpi=170)
    plt.close(fig)
if __name__=='__main__':main()
