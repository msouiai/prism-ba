#!/usr/bin/env python3
"""Audit actual-step predictions and committed pair transitions; summarize targets."""
import pathlib,json,re,math,statistics,sys
r=pathlib.Path('/workspace/prism-repair-damping');allrows=[];events=[];groups={};next_checks=0;eps=sys.float_info.epsilon
for stage in ['audit','medium','prospective','prospective-repeat']:
 rows=json.loads((r/stage/'results.json').read_text());allrows+=rows
 for row in rows:
  text=(r/stage/(row['name']+'.log')).read_text();models=[];pairs={}
  flags=json.loads((r/stage/(row['name']+'.manifest.json')).read_text())['flags']
  for m in re.finditer(r'REPAIR_PAIR o=(\d+) lambda=(\S+) tau=(\S+) next_lambda=(\S+) next_tau=(\S+) factor=(\S+)',text):pairs[int(m[1])]=list(map(float,m.group(2,3,4,5,6)))
  trace=[json.loads(re.sub(r'(?<=[,:\[])(-?nan|[+-]?inf)(?=[,}\]])',lambda m:'NaN' if 'nan' in m[1] else ('-Infinity' if m[1].startswith('-') else 'Infinity'),s)) for s in (r/stage/(row['name']+'.jsonl')).read_text().splitlines()];attempts={}
  for x in trace:
   if x.get('t')=='a':attempts.setdefault(x['o'],x)
  for m in re.finditer(r'REPAIR_MODEL o=(\d+) mode=(\d+) current=(\S+) next=(\S+) slope=(\S+) curvature=(\S+) prediction=(\S+) rho=(\S+) factor=(\S+) valid=(\d+)',text):
   o,mode=int(m[1]),int(m[2]);current,new,slope,curv,pred,rho,fac=map(float,m.group(3,4,5,6,7,8,9));valid=bool(int(m[10]));p=-slope-.5*curv;assert math.isclose(p,pred,rel_tol=1e-12,abs_tol=1e-12)
   expected=all(math.isfinite(x) for x in [current,new,slope,curv,pred]) and current>new and slope<0 and curv>=0 and pred>64*eps*max(1,current)
   assert valid==expected
   if valid:assert math.isclose(rho,(current-new)/pred,rel_tol=1e-12,abs_tol=1e-12)
   band=64*eps*max(1,abs(rho));want=.5 if valid and mode>=2 and rho>.75+band else (2 if valid and mode==3 and rho<.25-band else 1);assert fac==want
   old_l,old_t,new_l,new_t,pairfac=pairs[o];assert pairfac==fac
   floor=float(flags.get('OCA_LAM0','10'))*10**(-float(flags.get('OCA_LAM_FLOOR','8')))
   assert math.isclose(new_l,min(1e8,max(floor,old_l*fac)),rel_tol=1e-12)
   assert math.isclose(new_t,min(1e8,max(1e-7,old_t*fac)),rel_tol=1e-12)
   if o+1 in attempts:
    nxt=attempts[o+1];assert math.isclose(nxt['lam'],new_l,rel_tol=2e-6,abs_tol=1e-14),(row['name'],o,nxt['lam'],new_l)
    assert math.isclose(nxt['tau'],new_t,rel_tol=2e-6,abs_tol=1e-14),(row['name'],o,nxt['tau'],new_t);next_checks+=1
   models.append(dict(outer=o,rho=rho,factor=fac,valid=valid,ray_optimum_multiple=-slope/curv if curv>0 else None))
  assert len(models)==row.get('repair_calls',0) and len(pairs)==len(models)
  assert sum(x['factor']<1 for x in models)==row.get('repair_down',0)
  assert sum(x['factor']>1 for x in models)==row.get('repair_up',0)
  events.append(dict(stage=stage,name=row['name'],models=models))
 for scene in sorted({x['scene'] for x in rows}):
  for arm in sorted({x['arm'] for x in rows}):
   a=[x for x in rows if x['scene']==scene and x['arm']==arm]
   if not a:continue
   med=lambda k:statistics.median(x.get(k,0) for x in a)
   groups[f'{stage}/{scene}/{arm}']=dict(n=len(a),hits=sum(x.get('hit',False) for x in a),cross=statistics.median(x['crossing_seconds'] for x in a) if all(x.get('hit',False) for x in a) else None,cost=med('cost'),seconds=med('seconds'),matvecs=med('matvecs'),backtrack=med('backtrack'),rejects=med('rejects'),repair_calls=med('repair_calls'),repair_seconds=med('repair_seconds'),down=med('repair_down'),up=med('repair_up'),point_seconds=med('point_safe_seconds'),point_wins=med('point_safe_wins'))
for scene in ['venice-52','dubrovnik-88']:
 for arm in ['plain','frozen','relax']:
  a=[x for x in allrows if x['scene']==scene and x['arm']==arm]
  groups[f'pooled/{scene}/{arm}']=dict(n=len(a),hits=sum(x['hit'] for x in a),cross=statistics.median(x['crossing_seconds'] for x in a) if all(x['hit'] for x in a) else None,cost=statistics.median(x['cost'] for x in a),seconds=statistics.median(x['seconds'] for x in a))
summary=dict(runs=len(allrows),native_seconds=sum(x['seconds'] for x in allrows),max_cpu_error=max(x['audit_relerr'] for x in allrows),model_calls=sum(x.get('repair_calls',0) for x in allrows),invalid=sum(x.get('repair_invalid',0) for x in allrows),next_assembly_checks=next_checks,groups=groups)
(r/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(r/'model-audits.json').write_text(json.dumps(events,indent=2)+'\n');print(json.dumps(summary,indent=2))
