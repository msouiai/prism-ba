#!/usr/bin/env python3
import argparse,pathlib,json,re,collections,statistics,math
p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args();rows=[]
for phase in ['development','evaluation']:
 for f in sorted((a.root/phase).glob('*.json')):
  r=json.loads(f.read_text())
  if 'arm' not in r:continue
  r['phase']=phase
  if r.get('status','ok')=='ok':
   diagnostic=re.search(r'median_reproj_err_px (\S+) -> (\S+) \| cheirality_violations\(obs\) (\d+) -> (\d+)',f.with_suffix('.log').read_text())
   if diagnostic:
    r['median_reprojection_px']=float(diagnostic[2]);r['cheirality_observations']=int(diagnostic[4])

  if r.get('status','ok')=='ok' and r['arm']=='adaptive':
   events=[]
   for line in f.with_suffix('.log').read_text().splitlines():
    if not line.startswith('ADAPT '):continue
    e={k:float(v) for k,v in re.findall(r'(\w+)=(\S+)',line)}
    assert e['extra_evals']==4*e['full'],(f,'full menu count')
    assert 0<=e['value']<=4,(f,'controller value')
    assert abs(e['anchor_gain']+e['extra_gain']-e['menu_gain'])<=1e-8*max(1,e['menu_gain']),(f,'marginal gain accounting')
    events.append(e)
   assert events,(f,'missing diagnostics')
   assert sum(e['anchor_evals']+e['extra_evals'] for e in events)==r['menu_evals'],(f,'unaccounted scoring')
   r['adaptive_events']=events
   for k in ['full','narrow','flat','anchor_evals','extra_evals','anchor_s','extra_s','center_frozen']:
    r['adaptive_'+k]=sum(e[k] for e in events)
  rows.append(r)
(a.root/'results.json').write_text(json.dumps(rows,indent=2,allow_nan=False)+'\n')
lines=['# Adaptive candidate-menu pilot','',
 'Completed all 36 paired runs.' if len(rows)==36 else f'In progress: {len(rows)} retained runs of 36 planned.',
 'Three repeats per cell; 600-outer cap. Adaptive retains five CG shifts and changes scored candidates, with a confidence rule for the next center. Fixed single/multi controls use one/five shifts. All costs are GPU-fp64, initial costs independently checked. Small endpoint differences are tradeoffs; primary target bands are 1%,3%,5%.',
 '', '| Phase | Scene | Arm | Success / failures | Cost median [range] | Seconds median [range] | Iterations / retries / matvecs / scored medians |',
 '|---|---|---|---|---|---|---|']
groups=collections.defaultdict(list)
for r in rows:groups[r['phase'],r['scene'],r['arm']].append(r)
for (phase,scene,arm),rr in sorted(groups.items()):
 ok=[r for r in rr if r.get('status','ok')=='ok']
 def med(k):return statistics.median(r[k] for r in ok)
 def span(k):return f'{med(k):.6g} [{min(r[k] for r in ok):.6g}, {max(r[k] for r in ok):.6g}]' if ok else '—'
 work=' / '.join(f'{med(k):g}' for k in ['iters','rejects','matvecs','total_scored']) if ok else '—'
 lines.append(f'| {phase} | {scene} | {arm} | {len(ok)} / {len(rr)-len(ok)} | {span("cost")} | {span("seconds")} | {work} |')
lines+=['','## Time to acceptable quality','',
 'Per scene, reference is the lowest endpoint among these three fixed measured arms, not a proven optimum. Target is reference*(1+epsilon). Trace crossing bounds charge all untraced solver time and rounding before crossing. Missing attainment is retained; a median is shown only when all three runs reach the target.',
 '', '| Scene | Band | Arm | Reached / runs | Median upper-bound seconds |', '|---|---:|---|---|---:|']
crossings=[]
for scene in sorted({r['scene'] for r in rows}):
 rr=[r for r in rows if r['scene']==scene and r.get('status','ok')=='ok']
 if not rr:continue
 best=min(r['cost'] for r in rr)
 for eps in [.01,.03,.05]:
  for arm in ['single','multi','adaptive']:
   runs=[r for r in rr if r['arm']==arm];hits=[]
   for r in runs:
    tr=r['trace'];over=max(0,r['seconds']-float(tr[-1]['wall_s']));hit=next((float(t['wall_s'])+over+.000101 for t in tr if float(t['cost'])<=best*(1+eps)),None)
    crossings.append(dict(scene=scene,arm=arm,rep=r['rep'],epsilon=eps,target=best*(1+eps),solver_upper=hit))
    if hit is not None:hits.append(hit)
   t=f'{statistics.median(hits):.6g}' if len(hits)==len(runs)==3 else '—'
   lines.append(f'| {scene} | {eps:.0%} | {arm} | {len(hits)}/{len(runs)} | {t} |')
lines+=['','## Controller execution','', '| Scene | N | Full / center-only checkpoint menus (summed) | Freeze-eligible attempts | Anchor / extra scoring seconds (summed) |','|---|---:|---|---:|---|']
for scene in sorted({r['scene'] for r in rows}):
 rr=[r for r in rows if r['scene']==scene and r['arm']=='adaptive' and r.get('status','ok')=='ok']
 if not rr:continue
 sm=lambda k:sum(r['adaptive_'+k] for r in rr)
 lines.append(f'| {scene} | {len(rr)} | {sm("full"):g} / {sm("anchor_evals")-sm("full"):g} | {sm("center_frozen"):g} | {sm("anchor_s"):.3f} / {sm("extra_s"):.3f} |')
lines+=['','## Geometric diagnostics','',
 'These are reprojection and cheirality diagnostics, not ground-truth reconstruction accuracy.',
 '', '| Scene | Arm | N | Median reprojection error (px), median across runs | Cheirality violations (observations), median across runs |','|---|---|---:|---:|---:|']
for (phase,scene,arm),rr in sorted(groups.items()):
 ok=[r for r in rr if 'median_reprojection_px' in r]
 if ok:lines.append(f"| {scene} | {arm} | {len(ok)} | {statistics.median(r['median_reprojection_px'] for r in ok):.6g} | {statistics.median(r['cheirality_observations'] for r in ok):g} |")
(a.root/'crossings.json').write_text(json.dumps(crossings,indent=2)+'\n');a.out.write_text('\n'.join(lines)+'\n');print('Validated',len(rows),'retained runs')
