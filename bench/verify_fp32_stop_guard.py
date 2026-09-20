#!/usr/bin/env python3
import pathlib,json,re,statistics
from profile_iterations import sha
from cached_benchmark_input import load_input
from audit_prism_state import audit
ROOT=pathlib.Path('/workspace/prism-fresh-tr-caspar/fp32-stop-guard')
def main():
 p=json.loads((ROOT/'protocol.json').read_text());rows=json.loads((ROOT/'results.json').read_text());assert len(rows)==3
 assert sha('/workspace/prism-caspar-current/caspar32')==p['binary_sha256'];assert sha(pathlib.Path(__file__).with_name('caspar_fp32_stop_guard.py'))==p['harness_sha256']
 dh,(dims,obs),initial=load_input('/workspace/bal/final-13682.txt','/workspace/prism-caspar-expanded/cpu-cache');assert dh==p['data_sha256']
 for r in rows:
  stem=ROOT/f"final-13682-caspar32-guard-{r['rep']}";assert sha(stem.with_suffix('.state'))==r['state_sha256'];m=json.loads(stem.with_suffix('.manifest.json').read_text());assert m['target']==p['target'] and m['native_goal']==p['native_goal']
  cost=audit(stem.with_suffix('.state'),dims,obs);assert abs(cost-r['cost'])<1e-10*cost
  certified=r['crossing'] is not None and r['crossing']<=20 and cost<=p['target'];assert certified==r['hit']
 out=dict(runs=3,hits=sum(r['hit'] for r in rows),native_goal=p['native_goal'],certification_target=p['target'],median_crossing=statistics.median(r['crossing'] for r in rows) if all(r['hit'] for r in rows) else None,crossing_range=[min(r['crossing'] for r in rows),max(r['crossing'] for r in rows)],native_seconds=sum(r['native_seconds'] for r in rows),process_seconds=sum(r['process_wall'] for r in rows),max_audit_error=max(r['audit_error'] for r in rows),max_native_cpu_gap=max(r['native_cpu_gap'] for r in rows))
 (ROOT/'verification.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
if __name__=='__main__':main()
