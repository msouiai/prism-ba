#!/usr/bin/env python3
"""Audit the selection guarantee and report retained priority-pilot results."""
import pathlib,json,re,math,statistics,collections,argparse
p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args();rows=[]
pattern=r'HYST o=(\d+) retry=(\d+) prior=(\S+) center=(\S+) current=(\S+) greedy=(-?\d+) preferred=(-?\d+) selected=(-?\d+) costs=(\S+) shifts=(\S+) depths=(\S+)'
for phase in ['main','stress']:
 for f in sorted((a.root/phase).glob('*.json')):
  r=json.loads(f.read_text())
  if 'arm' not in r:continue
  if r.get('status','ok')!='ok':rows.append(dict(r,phase=phase));continue
  log=f.with_suffix('.log').read_text();events=[]
  for m in re.findall(pattern,log):
   o,retry=int(m[0]),int(m[1]);prior,center,current=map(float,m[2:5]);greedy,preferred,selected=map(int,m[5:8]);costs=list(map(float,m[8].split(',')));shifts=list(map(float,m[9].split(',')))
   gains=sorted([current-c for c in costs if math.isfinite(c) and c<current],reverse=True)
   if preferred>=0:
    assert gains and current-costs[preferred]>=.95*gains[0],(f,o,'reduction guarantee')
    eligible=[j for j,c in enumerate(costs) if math.isfinite(c) and current-c>=.95*gains[0]]
    dist=lambda j:abs(math.log(shifts[j])-math.log(prior))
    assert dist(preferred)<=min(map(dist,eligible))+1e-12,(f,o,'distance guarantee')
   if r['arm']=='hysteresis' and preferred>=0:assert selected==preferred,(f,o,'selection mismatch')
   events.append(dict(outer=o,retry=retry,prior=prior if math.isfinite(prior) else None,center=center,greedy=greedy,preferred=preferred,selected=selected,selected_shift=shifts[selected] if selected>=0 else None,depths=list(map(int,m[10].split(','))),relative_gap=None if len(gains)<2 else (gains[0]-gains[1])/gains[0],retained_fraction=None if not gains or selected<0 else (current-costs[selected])/gains[0]))
  gaps=[e['relative_gap'] for e in events if e['relative_gap'] is not None]
  centers=[float(x) for x in re.findall(r'MFCG it\s+\d+ cost=\S+ lam=(\S+).*? acc',log)]
  moves=[math.log10(y/x) for x,y in zip(centers,centers[1:]) if x>0 and y>0];sign=[1 if x>0 else -1 for x in moves if abs(x)>.01]
  r.update(phase=phase,events=events,competitive_menus=len(gaps),near_tie_menus=sum(g<=.05 for g in gaps),preferred_switches=sum(e['preferred']>=0 and e['preferred']!=e['greedy'] for e in events),actual_switches=sum(e['selected']!=e['greedy'] for e in events),center_reversals=sum(x!=y for x,y in zip(sign,sign[1:])))
  rows.append(r)
(a.root/'results.json').write_text(json.dumps(rows,indent=2,allow_nan=False)+'\n')
lines=['# Lambda hysteresis priority pilot','',
'Fixed retention fraction 95%; same instrumented binary in both arms. All previously scored candidates remain scored. Per-shift best checkpoint candidates are compared before the existing alpha search. The 95% guarantee applies to menu reduction at that stage, not the final alpha-optimized endpoint or future trajectory.',
'Venice/Ladybug use 600 outers; final-3068 uses a 100-outer transient/retry-stress cap. No full-convergence claim for that scene. N=3 ranges are not tail bounds.',
'', '| Phase | Scene | Arm | N | Iterations median | Cost median [range] | Seconds median [range] | Rejects | Center reversals | Near ties / competitive menus | Preferred switches |',
'|---|---|---|---:|---:|---|---|---:|---:|---|---:|']
groups=collections.defaultdict(list)
for r in rows:groups[r['phase'],r['scene'],r['arm']].append(r)
for (phase,scene,arm),rr in sorted(groups.items()):
 ok=[r for r in rr if r.get('status','ok')=='ok']
 def med(k):return statistics.median(r[k] for r in ok) if ok else math.nan
 def span(k):return f'{med(k):.6g} [{min(r[k] for r in ok):.6g}, {max(r[k] for r in ok):.6g}]' if ok else 'failed'
 lines.append(f"| {phase} | {scene} | {arm} | {len(ok)} | {med('iters'):g} | {span('cost')} | {span('seconds')} | {med('rejects'):g} | {med('center_reversals'):g} | {med('near_tie_menus'):g} / {med('competitive_menus'):g} | {med('preferred_switches'):g} |")
lines+=['','## Time to common quality','', 'Targets use the lowest observed endpoint across both arms on each scene times (1+epsilon). Accepted trace times charge untraced solver overhead. An unattained target remains missing.','', '| Scene | Epsilon | Arm | Reached / runs | Median upper-bound seconds (only if all three reach) |','|---|---:|---|---|---:|']
for scene in sorted({r['scene'] for r in rows}):
 rr=[r for r in rows if r['scene']==scene and r.get('status','ok')=='ok'];best=min(r['cost'] for r in rr)
 for eps in [.01,.001,.0001]:
  for arm in ['control','hysteresis']:
   hits=[];group=[r for r in rr if r['arm']==arm]
   for r in group:
    tr=r['trace'];over=max(0,r['seconds']-float(tr[-1]['wall_s']));hit=next((float(t['wall_s'])+over+.000101 for t in tr if float(t['cost'])<=best*(1+eps)),None)
    if hit is not None:hits.append(hit)
   value=f'{statistics.median(hits):.6g}' if len(hits)==len(group)==3 else '—'
   lines.append(f'| {scene} | {eps:g} | {arm} | {len(hits)}/{len(group)} | {value} |')
a.out.write_text('\n'.join(lines)+'\n');print('Verified selection guarantees for',len(rows),'retained runs')
