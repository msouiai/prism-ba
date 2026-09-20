#!/usr/bin/env python3
"""Aggregate retained online experiments without treating misses as speedups."""
import pathlib,json,statistics,re,math
r=pathlib.Path('/workspace/prism-point-safeguard');rows=[];groups={};events=[]
for stage in ['sanity','medium','prospective','off-repeat','refinement']:
 data=json.loads((r/stage/'results.json').read_text());rows+=data
 for x in data:
  text=(r/stage/(x['name']+'.log')).read_text()
  parsed=[]
  for m in re.finditer(r'POINT_SAFE o=(\d+) frozen=(\d+) slope=(\S+) candidate=(\S+) original=(\S+) current=(\S+) won=(\d+)',text):
   o,frozen=int(m[1]),int(m[2]);slope,candidate,original,current=map(float,m.group(3,4,5,6));won=int(m[7]);valid=math.isfinite(candidate) and math.isfinite(slope) and slope<0 and candidate<current and candidate<=current+1e-4*slope and candidate<original
   assert bool(won)==valid,(stage,x['name'],o)
   parsed.append(dict(outer=o,frozen=frozen,slope=slope,candidate=candidate,original=original,current=current,won=won))
  assert len(parsed)==x.get('point_safe_calls',0)
  assert sum(z['won'] for z in parsed)==x.get('point_safe_wins',0)
  d=[dict(outer=int(o),slots=int(sl),lam=float(l),tau=float(t),rescued=int(res)) for o,sl,l,t,res in re.findall(r'DEMAND accept o=(\d+) slots=(\d+) lambda=(\S+) tau=(\S+) rescued=(\d+)',text)]
  events.append(dict(stage=stage,name=x['name'],proposals=parsed,demand=d))
 if stage in ['medium','refinement']:
  for scene in sorted({x['scene'] for x in data}):
   for arm in sorted({x['arm'] for x in data}):
    for mode in sorted({x['safeguard'] for x in data}):
     a=[x for x in data if x['scene']==scene and x['arm']==arm and x['safeguard']==mode]
     if not a:continue
     med=lambda k:statistics.median(x.get(k,0) for x in a)
     key=f'{stage}/{scene}/{arm}/{mode}';groups[key]=dict(n=len(a),hits=sum(x['hit'] for x in a),cross=statistics.median(x['crossing_seconds'] for x in a) if all(x['hit'] for x in a) else None,cost=med('cost'),seconds=med('seconds'),rejects=med('rejects'),matvecs=med('matvecs'),backtrack=med('backtrack'),calls=med('point_safe_calls'),wins=med('point_safe_wins'),point_seconds=med('point_safe_seconds'))
summary=dict(groups=groups,runs=len(rows),native_seconds=sum(x['seconds'] for x in rows),max_cpu_error=max(x['audit_relerr'] for x in rows),proposal_calls=sum(x.get('point_safe_calls',0) for x in rows),proposal_wins=sum(x.get('point_safe_wins',0) for x in rows))
(r/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(r/'event-audits.json').write_text(json.dumps(events,indent=2)+'\n');print(json.dumps(summary,indent=2))
