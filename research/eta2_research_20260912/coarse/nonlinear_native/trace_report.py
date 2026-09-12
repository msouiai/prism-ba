#!/usr/bin/env python3
"""Keep raw common trace, explicitly identify non-LM probe work."""
import json,re
from pathlib import Path

def report(folder):
    folder=Path(folder);trace=json.loads((folder/'attempts.json').read_text());text=(folder/'stdout.log').read_text();rows=trace['rows']
    events=[]
    for line in text.splitlines():
        if line.startswith('PASSENGER_EVENT '):events.append(dict(re.findall(r'(\w+)=([^ ]+)',line)))
    probes=[x for x in events if x['event']=='probe'];probe_ids={int(x['trace_row']) for x in probes}
    continuations={int(x['trace_row']) for x in events if x['event']=='fine_continuation'}
    ordinary=[r for i,r in enumerate(rows) if i not in probe_ids]
    probe_seconds=sum(rows[i]['seconds'] for i in probe_ids);episode_seconds=sum(float(x['seconds']) for x in probes)
    total=trace['totals']['attempt_seconds'];raw_retry=sum(r['seconds'] for r in rows if r['retry_entry'])
    corrected_retry=sum(r['seconds'] for i,r in enumerate(rows) if r['retry_entry'] and i not in probe_ids and i not in continuations)
    count=re.search(r'MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)',text)
    assert count and trace['totals']['accepted']==int(count[1]) and trace['totals']['matvecs']==int(count[3])
    assert len(probes)<=1 and all(rows[i]['matvecs']==0 and rows[i]['pcg_iterations']==0 and not rows[i]['accepted'] for i in probe_ids)
    controls=[]
    for line in text.splitlines():
        if line.startswith('PASSENGER_CONTROL '):
            row=dict(re.findall(r'(\w+)=([^ ]+)',line))
            for key in ('lambda','radius','floor','forcing','last_rel','confirm'):assert row[key+'_before']==row[key+'_after']
            controls.append(row)
    result=dict(probe_events=probes,probe_trace_rows=sorted(probe_ids),fine_continuation_rows=sorted(continuations),
        raw_attempt_seconds=total,raw_retry_entry_seconds=raw_retry,corrected_unchanged_state_retry_seconds=corrected_retry,
        corrected_unchanged_state_retry_fraction=corrected_retry/total if total else 0,
        probe_attempt_seconds_including_fresh_fine_setup=probe_seconds,probe_episode_seconds=episode_seconds,
        ordinary_attempts=len(ordinary),ordinary_not_accepted=sum(not r['accepted'] for r in ordinary),
        native_accepts=int(count[1]),native_rejects=int(count[2]),matvecs=int(count[3]),trace_count_invariants=True,
        controller_invariants=controls,ordinary_not_accepted_note='Includes numerical repair; use native_rejects for actual LM rejects. Probe rows are separately excluded.')
    (folder/'passenger_trace.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    import sys;print(json.dumps(report(sys.argv[1]),indent=2))
