#!/usr/bin/env python3
import argparse,json,re,statistics
from pathlib import Path
import numpy as np
from grid_common import P,write
def med(a):return statistics.median(a) if a else None
def summary(rows):
    times=[r['target_seconds'] for r in rows if r['hit']]
    return dict(n=len(rows),hits=len(times),target_median=med(times),target_range=[min(times),max(times)] if times else None,
      cost_median=med([r['cost'] for r in rows]),cost_range=[min(r['cost'] for r in rows),max(r['cost'] for r in rows)],
      native_median=med([r['native_seconds'] for r in rows]),rejects=[r['rejects'] for r in rows],
      pcg_per_outer=[r['pcg_per_outer'] for r in rows],retry_fraction=[r['retry_fraction_native'] for r in rows],
      failed_fraction=[r['failed_fraction_native'] for r in rows],cutoffs=[r['attempts']['curvature_cutoffs'] for r in rows],
      cutoff_accepts=[r['attempts']['cutoff_accepts'] for r in rows],repairs=[r['attempts']['numeric_repairs'] for r in rows],
      cap_hits=sum(r['cap_hit'] for r in rows),ftol=sum(r['stop_ftol'] for r in rows))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('candidate');a=ap.parse_args();all_rows=[];result={}
    for stage in ['practical','tail']:
        p=P/(a.candidate+'-'+stage+'-results.json')
        if not p.exists():continue
        rows=json.loads(p.read_text());all_rows.extend(rows);cells={}
        for cell in dict.fromkeys(r['cell'] for r in rows):
            arms={arm:summary([r for r in rows if r['cell']==cell and r['arm']==arm]) for arm in ['off','on']}
            off,on=arms['off'],arms['on'];matched=off['hits']==off['n'] and on['hits']==on['n'] and off['n']==on['n']
            signal='target_miss' if off['n']==on['n']==(3 if stage=='practical' else 5) else 'incomplete'
            if matched:
                signal='overlap'
                if on['target_range'][1]<off['target_range'][0]:signal='faster_disjoint'
                if off['target_range'][1]<on['target_range'][0]:signal='slower_disjoint'
            cells[cell]=dict(arms=arms,time_signal=signal,
              speedup=off['target_median']/on['target_median'] if matched and on['target_median'] else None,
              cost_delta_pct=100*(on['cost_median']/off['cost_median']-1))
        result[stage]=cells
    write(P/(a.candidate+'-native-summary.json'),result)
    lines=[f'# {a.candidate}: registered native comparison','',
      'Same derived binary, algorithm off/on; original-binary compatibility is reported separately. Identical original-observation targets, audited FP64 endpoints, all overhead counted in native time. Medians [min,max] are observed ranges, not confidence intervals. Misses remain censored.','']
    for stage,cells in result.items():
        lines += [f'## {stage}','', '| Cell | Off hits | On hits | Off target seconds | On target seconds | Speedup | Range signal |','|---|---:|---:|---:|---:|---:|---|']
        def tf(s):return '—' if s['target_median'] is None else f"{s['target_median']:.4f} [{s['target_range'][0]:.4f}, {s['target_range'][1]:.4f}]"
        for cell,c in cells.items():
            x,y=c['arms']['off'],c['arms']['on'];speed='—' if c['speedup'] is None else f"{c['speedup']:.3f}×"
            lines.append(f"| {cell} | {x['hits']}/{x['n']} | {y['hits']}/{y['n']} | {tf(x)} | {tf(y)} | {speed} | {c['time_signal']} |")
        lines+=['','| Cell / arm | Median full cost | Rejects | PCG/outer | Retry-entry / native wall | Nonaccepted / native wall | Curvature cutoffs / accepts |','|---|---:|---|---|---|---|---|']
        for cell,c in cells.items():
            for arm,s in c['arms'].items():
                fmt=lambda xs:', '.join(f'{x:.3g}' for x in xs)
                lines.append(f"| {cell} / {arm} | {s['cost_median']:.8g} | {s['rejects']} | {fmt(s['pcg_per_outer'])} | {fmt(s['retry_fraction'])} | {fmt(s['failed_fraction'])} | {s['cutoffs']} / {s['cutoff_accepts']} |")
        lines+=['']
    lines+=['## Limits','',
      'CSV target times have 0.0001-second resolution. Host steady-clock attempt tracing adds no GPU barrier; numeric continuations are included, and attempt acceptance/matvec totals must match native summaries. Retry-entry and nonaccepted-attempt fractions are distinct. Endpoint overshoot at a target stop is not automatically a quality advantage.',
      'N3 practical/N5 tail are screening cohorts. Report any larger-repetition confirmation separately. A configuration is not promoted solely by a favorable median on a subset. Frozen Eta2 remains the champion unless the complete registered gate passes.']
    (P/(a.candidate.upper()+'_NATIVE_RESULTS.md')).write_text('\n'.join(lines)+'\n')
    compact={stage:{cell:dict(speedup=x['speedup'],signal=x['time_signal'],hits=[x['arms'][a]['hits'] for a in ['off','on']]) for cell,x in cells.items()} for stage,cells in result.items()}
    print(json.dumps(compact,indent=2))
if __name__=='__main__':main()
