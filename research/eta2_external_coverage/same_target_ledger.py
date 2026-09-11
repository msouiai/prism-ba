#!/usr/bin/env python3
"""Combine local target measurements and explicitly labeled external evidence."""
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

P = Path(__file__).resolve().parent
B = P / 'banked'


def write(name, value):
    (P / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def stats(values):
    return dict(median=statistics.median(values), min=min(values), max=max(values)) if values else None


def main():
    for entry in json.loads((B / 'sources.json').read_text()):
        assert hashlib.sha256((B / entry['copy']).read_bytes()).hexdigest() == entry['sha256'], entry
    targets = {}
    for name in ['early-storm-targets.json', 'storm-targets.json']:
        if (P / name).exists():
            for scene, r in json.loads((P / name).read_text()).items():
                if scene in targets:
                    assert targets[scene] == r['target']
                targets[scene] = r['target']
    assert targets['final-3068'] == 1744796.9841897595
    rows = []
    for r in json.loads((P / 'all-results.json').read_text()):
        if r['stage'] not in ['storm', 'ceres-storm']:
            continue
        rows.append(dict(scene=r['scene'], arm=('Eta2 champion' if r['solver']=='eta2' else 'Ceres '+r['arm']),
          rep=r['rep'], host='Codex', evidence='fresh', target=r.get('target'), hit=r.get('hit') if r['valid'] else None,
          valid=r['valid'], cost=r.get('cost'), native_seconds=r.get('native_seconds'),
          target_seconds=r.get('target_seconds'), timing_kind='accepted crossing',
          source=r.get('source'), endpoint_audit='local FP64'))

    manifest = json.loads((B / 'caspar32/preregistered.json').read_text())
    primary_manifest = json.loads((P / 'evidence/ceres-storm/preregistered.json').read_text())
    for scene in ['final-3068', 'final-4585']:
        assert manifest['data_sha256'][scene] == primary_manifest['data_sha256'][scene]
    for f in sorted((B / 'caspar32').glob('final-*.json')):
        r=json.loads(f.read_text())
        assert r['status']=='ok' and r['data_sha256']==manifest['data_sha256'][r['scene']]
        # Reconcile the preserved scored row with its native output.
        log=f.with_suffix('.log').read_text()
        checked=re.search(r'CHECK final_score=(\S+)',log)
        result=re.search(r'RESULT exit=(\d+) iters=(\d+) final_score=(\S+) runtime=(\S+)',log)
        assert checked and result and float(checked[1])==r['cost'] and float(result[4])==r['seconds']
        target=targets.get(r['scene'])
        hit=r['cost']<=target if target is not None else None
        native_trace=[float(c) for c in re.findall(r'TRACE iter=\d+ cost=(\S+)',log)]
        assert native_trace and all(math.isfinite(c) for c in native_trace)
        rows.append(dict(scene=r['scene'],arm='Caspar32 '+r['profile']+' / '+str(r['budget']),
          rep=r['rep'],host='Codex',evidence='banked',target=target,hit=hit,valid=True,cost=r['cost'],
          native_seconds=r['seconds'],target_seconds=None,timing_kind='endpoint only; native trace is FP32',
          native_trace_min=min(native_trace),source=str(f.relative_to(P)),endpoint_audit='banked driver FP64',
          input_sha256=r['data_sha256'],binary_sha256=manifest['binary_sha256']))

    text=(B / 'mfree_target3068.csv').read_text().splitlines()
    assert text[-1]=='TARGET3068_DONE'
    supplied=list(csv.DictReader(text[:-1]))
    assert len(supplied)==20
    for arm in ['base','deep']:
        assert sorted(int(r['rep']) for r in supplied if r['arm']==arm)==list(range(1,11))
    for r in supplied:
        cost=float(r['cost']); secs=float(r['secs']); target=targets['final-3068']
        hit=cost<target
        assert hit==bool(int(r['hit'])) and math.isfinite(cost) and secs>0
        rows.append(dict(scene='final-3068',arm='MFREE '+r['arm'],rep=int(r['rep']),host='Claude',
          evidence='collaborator CSV',target=target,hit=hit,valid=True,cost=cost,native_seconds=secs,
          target_seconds=secs if hit else None,timing_kind='crossing-time upper bound',
          source='banked/mfree_target3068.csv',endpoint_audit='collaborator-reported'))

    setup_results=P/'ceres_setup/results.json'
    if setup_results.exists():
        for r in json.loads(setup_results.read_text()):
            assert r['target']==targets['final-3068']
            rows.append(dict(scene=r['scene'],arm='Ceres setup '+r['arm'],rep=r['rep'],host='Codex',
              evidence='separate setup screen',target=r['target'],hit=r['hit'] if r['valid'] else None,
              valid=r['valid'],cost=r.get('cost'),native_seconds=r.get('native_seconds'),
              target_seconds=r.get('target_seconds'),timing_kind='accepted crossing',
              source='ceres_setup/'+r['source'],endpoint_audit='local FP64'))

    # Aggregate provenance is deliberately not converted into synthetic repetitions.
    old=(B / 'champion_vs_mine_samehost.txt').read_text()
    f64=float(re.search(r'^final-3068\s+(\S+)',old,re.M)[1])
    assert f64>targets['final-3068']
    aggregate=dict(scene='final-3068',arm='Caspar f64',host='Claude',evidence='collaborator aggregate',
      target=targets['final-3068'],reported_cost=f64,reported_hit=False,n=None,hits=None,
      native_seconds=None,target_seconds=None,source='banked/champion_vs_mine_samehost.txt',
      note='Rounded aggregate; never-hit statement supplied by collaborator. N and solve times unavailable.')
    summary=[]
    for scene, arm in sorted({(r['scene'],r['arm']) for r in rows}):
        rr=[r for r in rows if (r['scene'],r['arm'])==(scene,arm)]
        known=[r for r in rr if r['hit'] is not None]
        summary.append(dict(scene=scene,arm=arm,n=len(rr),valid=sum(r['valid'] for r in rr),
          known_outcomes=len(known),hits=sum(r['hit'] for r in known) if known else None,
          target=targets.get(scene),host=rr[0]['host'],evidence=rr[0]['evidence'],
          cost=stats([r['cost'] for r in rr if r['cost'] is not None]),
          native_seconds=stats([r['native_seconds'] for r in rr if r['native_seconds'] is not None]),
          target_seconds=stats([r['target_seconds'] for r in rr if r['hit'] and r['target_seconds'] is not None]),
          timing_kind=rr[0]['timing_kind']))
    write('same-target-runs.json',rows)
    write('same-target-ledger.json',dict(targets=targets,summary=summary,aggregate_only=[aggregate]))
    with (P / 'same-target-runs.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=sorted(set().union(*(r.keys() for r in rows))),lineterminator='\n')
        writer.writeheader();writer.writerows(rows)
    lines=['# Same-target ledger: measured hits and misses','',
      'Banked profiles remain separate. Times below are native solve seconds; no time-to-target is assigned to a miss.',
      'Claude-host measurements are not same-host timing comparisons. Successful-run medians are conditional.',
      'Counts describe the available repetitions, not known population success probabilities.','']
    def fmt(value):
        return f"{value['median']:,.3f} [{value['min']:,.3f}, {value['max']:,.3f}]" if value else '—'
    for scene in ['final-3068','final-4585']:
        target=targets.get(scene)
        lines += ['## '+scene,'',('Target: '+repr(target)) if target is not None else 'Target pending completion of the registered Ceres endpoint stage.','',
          '| Arm | Observed hits | Host / evidence | Endpoint median [range] | Full solve median [range], s | Conditional target time median [range], s |',
          '|---|---:|---|---:|---:|---:|']
        for r in summary:
            if r['scene']!=scene:continue
            hits=f"{r['hits']}/{r['n']}" if r['known_outcomes']==r['n'] else f"pending ({r['n']} runs)"
            timing=fmt(r['target_seconds'])
            if r['target_seconds'] and r['timing_kind']=='crossing-time upper bound':timing='≤ '+timing+' (upper bounds)'
            lines.append(f"| {r['arm']} | {hits} | {r['host']} / {r['evidence']} | {fmt(r['cost'])} | {fmt(r['native_seconds'])} | {timing} |")
        if scene=='final-3068':
            lines.append(f"| Caspar f64 | reported miss; N unavailable | Claude / original aggregate | ≈ {f64:,.0f} | unavailable | — |")
        lines.append('')
    lines += ['Final3068: Eta2 has 8/10 observed hits and a 3.692-second conditional median. MFREE-deep has 5/10 and a 15.694-second median upper bound on crossing time. These samples do not establish a population reliability ranking or a same-host speed ratio.', '',
      'Ceres dogleg has 2/3 hits at 686.494–1918.991 seconds; its conditional median divided by Eta2’s is about 353 on this host and this frozen configuration. This excludes misses and is not an unconditional speedup. The separate Ceres setup sensitivity experiment tests how dependent that comparison is on the baseline setup.', '',
      'Any Ceres setup rows are a separate 60-native-second exploratory screen with a new instrumented driver. They keep the same target but are not pooled into the frozen primary Ceres medians. See ceres_setup/PROTOCOL.md and ceres_setup/README.md when available.', '',
      'Caspar32 endpoint hits are checked with the banked CPU FP64 original-observation score. Its FP32 traces are retained as diagnostics but cannot certify an FP64 crossing. The reported f64 aggregate has no delivered raw repetitions or times; the old table’s 3/3 column belongs to other solvers at a different target.', '',
      'Sources and limitations: [banked/PROVENANCE.md](banked/PROVENANCE.md). Machine-readable runs and aggregates: same-target-runs.csv, same-target-runs.json, same-target-ledger.json. The primary experiment remains separate in summary.json and runs.csv.', '']
    (P / 'SAME_TARGET_LEDGER.md').write_text('\n'.join(lines))
    print('Ledger updated:',len(rows),'individual runs;',len(summary),'groups; one aggregate-only f64 row')


if __name__=='__main__':
    main()
