#!/usr/bin/env python3
"""Keep budget caps and failures visible in the short medium-scene screen."""
import json,argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('/workspace/prism-medium'));p.add_argument('--output',type=Path,required=True);p.add_argument('--title',default='Short medium-size BA screen');a=p.parse_args();rows=[]
for folder in ['prism','caspar']:
 for path in (a.root/folder).glob('*.json'):
  r=json.loads(path.read_text())
  if 'status' not in r:continue
  r['family']=folder
  if r['status']=='ok':
   log=path.with_suffix('.log').read_text()
   r['rearm_events']=log.count('[menu-backtrack] rearmed after meaningful confirmation progress')
   r['confirmations']=log.count('[menu-backtrack] confirming stop with original retry policy')
  rows.append(r)
pm=json.loads((a.root/'prism'/'preregistered.json').read_text());cm=json.loads((a.root/'caspar'/'preregistered.json').read_text())
lines=['# '+a.title,'',f"One run per cell; no statistical verdict. PRISM: {pm['max_iter']}-outer cap, existing eight-probe backtracking. Caspar: FP32 {', '.join(cm['profiles'])}, iteration caps {cm['budgets']}.",f"All jobs share the GPU lock; PRISM timeout {pm['timeout']} seconds, Caspar timeout {cm['timeout']} seconds. Unequal iteration budgets compare early progress, not equal work or full convergence.",'Caspar endpoints are CPU-fp64 checked against original observations; PRISM initial costs are independently checked. PRISM final costs are its fp64 solver scores.','','| Scene | Method | Status | Iterations | Seconds | Final cost | Rejects | Rescues | Rearms |','|---|---|---|---:|---:|---:|---:|---:|---:|']
for r in sorted(rows,key=lambda r:(r['scene'],r['arm'])):
 if r['status']!='ok':
  lines.append(f'| {r["scene"]} | {r["arm"]} | failed / return code {r.get("returncode")} | — | — | — | — | — | — |');continue
 lines.append(f'| {r["scene"]} | {r["arm"]} | completed | {r["iters"]} | {r["seconds"]:.3f} | {r["cost"]:,.3f} | {r.get("rejects","—")} | {r.get("backtrack_rescues","—")} | {r["rearm_events"] if r["family"]=="prism" else "—"} |')
lines+=['','## Cost-matched comparison','','Conservative PRISM time to Caspar\'s checked endpoint. All untraced solver time is charged before crossing.','The Caspar column certifies its endpoint only, not its unknown first crossing.','','| Scene | PRISM arm | PRISM seconds to Caspar endpoint | Caspar full seconds | Caspar final cost at/below PRISM endpoint? |','|---|---|---:|---:|---|']
for r in rows:
 if r['family']!='prism' or r['status']!='ok':continue
 cc=next((c for c in rows if c['family']=='caspar' and c['scene']==r['scene'] and c['status']=='ok'),None)
 if cc is None:continue
 overhead=max(0,r['seconds']-float(r['trace'][-1]['wall_s']))
 crossing=next((float(t['wall_s'])+overhead for t in r['trace'] if float(t['cost'])<=cc['cost']),None)
 r['seconds_to_caspar_endpoint']=crossing
 r['cost_change_vs_caspar_percent']=100*(r['cost']/cc['cost']-1)
 lines.append(f'| {r["scene"]} | {r["arm"]} | {crossing:.4f} | {cc["seconds"]:.4f} | {"yes" if cc["cost"]<=r["cost"] else "no"} |' if crossing is not None else f'| {r["scene"]} | {r["arm"]} | not attained in budget | {cc["seconds"]:.4f} | {"yes" if cc["cost"]<=r["cost"] else "no"} |')
(a.root/'results.json').write_text(json.dumps(rows,indent=2)+'\n');a.output.write_text('\n'.join(lines)+'\n');print('completed',sum(r['status']=='ok' for r in rows),'failed',sum(r['status']!='ok' for r in rows))
