#!/usr/bin/env python3
"""Summarize every registered pair, independently validate rows and initial scores."""
from collections import Counter
from pathlib import Path
import csv,json,re,statistics,sys
import numpy as np
from run import P,G

def median(x):return statistics.median(x) if x else None
def aggregate(rows):
    times=[r['target_seconds'] for r in rows if r['hit']]
    return dict(n=len(rows),hits=len(times),time_median=median(times),time_range=[min(times),max(times)] if times else None,
        cost_median=median([r['cost'] for r in rows]),cost_range=[min(r['cost'] for r in rows),max(r['cost'] for r in rows)],
        native_median=median([r['native_seconds'] for r in rows]),outers=[r['outers'] for r in rows],
        rejects=[r['rejects'] for r in rows],pcg_per_outer=[r['pcg_per_outer'] for r in rows],
        retry_fraction=[r['retry_fraction_native'] for r in rows],failed_fraction=[r['failed_fraction_native'] for r in rows],
        curvature_cutoffs=[r['attempts']['curvature_cutoffs'] for r in rows],
        numeric_repairs=[r['attempts']['numeric_repairs'] for r in rows],
        ftol_markers=sum(r['stop_ftol'] for r in rows),caps=sum(r['cap_hit'] for r in rows),
        score_init_range=[min(r['score_init'] for r in rows),max(r['score_init'] for r in rows)])

def main():
    rows=json.loads((P/'tail-results.json').read_text());assert len(rows)==20
    assert set(Counter((r['scene'],r['arm']) for r in rows).values())=={5}
    result={};all_inputs={};input_hashes={};manifest=json.loads((P/'build_manifest.json').read_text())
    assert G.sha(P/'build/prism-track-tau')==manifest['binary_sha256']
    assert G.sha(G.F/'source/prism_eta2.cu')==manifest['frozen_source_sha256']
    assert G.sha(P/'build/prism_track_tau.cu')==manifest['derived_source_sha256']
    assert G.sha(G.F/'champion.json')==manifest['champion_sha256']
    assert all(G.sha(P/k)==v for k,v in manifest['headers'].items())
    for r in rows:
        f=P/r['source'];m=json.loads((f/'manifest.json').read_text())
        assert r==json.loads((f/'result.json').read_text()) and r['valid'] and r['audit_relative_error']<1e-6
        assert m['binary_sha256']==manifest['binary_sha256'] and m['protocol_sha256']==G.sha(P/'PROTOCOL.md')
        problem=m['command'][m['command'].index('--problem')+1]
        if problem not in input_hashes:input_hashes[problem]=G.sha(problem)
        assert input_hashes[problem]==m['input_sha256']
        assert m['flags']['OCA_TRACK_TAU']==str(int(r['arm']=='on'))
        for k,v in G.CHAMP['flags'].items():assert m['flags'][k]==v
        assert G.sha(f/'endpoint.state.gz')==r['state']['compressed_sha256']
        curve=list(csv.DictReader(x for x in (f/'curve.csv').read_text().splitlines() if not x.startswith('#')))
        crossing=next((float(x['wall_s']) for x in curve if float(x['cost'])<=r['target']),None)
        hit=r['cost']<=r['target'] and crossing is not None and crossing<=r['cap']
        assert r['hit']==hit and r['target_seconds']==(crossing if hit else None)
        assert r['attempts']['accepted']==r['accepts'] and r['attempts']['matvecs']==r['matvecs']
    for scene in sorted({r['scene'] for r in rows}):
        arms={a:aggregate([r for r in rows if r['scene']==scene and r['arm']==a]) for a in ['off','on']}
        result[scene]=dict(arms=arms,cost_delta_percent=100*(arms['on']['cost_median']/arms['off']['cost_median']-1),
            hit_delta=arms['on']['hits']-arms['off']['hits'])
        path=Path('/workspace/bal')/(scene+'.txt');dims,obs=G.observations(path)
        counts=np.bincount(obs[:,1].astype(np.int64),minlength=dims[1]);classes=np.where(counts<=2,0,np.where(counts<=5,1,2))
        all_inputs[scene]=dict(input_sha256=G.sha(path),dimensions=dims,
          class_points=[int(sum(classes==i)) for i in range(3)],
          class_observations=[int(counts[classes==i].sum()) for i in range(3)],
          long_point_fraction=float(np.mean(counts>=6)))
        values=[r['score_init'] for r in rows if r['scene']==scene]
        assert max(values)-min(values)<=1e-9*max(values)
    hit_gate=max(x['hit_delta'] for x in result.values())>=2 and min(x['hit_delta'] for x in result.values())>-2
    endpoint_gate=min(x['cost_delta_percent'] for x in result.values())<-.15 and max(x['cost_delta_percent'] for x in result.values())<=.5
    report=dict(paired=result,inputs=all_inputs,extension_gate=bool(hit_gate or endpoint_gate),
                hit_gate=hit_gate,endpoint_gate=endpoint_gate,all_twenty_rows_verified=True,
                protocol_sha256=G.sha(P/'PROTOCOL.md'),binary_sha256=manifest['binary_sha256'])
    G.write(P/'summary.json',report)
    lines=['# Static long-track damping: paired transfer screen','',
       'Full original-observation objective; one binary off/on; N=5 per arm per scene. Ranges are observed samples, not confidence intervals. Misses are censored. Native times count the intervention and attempt tracing.','',
       '| Scene | Off hits | On hits | Off target seconds | On target seconds | Off median cost | On median cost | Cost delta |',
       '|---|---:|---:|---|---|---:|---:|---:|']
    def fmt(s):return '—' if s['time_median'] is None else f"{s['time_median']:.4f} [{s['time_range'][0]:.4f}, {s['time_range'][1]:.4f}]"
    for sc,x in result.items():
        o,n=x['arms']['off'],x['arms']['on']
        lines.append(f"| {sc} | {o['hits']}/5 | {n['hits']}/5 | {fmt(o)} | {fmt(n)} | {o['cost_median']:.3f} | {n['cost_median']:.3f} | {x['cost_delta_percent']:+.3f}% |")
    lines+=['','Conditional crossing times on different successful subsets are not a matched speedup. Target-stopped endpoint overshoot is not by itself a quality win.','',
      '| Scene / arm | Outers | Rejects | PCG/outer | Retry/native wall | Failed/native wall | Curvature repairs | FTOL / cap |',
      '|---|---|---|---|---|---|---|---|']
    for sc,x in result.items():
        for a,s in x['arms'].items():
            f=lambda vv:', '.join(f'{v:.3g}' for v in vv)
            lines.append(f"| {sc} / {a} | {s['outers']} | {s['rejects']} | {f(s['pcg_per_outer'])} | {f(s['retry_fraction'])} | {f(s['failed_fraction'])} | {s['numeric_repairs']} | {s['ftol_markers']} / {s['caps']} |")
    lines+=['','## Input classes and initial scores','',
      '| Scene | Points: ≤2 / 3–5 / ≥6 obs | Observations in those classes | Initial score range |','|---|---|---|---|']
    for sc,x in all_inputs.items():
        ss=[r['score_init'] for r in rows if r['scene']==sc]
        lines.append(f"| {sc} | {x['class_points']} | {x['class_observations']} | [{min(ss):.12g}, {max(ss):.12g}] |")
    lines+=['',f"Registered extension gate: **{'PASS' if report['extension_gate'] else 'FAIL'}**. Hit gate={hit_gate}; endpoint gate={endpoint_gate}.",
      'No per-scene parameter or alternative dose was selected from these outcomes. All traces, commands, source/input hashes, audited results and exact compressed scored endpoints are retained.']
    (P/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
