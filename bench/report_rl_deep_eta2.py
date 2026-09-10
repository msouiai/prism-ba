"""Report the frozen deep-CG retry, including misses and control failures."""
import json,math,pathlib,statistics as st
ROOT=pathlib.Path('/tmp/prism-rl-deep-eta2');REPO=pathlib.Path(__file__).parents[1]
def read(n):return json.loads((ROOT/n).read_text())
def mr(v):return f'{st.median(v):.4f} [{min(v):.4f}, {max(v):.4f}]'
def summarize(rows):
    out={}
    for scene in dict.fromkeys(r['scene'] for r in rows):
        out[scene]={}
        for arm in dict.fromkeys(r['arm'] for r in rows if r['scene']==scene):
            rs=[r for r in rows if r['scene']==scene and r['arm']==arm];assert len(rs)==3
            out[scene][arm]=dict(hits=sum(r['hit'] for r in rs),
                time=st.median(r['target_seconds'] for r in rs) if all(r['hit'] for r in rs) else None,
                gap_percent=100*(st.median(r['audit_cost'] for r in rs)/rs[0]['target']-1),
                cost=st.median(r['audit_cost'] for r in rs),
                outers=st.median(r['outers'] for r in rs),rejects=st.median(r['rejects'] for r in rs),
                matvecs=st.median(r['matvecs'] for r in rs))
        base=out[scene]['champion']['time']
        for a,v in out[scene].items():v['speedup']=base/v['time'] if base and v['time'] else None
    return out
def table(rows):
    lines=['| Scene | Arm | Hits | Target seconds median [min,max] | Audited cost | Gap to target | Outers | Rejects | Matvecs |',
           '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for scene in dict.fromkeys(r['scene'] for r in rows):
        for arm in ['champion','learned','shallow-learned','opening-decay']:
            rr=[r for r in rows if r['scene']==scene and r['arm']==arm]
            if not rr:continue
            hits=[r['target_seconds'] for r in rr if r['hit']]
            tm=mr(hits)+(' (hits only)' if len(hits)<3 else '') if hits else 'MISS; solve '+mr([r['seconds'] for r in rr])
            cost=st.median(r['audit_cost'] for r in rr);gap=100*(cost/rr[0]['target']-1)
            work=[st.median(r[k] for r in rr) for k in ['outers','rejects','matvecs']]
            lines.append(f'| {scene} | {arm} | {len(hits)}/3 | {tm} | {cost:.6f} | {gap:+.4f}% | {work[0]:g} | {work[1]:g} | {work[2]:g} |')
    return lines
def main():
    assert read('completion.json')['complete']
    transfer=read('transfer-rows.json');family=read('family-rows.json')
    assert len(transfer)==36 and len(family)==27
    analysis=read('analysis.json');diag=read('diagnostic.json');cells=analysis['cells']
    assert not any(c['scene'] in ['muell-gba146','final-1936','trafalgar-126'] for c in cells)
    ts=summarize(transfer);fs=summarize(family)
    ratios=[v['learned']['speedup'] for v in ts.values()]
    allhit=all(x is not None for x in ratios)
    median=st.median(ratios) if allhit else None
    geo=math.exp(st.mean(math.log(x) for x in ratios)) if allhit else None
    panel_gate=allhit and median>=1.1 and min(ratios)>=1/1.05
    audits=[read(str(p.relative_to(ROOT))) for p in (ROOT/'runs').glob('*/result.json')]
    valid=[r for r in audits if 'audit_error' in r]
    summary=dict(transfer=ts,family=fs,panel_gate=panel_gate,median_speedup=median,geometric_speedup=geo,
        audits=len(valid),max_audit_error=max(r['audit_error'] for r in valid),native_seconds=read('completion.json')['native_seconds'],
        deep_states=analysis['deep_states'],training_states=len(cells),family_advantages=analysis['family_advantages'],
        diagnostics={a:{k:v for k,v in d.items() if k!='decisions'} for a,d in diag.items()})
    (ROOT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    lines=['# Deep-CG learned damping versus sustained eta2','',
        ('The learned policy passes the registered transfer timing gate; inspect the family and opening-decay controls below before a general claim.' if panel_gate else
         '**Retain the sustained-eta2 champion. The learned policy fails the registered transfer promotion gate.**'),'',
        'This retries the original rollout-trained linear damping policy with actual deep-CG states and up to 32-outer returns. Every arm uses the current champion: initial lambda 0.1 and sustained eta multiplier 2, capped at 0.5. The fixed comparator applies one extra decade of opening decay at boundaries 1 and 2. The shallow-only model uses the same long returns and ridge recipe, excluding the added deep-source scenes.','',
        'Muell-gba146, Final1936 and Trafalgar126 supply no training states, normalization, labels or model selection. Their earlier results are known, so this is a held-out retry on a research panel, not a claim of pristine unseen evaluation. Models were frozen before the family and transfer solves.','',
        '## Fixed-target transfer','',
        'N3, same binary and host2237c6528e79 / RTX2000 Ada, rotating serialized arm order. Native time includes inference and solver setup; loading, state export and CPU audits are excluded. Detailed logging is off. Targets/caps: Traf126 105579.58394455544 / 4s; Final1936 5125687.352261469 / 8s; Muell 1946488.746262194 / 12s. Half-sum original squared pixel residuals, SIMPLE_RADIAL with k2 fixed zero.','']
    lines+=table(transfer)
    lines+=['','Endpoint/work columns use all repeats, including misses. A miss has no fabricated finite crossing time. Small endpoint gaps are reported explicitly; endpoints already below target receive no extra quality reward.','',
        '| Scene | Learned / champion speedup | Shallow-only / champion speedup | Opening-decay / champion speedup |','|---|---:|---:|---:|']
    for scene,arms in ts.items():
        vals=[f"{arms[a]['speedup']:.4f}x" if arms[a]['speedup'] is not None else 'Withheld: miss' for a in ['learned','shallow-learned','opening-decay']]
        lines.append('| '+scene+' | '+' | '.join(vals)+' |')
    lines+=['',f'All-scene median/geometric learned speedups: {median:.4f}x / {geo:.4f}x.' if allhit else 'All-scene finite speedups are withheld because at least one learned or champion case misses.',
        'The registered gate requires every learned repeat to hit, median scene speedup >=1.10 against sustained eta2, and no scene >5% slower. Passing that gate would still require explaining the family checks and whether learning beats opening-decay.','',
        '### What changed','',
        'All 36 transfer runs hit their fixed targets. The learned model wins Trafalgar at1.249x, but takes83.4% longer on Final1936 and3.8% longer on Muell. Muell\'s small slowdown is not the decisive objection; Final1936 is a large same-target speed regression. Median scene speedup0.963x also misses the1.10x requirement.','',
        'Adding the deep-source data improves the Muell median only slightly against the matched shallow-only32-outer model (4.405s versus4.438s), while worsening Final1936 (0.928s versus0.673s). This does not confirm that the original coverage gap was the sole cause or that it is now fixed. The opening schedule loses to the champion on all three transfer scenes, so it also earns no promotion under sustained eta2.','',
        '## Training coverage and return horizon','',
        f"{len(cells)} saved training states, {analysis['deep_states']} with actual previous CG depth >=64/128. Three actions times N3 yields {len(cells)*9} branch continuations. Every branch restored the exact saved feature history before its action. Up to 32 outers, cap6s; actual continuation lengths range {min(min(c['lengths']) for c in cells)}–{max(max(c['lengths']) for c in cells)}. No Muell checkpoints.",'',
        '| Training scene | Boundary | Previous CG | Common long horizon s | Long best action | Four-outer best action |',
        '|---|---:|---:|---:|---:|---:|']
    for c in cells:
        short=min([0,-1,1],key=lambda a:c['short_auc'][str(a)])
        lines.append(f"| {c['scene']} | {c['k']} | {c['features'][7]*128:g} | {c['horizon']:.4f} | {c['best']:+d} | {short:+d} |")
    lines+=['','The reward integrates the causal accepted-cost curve over the shortest measured elapsed horizon among all nine branches at a checkpoint. Costs are normalized by the checkpoint cost. Four-outer prefixes are rescored from the same traces, not extra runs. Hindsight best actions are descriptive. Late states with very little remaining cost reduction can have tiny AUC labels despite large runtime differences.','',
        '## Whole-family exclusion','',
        'Each fit excludes all sizes of the omitted family, including normalization. Models use fixed ridge10 / intercept0.01 with no parameter search. Positive offline AUC advantage favors learning. Full-solve family checks use the corresponding excluded-family policy and cannot select the transfer model.','',
        '| Omitted family | Offline normalized AUC advantage |','|---|---:|']
    for g,a in analysis['family_advantages'].items():lines.append(f'| {g} | {a:+.8f} |')
    lines+=['']+table(family)
    lines+=['','## Final1936 mechanism check','',
        'Separate logged solves, up to32 outers and8s, stop at the same target. These are mechanism diagnostics, excluded from N3 timing medians. The earlier extended policy is run unchanged as a historical pathology control, now on sustained eta2.','',
        '| Controller | Outers | Cost | Exact lambda0.025 ->0.25 corrections | Longest consecutive +1 streak |','|---|---:|---:|---:|---:|']
    for a,d in diag.items():lines.append(f"| {a} | {d['outers']} | {d['cost']:.6f} | {d['exact_pathology_count']} | {d['positive_streak']} |")
    lines+=['','The new policy makes0.025 ->0.25 at boundary1, then lets damping decay at boundaries2–3, but makes0.00025 ->0.0025 at boundaries4–7. It reaches the target in8 outers versus champion4. The older policy makes0.025 ->0.25 at all31 observed boundaries and remains above target at outer32. Thus the runaway high-damping behavior is reduced, while repeated decay cancellation survives at a smaller scale.','',
        'All decision histories, including proposed and used lambda, are in `diagnostic.json`. A missing exact numerical signature does not by itself show useful convergence; the transfer table is decisive.','',
        '## Interpretation limits','',
        'Adding actual deep-CG states and using longer returns tests whether those changes are sufficient for this learned-policy recipe. It does not isolate all possible causes of a failure: labels still measure one intervention followed by champion continuation, whereas deployment repeats learned interventions. This mismatch can turn a locally useful damping increase into persistent regularization. The matched shallow-only model helps assess the contribution of the additional deep-source data; it does not make the finite, correlated panel a population study.','',
        'A negative outcome establishes a reproducible counterexample for this controller and protocol. It does not establish that all learned damping or state-dependent controllers lose to constants. No new RL or novelty claim follows.','',
        'The fold-specific policy does win Dubrovnik356 at1.165x. Ladybug and Venice fold policies miss their fixed targets, but the endpoint gaps are only0.593% and0.193%; these are not catastrophic quality failures. Final1936 supplies a clear speed counterexample independently of those near-target classifications.','',
        '## Verification and evidence','',
        f"{len(valid)} independently audited FP64 endpoints; maximum relative discrepancy {summary['max_audit_error']:.3g}. Native solver total {summary['native_seconds']:.3f}s. One deliberately mismatched-eta replay is expected to fail. All fitted policies pass C++/Python inference parity on every saved training feature vector.",'',
        'The only solver-source change adds the fixed forcing flag to the replay fingerprint. N3 parent/new/zero checks pass. Exact restored history and first-four-step continuation parity pass. The initial overly strict32-step field parity failed near stationarity; repeated uninterrupted runs also vary in late CG work. The pre-label amendment retains the1e-7 endpoint tolerance, requires restored work inside continuous repeat spread, and preserves all original failed evidence.','',
        '[Registered protocol and validation amendment](rl_deep_eta2_protocol.md). Driver `bench/rl_deep_eta2.py`; isolated builder `bench/build_rl_deep_eta2.py`; reporter `bench/report_rl_deep_eta2.py`. Raw artifacts `/tmp/prism-rl-deep-eta2/`; durable compact archive `/workspace/prism-rl-deep-eta2-evidence.tar.xz`. No production defaults changed and no fresh Caspar comparison.','',
        'The plotted CSV iteration clock starts after some local setup and is slightly shorter than the native TARGET clock used for every table. Curves are causal recorded steps; no interpolated target crossings are used.','',
        '![Transfer convergence](figures/convergence/rl_deep_eta2_transfer.png)']
    text='\n'.join(lines)+'\n';(ROOT/'RESULTS.md').write_text(text);(REPO/'docs/rl_deep_eta2_results.md').write_text(text)
    plot(transfer)
    print(json.dumps(summary,indent=2),flush=True)
def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    colors={'champion':'#2864b4','learned':'#d97420','shallow-learned':'#8b62b1','opening-decay':'#268558'}
    fig,axes=plt.subplots(1,3,figsize=(14,4.2),constrained_layout=True)
    for ax,scene in zip(axes,dict.fromkeys(r['scene'] for r in rows)):
        for r in [r for r in rows if r['scene']==scene]:
            trace=read('runs/'+r['name']+'/result.json')['trace']
            ax.step([x['wall_s'] for x in trace],[x['cost']/r['target'] for x in trace],where='post',
                    color=colors[r['arm']],alpha=.55,lw=1.3)
        ax.axhline(1,color='black',ls='--',lw=1);ax.set_title(scene);ax.set_yscale('log')
        ax.set_xlabel('Native iteration-trace seconds');ax.set_ylabel('Cost / fixed target');ax.grid(alpha=.2)
    fig.suptitle('Deep-CG retry: current eta2 champion and damping controls (N=3)')
    fig.legend(handles=[Line2D([0],[0],color=c,label=a) for a,c in colors.items()],loc='outside lower center',ncol=4)
    dest=REPO/'docs/figures/convergence';dest.mkdir(exist_ok=True,parents=True)
    for ext in ['png','pdf']:fig.savefig(dest/('rl_deep_eta2_transfer.'+ext),dpi=160)
    plt.close(fig)
if __name__=='__main__':main()
