#!/usr/bin/env python3
"""Separate terminal-probe work from ordinary LM rows in the exact common trace."""
import argparse
import json
from pathlib import Path
import re

def analyze(trace,stdout):
 t=json.loads(Path(trace).read_text());text=Path(stdout).read_text();rows=t['rows']
 events=[]
 for m in re.finditer(r'SOFT_KICK_ATTEMPT trace_index=(\d+) o=(\d+) admitted=(\d+) ordinary_LM=0 fresh_assembly=1 history_preserved=1 retry_entry=(\d+) seconds=(\S+)',text):
  i,o,admit,retry,seconds=m.groups();i=int(i);r=rows[i]
  assert r['outer']==int(o) and r['pcg_iterations']==0 and not r['accepted']
  events.append(dict(trace_index=i,outer=int(o),admitted=bool(int(admit)),raw_retry_entry=bool(int(retry)),
    seconds=r['seconds'],matvecs=r['matvecs'],phase_seconds=float(seconds)))
 indices={e['trace_index'] for e in events};lm=[r for i,r in enumerate(rows) if i not in indices]
 m=re.search(r'MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+).*?negcurv=(\d+)',text)
 native=dict(zip(('accepts','rejects','matvecs','negcurv'),map(int,m.groups()))) if m else None
 total=sum(r['seconds'] for r in rows);probe=sum(e['seconds'] for e in events)
 fail=sum(r['seconds'] for r in lm if not r['accepted']);numeric=sum(r['seconds'] for r in lm if r['numeric_repair'])
 retry=sum(r['seconds'] for r in lm if r['retry_entry'])
 result=dict(raw=t['totals'],native=native,interventions=events,
  corrected=dict(ordinary_attempts=len(lm),ordinary_accepts=sum(r['accepted'] for r in lm),
    ordinary_failed_or_numeric_attempts=sum(not r['accepted'] for r in lm),
    numeric_attempts=sum(r['numeric_repair'] for r in lm),
    intervention_attempts=len(events),admitted_kicks=sum(e['admitted'] for e in events),skipped_kicks=sum(not e['admitted'] for e in events),
    intervention_seconds=probe,ordinary_attempt_seconds=total-probe,
    ordinary_failed_or_numeric_seconds=fail,numeric_repair_seconds=numeric,
    unchanged_state_retry_seconds=retry,unchanged_state_retry_wall_fraction=retry/total if total else 0,
    ordinary_failed_or_numeric_wall_fraction=fail/total if total else 0,
    intervention_wall_fraction=probe/total if total else 0),
  scope='Common not_accepted includes probe rows; corrected values explicitly exclude them. An admitted kick is not an LM rejection.')
 if native:
  assert sum(r['accepted'] for r in lm)==native['accepts'],'accept count mismatch'
  assert sum(r['matvecs'] for r in rows)==native['matvecs'],'matvec count mismatch'
  result['native_accept_and_matvec_invariants_pass']=True
 return result

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('trace');ap.add_argument('stdout');ap.add_argument('--out');a=ap.parse_args()
 result=analyze(a.trace,a.stdout);text=json.dumps(result,indent=2)+'\n'
 if a.out:Path(a.out).write_text(text)
 else:print(text,end='')
