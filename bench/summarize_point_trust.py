#!/usr/bin/env python3
"""Summarize every retained run, with misses excluded from speedup claims."""
import argparse
import json
import pathlib
import re
import statistics as st


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=pathlib.Path)
    root = parser.parse_args().root
    stages = {p.parent.name: json.loads(p.read_text())
              for p in sorted(root.glob('*/results.json'))}
    rows = [r for rr in stages.values() for r in rr]
    comparison = {}
    model_rows = stages.get('full-model', []) + stages.get('full-model-confirm', [])
    for scene in sorted({r['scene'] for r in model_rows}):
        comparison[scene] = {}
        for shifts in [1, 5]:
            arms = {}
            for mode in ['baseline', 'full']:
                rr = [r for r in model_rows if r['scene'] == scene
                      and r['arm'] == f'shift{shifts}-{mode}']
                if not rr:
                    continue
                arms[mode] = dict(
                    n=len(rr), hits=sum(r['hit'] for r in rr),
                    crossing_seconds=st.median(r['crossing_seconds'] for r in rr)
                    if all(r['hit'] for r in rr) else None,
                    **{k: st.median(r.get(k, 0) for r in rr) for k in
                       ['seconds', 'cost', 'rejects', 'matvecs', 'scored',
                        'full_model_calls', 'full_model_seconds']})
            if all(arms.get(m, {}).get('crossing_seconds') for m in ['baseline', 'full']):
                arms['speedup'] = arms['baseline']['crossing_seconds'] / arms['full']['crossing_seconds']
            comparison[scene][str(shifts)] = arms
    prediction = {}
    for stage in ['full-model', 'full-model-confirm']:
        for r in stages.get(stage, []):
            if not r['arm'].endswith('full'):
                continue
            text = (root / stage / (r['name'] + '.log')).read_text()
            pairs = re.findall(r'FULL_MODEL o=\d+ prediction=(\S+) old_prediction=(\S+)', text)
            ratios = [float(a) / float(b) for a, b in pairs if float(b) > 0]
            prediction[stage + '/' + r['name']] = dict(
                calls=len(pairs), positive_old=len(ratios),
                direct_over_old_min=min(ratios) if ratios else None,
                direct_over_old_median=st.median(ratios) if ratios else None,
                direct_over_old_max=max(ratios) if ratios else None)
    summary = dict(runs=len(rows), native_seconds=sum(r['seconds'] for r in rows),
                   target_runs=sum('target' in r for r in rows),
                   target_hits=sum(r.get('hit', False) for r in rows),
                   max_cpu_relative_error=max(r['audit_relerr'] for r in rows),
                   stage_runs={s: len(rr) for s, rr in stages.items()},
                   full_model_comparison=comparison, prediction_diagnostics=prediction,
                   point_feedback_promoted=False, defaults_changed=False)
    (root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
