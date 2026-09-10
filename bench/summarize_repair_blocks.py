#!/usr/bin/env python3
"""Aggregate the development screen and independently audit split pair updates."""
import pathlib,json,math,statistics,re,sys
r=pathlib.Path('/workspace/prism-block-error');rows=[];audit=[];eps=sys.float_info.epsilon;next_checks=0
for stage in ['screen','repeat','optimized']:
 for x in json.loads((r/stage/'results.json').read_text()):
  rows.append(dict(x,study_stage=stage))
  if x['arm']!='split':continue
  log=(r/stage/(x['name']+'.log')).read_text();models={};pairs={}
  for line in log.splitlines():
   if line.startswith('REPAIR_SPLIT o=') or line.startswith('REPAIR_SPLIT_PAIR o='):
    d={k:float(v) for k,v in (word.split('=') for word in line.split()[1:])};(models if line.startswith('REPAIR_SPLIT o=') else pairs)[int(d['o'])]=d
  trace=[]
  for line in (r/stage/(x['name']+'.jsonl')).read_text().splitlines():
   line=re.sub(r'(?<=[,:\[])(-?nan|[+-]?inf)(?=[,}\]])',lambda m:'NaN' if 'nan' in m[1] else ('-Infinity' if m[1].startswith('-') else 'Infinity'),line);trace.append(json.loads(line))
  attempts={}
  for a in trace:
   if a.get('t')=='a':attempts.setdefault(a['o'],a)
  flags=json.loads((r/stage/(x['name']+'.manifest.json')).read_text())['flags'];floor=float(flags.get('OCA_LAM0','10'))*10**(-float(flags.get('OCA_LAM_FLOOR','8')))
  for o,m in models.items():
   for block,g,q in [('camera','gc','cc'),('point','gp','pp')]:
    pred=-m[g]-.5*m[q];assert math.isclose(pred,m[block+'_pred'],rel_tol=1e-12,abs_tol=1e-12)
    current,new=m['current'],m[block+'_cost'];valid=all(math.isfinite(v) for v in [current,new,m[g],m[q],pred]) and current>new and m[g]<0 and m[q]>=0 and pred>64*eps*max(1,current)
    rho=(current-new)/pred if valid else 0.;assert math.isclose(m[block+'_rho'],rho,rel_tol=1e-12,abs_tol=1e-12)
    fac=.5 if valid and rho>.75+64*eps*max(1,abs(rho)) else 1.;assert m[block+'_factor']==fac
   p=pairs[o];assert p['camera_factor']==m['camera_factor'] and p['point_factor']==m['point_factor']
   assert math.isclose(p['next_lambda'],min(1e8,max(floor,p['lambda']*p['camera_factor'])),rel_tol=1e-12)
   assert math.isclose(p['next_tau'],min(1e8,max(1e-7,p['tau']*p['point_factor'])),rel_tol=1e-12)
   if o+1 in attempts:
    n=attempts[o+1];assert math.isclose(n['lam'],p['next_lambda'],rel_tol=2e-6,abs_tol=1e-14);assert math.isclose(n['tau'],p['next_tau'],rel_tol=2e-6,abs_tol=1e-14);next_checks+=1
  assert len(models)==x['repair_calls'] and len(pairs)==len(models)
  assert sum(m['camera_factor']<1 for m in models.values())==x['split_camera_down'];assert sum(m['point_factor']<1 for m in models.values())==x['split_point_down']
  audit.append(dict(stage=stage,name=x['name'],models=models,pairs=pairs))
groups={}
for scene in ['dubrovnik-356','venice-52']:
 for arm in ['single','frozen','split']:
  a=[x for x in rows if x['scene']==scene and x['arm']==arm and x['study_stage']!='optimized'];med=lambda k:statistics.median(x.get(k,0) for x in a)
  groups[scene+'/'+arm]=dict(n=len(a),hits=sum(x['hit'] for x in a),cross=statistics.median(x['crossing_seconds'] for x in a) if all(x['hit'] for x in a) else None,seconds=med('seconds'),cost=med('cost'),matvecs=med('matvecs'),rejects=med('rejects'),backtrack=med('backtrack'),reported_scored=med('scored'),extra_block_scores=2*med('repair_calls') if arm=='split' else 0,repair_calls=med('repair_calls'),repair_seconds=med('repair_seconds'),split_seconds=med('split_seconds'),point_seconds=med('point_safe_seconds'),camera_down=med('split_camera_down'),point_down=med('split_point_down'))
for scene in ['dubrovnik-356','venice-52']:
 a=[x for x in rows if x['scene']==scene and x['study_stage']=='optimized'];med=lambda k:statistics.median(x.get(k,0) for x in a)
 groups['optimized/'+scene]=dict(n=len(a),hits=sum(x['hit'] for x in a),cross=statistics.median(x['crossing_seconds'] for x in a) if all(x['hit'] for x in a) else None,seconds=med('seconds'),cost=med('cost'),matvecs=med('matvecs'),backtrack=med('backtrack'),reported_scored=med('scored'),extra_block_scores=2*med('repair_calls'),repair_calls=med('repair_calls'),repair_seconds=med('repair_seconds'),split_seconds=med('split_seconds'),point_seconds=med('point_safe_seconds'),camera_down=med('split_camera_down'),point_down=med('split_point_down'))
captures=json.loads((r/'capture/results.json').read_text());measure=json.loads((r/'measurements.json').read_text());allruns=captures+rows
s=dict(runs=len(allruns),capture_runs=len(captures),screen_runs=len(rows),native_seconds=sum(x['seconds'] for x in allruns),max_endpoint_error=max(x['audit_relerr'] for x in allruns),captures=len(measure),cpu_cost_checks=4*len(measure),max_capture_cost_error=max(max(x['cpu_state_errors'].values()) for x in measure),max_coefficient_error=max(max(x['cpu_coefficient_errors'].values()) for x in measure),split_records=sum(len(x['models']) for x in audit),next_pair_checks=next_checks,groups=groups)
(r/'split-audits.json').write_text(json.dumps(audit,indent=2)+'\n');(r/'summary.json').write_text(json.dumps(s,indent=2)+'\n');print(json.dumps(s,indent=2))
