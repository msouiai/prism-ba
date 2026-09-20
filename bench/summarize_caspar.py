#!/usr/bin/env python3
"""Report every fixed arm, endpoint range, and matched-cost crossing."""
import argparse,json,math,pathlib,statistics,re

def main():
    ap=argparse.ArgumentParser();ap.add_argument('results',type=pathlib.Path)
    ap.add_argument('--output',type=pathlib.Path,required=True);a=ap.parse_args()
    manifest=json.loads((a.results/'preregistered.json').read_text())
    rows=[]
    for p in a.results.glob('*-caspar*.json'):
        r=json.loads(p.read_text())
        checked=re.search(r'CHECK final_score=(\S+)',p.with_suffix('.log').read_text())
        if checked is None:raise RuntimeError(f'Missing returned-state check: {p}')
        r['independent_score_final']=float(checked[1])
        r['score_final_relerr']=abs(r['independent_score_final']-r['cost'])/max(1,abs(r['cost']))
        if not r['score_final_relerr']<1e-6:raise RuntimeError(f'Final objective mismatch: {p}')
        costs=[r['score_init']]+[t['cost'] for t in r['trace']]
        if not all(b<=v for v,b in zip(costs,costs[1:])):raise RuntimeError(f'Nonmonotone retained score: {p}')
        rows.append(r)
    for folder in manifest['prism_controls'].values():
        for p in pathlib.Path(folder).glob('*.json'):
            r=json.loads(p.read_text())
            if isinstance(r,dict) and 'rep' in r:
                r['arm']={'reference':'prism-reference','optimized':'prism-guarded'}[r['arm']]
                rows.append(r)
    names=['prism-reference','prism-guarded','caspar200','caspar2000']
    def interval(rr,key):
        vv=[r[key] for r in rr]
        return f'{statistics.median(vv):,.3f} [{min(vv):,.3f}, {max(vv):,.3f}]'
    lines=['# Prism versus COLMAP Caspar: controlled fp64 comparison','',
        'All costs are `0.5 sum ||residual||²`, SIMPLE_RADIAL with fixed principal point and k2=0. Lower is better.',
        'Every completed repeat is retained. N=3 per cell; ranges are observed ranges, not confidence or tail bounds.',
        'Prism uses fixed Config A with cache, batched scoring, and diagonal-norm optimizations. The guarded arm adds `OCA_MENU_BACKTRACK=8`.',
        'Prism budgets are 600 accepted outer iterations on Venice/Ladybug/final-3068 and **60 only on final-4585**.',
        'Caspar uses COLMAP defaults with separate 200 and 2,000 iteration caps. Iteration counts are not equivalent work across algorithms.',
        'Caspar is COLMAP’s vendored backend, run through a standalone BAL adapter; this is not a full COLMAP reconstruction pipeline benchmark.',
        f"COLMAP commit: `{manifest['colmap_commit']}`. Default COLMAP precision is fp32; this experiment explicitly builds its f64 backend.",
        'Prism controls come from the completed retry study and were collected before Caspar, not interleaved with it. All use the same GPU and data hashes.',
        'Solver wall time excludes file parsing and initial problem upload. Caspar graph setup is reported separately; Prism’s solver timer includes its internal workspace preparation. Crossings below also report Caspar with graph setup charged to avoid overstating its speed.',
        '', '| Scene | Arm | N | Final cost median [range] | Solver seconds median [range] | Iterations |',
        '|---|---|---:|---:|---:|---|']
    groups={}
    for scene in manifest['scenes']:
        for name in names:
            rr=sorted([r for r in rows if r['scene']==scene and r['arm']==name],key=lambda r:r['rep'])
            groups[scene,name]=rr
            if len(rr)!=3:raise RuntimeError(f'Incomplete {scene} {name}: {len(rr)}')
            assert all(r['data_sha256']==manifest['data_sha256'][scene] for r in rr)
            lines.append(f"| {scene} | {name} | {len(rr)} | {interval(rr,'cost')} | {interval(rr,'seconds')} | {', '.join(str(r['iters']) for r in rr)} |")
    lines+=['','## Endpoint quality versus Caspar 2,000','',
        'A quality difference is called resolved only when the median gap exceeds 0.15% and the observed ranges are disjoint. Negative changes favor Prism.',
        '', '| Scene | Prism arm | Median cost change | Quality comparison |', '|---|---|---:|---|']
    for scene in manifest['scenes']:
        cc=[r['cost'] for r in groups[scene,'caspar2000']]
        for arm in names[:2]:
            pp=[r['cost'] for r in groups[scene,arm]]
            delta=100*(statistics.median(pp)/statistics.median(cc)-1)
            disjoint=max(pp)<min(cc) or max(cc)<min(pp)
            verdict='resolved' if abs(delta)>.15 and disjoint else 'not resolved'
            lines.append(f'| {scene} | {arm} | {delta:+.4f}% | {verdict} |')
    lines+=['','## Time to common objective','',
        'Targets are each fixed arm’s median endpoint, chosen mechanically after all repeats. Each cell lists all three replicates.',
        '`—` means the target was not reached within that run’s budget; it is not an extrapolation.',
        'Times are conservative solver-wall upper bounds: all untraced solver overhead is charged before the crossing. Values in parentheses additionally charge Caspar graph setup. No tolerance is added to the target cost.',
        '', '| Scene | Target arm / cost | Measured arm | Crossing seconds, reps 1 / 2 / 3 |',
        '|---|---|---|---|']
    for scene in manifest['scenes']:
        for target_arm in ['prism-reference','prism-guarded','caspar2000']:
            target=statistics.median(r['cost'] for r in groups[scene,target_arm])
            for arm in names:
                times=[]
                for r in groups[scene,arm]:
                    trace=r['trace'];overhead=max(0,r['seconds']-float(trace[-1]['wall_s']))
                    hit=next((float(t['wall_s'])+overhead for t in trace if float(t['cost'])<=target),None)
                    def bound(t):return f'≤{math.ceil((t+.000101)*1000)/1000:.3f}'
                    times.append('—' if hit is None else bound(hit)+(f" ({bound(hit+r['setup_seconds'])})" if 'setup_seconds' in r else ''))
                lines.append(f"| {scene} | {target_arm} / {target:,.6f} | {arm} | {' / '.join(times)} |")
    lines+=['','## Validation and stopping','',
        '| Scene | Caspar budget | Exit codes, reps 1 / 2 / 3 | Graph setup seconds median [range] | Max initial relative error | Max final relative error |',
        '|---|---:|---|---:|---:|---:|']
    for scene in manifest['scenes']:
        for arm in names[2:]:
            rr=groups[scene,arm]
            lines.append(f"| {scene} | {rr[0]['budget']} | {' / '.join(str(r['exit_reason']) for r in rr)} | {interval(rr,'setup_seconds')} | {max(r['score_init_relerr'] for r in rr):.3g} | {max(r['score_final_relerr'] for r in rr):.3g} |")
    lines+=['','Exit 0 = iteration cap; 1 = absolute score threshold; 2 = damping exceeded threshold. A damping exit is not a proof of convergence.',
        'Initial costs are checked independently with NumPy at relative tolerance 1e-6; final Caspar costs are checked from returned poses/intrinsics/points by a separate CPU projection loop at the same tolerance.',
        'Logging-only instrumentation populates upstream’s unassigned `initial_score` result field. Acceptance is inferred from cost decreases because this revision never updates its `step_accepted` logging field. Solver decisions are unchanged.',
        '',f"Raw Caspar logs, per-run JSON and manifest: `{a.results}`. Prism source directories are recorded in the manifest.", '']
    a.output.write_text('\n'.join(lines))
    (a.results/'combined-results.json').write_text(json.dumps(rows,indent=2)+'\n')
if __name__=='__main__':main()
