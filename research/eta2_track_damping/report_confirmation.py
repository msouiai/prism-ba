#!/usr/bin/env python3
"""Audit and summarize the entire fresh confirmation, without pooling the screen."""
from collections import Counter
import csv,json,statistics
from pathlib import Path
from confirm import P,Q,G,PROTOCOL,verify_build
from report import aggregate

def main():
    build=verify_build();reg=json.loads((Q/'registration.json').read_text())
    rows=json.loads((Q/'tail-results.json').read_text())+json.loads((Q/'controls-results.json').read_text())
    assert len(rows)==58 and reg['binary_sha256']==build['binary_sha256']
    assert reg['protocol_sha256']==G.sha(PROTOCOL)
    cells={x['scene']:x for x in reg['cells']};inputs={};seen=set();largest_audit=0
    for r in rows:
        folder=P/r['source'];cell=cells[r['scene']]
        assert r==json.loads((folder/'result.json').read_text())
        assert r['source'] not in seen;seen.add(r['source'])
        assert r['valid'] and r['returncode']==0 and r['audit_relative_error']<1e-6
        largest_audit=max(largest_audit,r['audit_relative_error'])
        assert r['target']==cell['target'] and r['target_stopping']==cell['target_stopping']
        m=json.loads((folder/'manifest.json').read_text())
        assert m['binary_sha256']==build['binary_sha256'] and m['protocol_sha256']==reg['protocol_sha256']
        assert m['champion_sha256']==reg['champion_sha256']
        if cell['path'] not in inputs:inputs[cell['path']]=G.sha(cell['path'])
        assert inputs[cell['path']]==cell['input_sha256']==m['input_sha256']
        for k,v in G.CHAMP['flags'].items():assert m['flags'][k]==v
        assert m['flags']['OCA_TRACK_TAU']==str(int(r['arm']=='on'))
        assert m['target']==r['solver_target']==(cell['target'] if cell['target_stopping'] else 0)
        assert ('OCA_TARGET_COST' in m['flags'])==cell['target_stopping']
        curve=list(csv.DictReader(l for l in (folder/'curve.csv').read_text().splitlines() if not l.startswith('#')))
        cross=next((float(x['wall_s']) for x in curve if float(x['cost'])<=cell['target']),None)
        hit=r['cost']<=cell['target'] and cross is not None and cross<=cell['cap']
        assert r['hit']==hit and r['target_seconds']==(cross if hit else None)
        assert r['score_init']==float(curve[0]['cost'])
        assert G.sha(folder/'endpoint.state.gz')==r['state']['compressed_sha256']
        assert r['attempts']['accepted']==r['accepts'] and r['attempts']['matvecs']==r['matvecs']
    result={}
    for scene,cell in cells.items():
        rr=[r for r in rows if r['scene']==scene]
        assert Counter(r['arm'] for r in rr)=={'off':cell['n'],'on':cell['n']}
        init=[r['score_init'] for r in rr];assert max(init)-min(init)<=1e-9*max(init)
        arms={a:aggregate([r for r in rr if r['arm']==a]) for a in ('off','on')}
        for a in arms:
            subset=[r for r in rr if r['arm']==a]
            arms[a]['stop_counts']=dict(Counter(r['stop_reason'] for r in subset))
            arms[a]['legacy_cap_marker_count']=arms[a]['caps']
            arms[a]['caps']=sum(r['stop_reason'] in ('time_cap','outer_cap') for r in subset)
            arms[a]['misses']=[dict(rep=r['rep'],cost=r['cost'],stop=r['stop_reason']) for r in subset if not r['hit']]
            arms[a]['native_range']=[min(r['native_seconds'] for r in subset),max(r['native_seconds'] for r in subset)]
        o,n=arms['off'],arms['on'];signal='misses_or_unequal_successful_subsets'
        if o['hits']==n['hits']==cell['n']:
            signal='overlap'
            if n['time_range'][1]<o['time_range'][0]:signal='faster_disjoint'
            if o['time_range'][1]<n['time_range'][0]:signal='slower_disjoint'
        result[scene]=dict(arms=arms,target=cell['target'],target_stopping=cell['target_stopping'],
            cost_delta_percent=100*(n['cost_median']/o['cost_median']-1),
            successful_median_ratio=n['time_median']/o['time_median'] if n['time_median'] and o['time_median'] else None,
            timing_signal=signal)
    o,n=result['final-3068']['arms']['off'],result['final-3068']['arms']['on']
    primary=dict(on_zero_misses=n['hits']==10,off_ftol_misses=sum(x['stop']=='ftol' for x in o['misses']),
       on_ftol_misses=sum(x['stop']=='ftol' for x in n['misses']),
       fresh_timing_ceiling=1.2*o['time_median'] if o['time_median'] is not None else None,
       historical_timing_ceiling=reg['historical']['maximum_on_median_20percent'])
    primary['within_fresh_20percent']=n['time_median'] is not None and primary['fresh_timing_ceiling'] is not None and n['time_median']<=primary['fresh_timing_ceiling']
    primary['within_historical_20percent']=n['time_median'] is not None and n['time_median']<=primary['historical_timing_ceiling']
    primary['sample_rescue_and_speed_gate']=primary['on_zero_misses'] and primary['off_ftol_misses']>0 and primary['within_fresh_20percent']
    report=dict(verified=True,scored_runs=len(rows),max_endpoint_audit_relative_error=largest_audit,
      binary_sha256=build['binary_sha256'],registration_sha256=G.sha(Q/'registration.json'),
      prior_N5_pooled=False,per_scene=result,primary=primary,historical_reference=reg['historical'])
    G.write(Q/'summary.json',report)
    lines=['# Fresh N=10 static track-damping confirmation','',
      'This is the new user-requested cohort, separate from the earlier N=5 screen: 40 tail runs and 18 control runs. Frozen derived binary off/on; full original-observation objective; all endpoints independently audited.','',
      '## Primary prediction','',
      f"Final3068 target hits: **{o['hits']}/10 off → {n['hits']}/10 on**. On-arm FTOL misses: **{primary['on_ftol_misses']}**. The requested zero-miss observation {'holds' if primary['on_zero_misses'] else 'fails'} in this cohort.",
      f"Successful-run median crossing: {o['time_median']!r}s off versus {n['time_median']!r}s on. Within fresh-control +20%: {primary['within_fresh_20percent']}; within historical +20%: {primary['within_historical_20percent']}. Fresh controls supply {primary['off_ftol_misses']} FTOL misses.",
      'The zero-miss and timing conditions are separate. A favorable successful-subset median does not compensate for target misses. These are stochastic whole-run comparisons, not replay of identical internal failure states.','',
      '## Identical-target crossings','',
      '| Scene | Off hits | On hits | Off crossing seconds | On crossing seconds | Timing signal |',
      '|---|---:|---:|---|---|---|']
    def tf(s):return '—' if s['time_median'] is None else f"{s['time_median']:.4f} [{s['time_range'][0]:.4f}, {s['time_range'][1]:.4f}]"
    for scene,x in result.items():
        a,b=x['arms']['off'],x['arms']['on']
        lines.append(f"| {scene} | {a['hits']}/{a['n']} | {b['hits']}/{b['n']} | {tf(a)} | {tf(b)} | {x['timing_signal']} |")
    lines+=['','N=10 tail cells stop at target; N=3 control cells run to ordinary termination and use the registered target only to score crossings. No cap/termination time substitutes for a missed crossing. Ranges are observed samples, not confidence intervals.',
      'The preregistration mislabeled the rounded Dubrovnik88 reference as Caspar; it was the supplied MFREE library endpoint. The frozen target 362571.82 and every measured comparison are unchanged. See [provenance correction](PROVENANCE_CORRECTION.md).','',
      '## Endpoints and total native time','',
      '| Scene | Off median cost [range] | On median cost [range] | Cost delta | Off native median | On native median |',
      '|---|---|---|---:|---:|---:|']
    for scene,x in result.items():
        a,b=x['arms']['off'],x['arms']['on']
        cf=lambda z:f"{z['cost_median']:.6f} [{z['cost_range'][0]:.6f}, {z['cost_range'][1]:.6f}]"
        lines.append(f"| {scene} | {cf(a)} | {cf(b)} | {x['cost_delta_percent']:+.3f}% | {a['native_median']:.4f}s | {b['native_median']:.4f}s |")
    lines+=['','Total native time here is time to each run\'s own termination, not equal-quality speed. Target-stopped endpoint overshoot is not automatically a quality advantage. Final4585 N=3 does not establish a basin noise floor.','',
      '## Solver counters','',
      '| Scene / arm | Outers | Rejects | PCG/outer | Retry/native | Failed/native | Numerical repairs | Stops |',
      '|---|---|---|---|---|---|---|---|']
    for scene,x in result.items():
        for a,s in x['arms'].items():
            f=lambda v:', '.join(f'{q:.3g}' for q in v)
            lines.append(f"| {scene} / {a} | {s['outers']} | {s['rejects']} | {f(s['pcg_per_outer'])} | {f(s['retry_fraction'])} | {f(s['failed_fraction'])} | {s['numeric_repairs']} | {s['stop_counts']} |")
    lines+=['','## Misses','']
    for scene,x in result.items():
        for a,s in x['arms'].items():
            if s['misses']:lines.append(f"- {scene} / {a}: "+'; '.join(f"rep {v['rep']}: cost {v['cost']:.6f}, {v['stop']}" for v in s['misses']))
    lines+=['','## Verification and scope','',
      f"All 58 rows verified. Maximum independent objective discrepancy: {largest_audit:.3g} relative. Original source, 44 headers, fixed flags, derived binary/header hashes, input hashes, initial scores, trace counts, crossing times and endpoint-container hashes checked. No algorithm rebuild or coefficient change during the grid.",
      f"Historical reference: 8/10 successes, median {reg['historical']['median']:.9f}s, giving +20% ceiling {reg['historical']['maximum_on_median_20percent']:.9f}s. This older timing stream is context; fresh off/on is the primary comparison.",
      'The external MFREE 23-scene/dose results are supplied evidence and have not been independently reproduced here. No new Caspar run or global fastest-solver claim follows. Raw state exports were staged in RAM, independently audited and retained in verified compressed form on disk.']
    (Q/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(primary=primary,scenes={k:dict(hits={a:v['arms'][a]['hits'] for a in ['off','on']},cost_delta=v['cost_delta_percent']) for k,v in result.items()}),indent=2))
if __name__=='__main__':main()
