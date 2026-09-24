#!/usr/bin/env python3
import pathlib,json,re,csv,statistics
from profile_iterations import sha
from cached_benchmark_input import load_input
from audit_prism_state import audit
ROOT=pathlib.Path('/workspace/prism-tr-recurrence')
def main():
 cache={};rows=[];errors=[];summaries={}
 for phase,total in [('recurrence',16),('confirmation',31)]:
  folder=ROOT/phase
  if not (folder/'results.json').exists():continue
  rr=json.loads((folder/'results.json').read_text());assert len(rr)==total
  proto=json.loads((folder/'protocol.json').read_text());assert sha(ROOT/'source.cu')==proto['source_sha256'];assert sha(ROOT/'prism')==proto['binary_sha256']
  for p,h in proto['headers'].items():assert sha(p)==h
  for r in rr:
   scene=r['scene'];stem=folder/(scene+'-mode'+str(r['mode'])+'-rep'+str(r['rep']))
   if scene not in cache:cache[scene]=load_input(pathlib.Path('/workspace/bal')/(scene+'.txt'),'/workspace/prism-caspar-expanded/cpu-cache')
   dh,(dims,obs),initial=cache[scene];assert dh==proto['data_sha256'][scene]
   cost=audit(stem.with_suffix('.state'),dims,obs);assert abs(cost-r['cost'])<1e-10*max(1,cost)
   with stem.with_suffix('.csv').open() as f:trace=list(csv.DictReader(l for l in f if not l.startswith('#')))
   assert abs(float(trace[0]['cost'])-initial)<1e-7*initial and abs(float(trace[-1]['cost'])-cost)<1e-7*cost
   assert all(float(b['cost'])<=float(a['cost'])*(1+1e-10) for a,b in zip(trace,trace[1:]))
   log=stem.with_suffix('.log').read_text();calls=re.search(r'TR_RECURRENCE_SUMMARY candidates=(\d+)',log)
   r['avoided_candidate_matvecs']=int(calls[1]) if calls else 0
   for line in log.splitlines():
    if line.startswith('TR_RECURRENCE o='):e=float(re.search(r'error=(\S+)',line)[1]);assert e<=1e-7;errors.append(e)
    if line.startswith('CAMERA_TR o='):
     v={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)}
     if v['accept']:assert v['rho']>=.1 and v['prediction']>0 and v['norm']<=v['radius']*(1+1e-8)
   manifest=json.loads(stem.with_suffix('.manifest.json').read_text())
   if r['rep']>0:assert not any(k in manifest['flags'] for k in ['OCA_LEARN_LOG','OCA_PROFILE','OCA_TR_RECURRENCE_AUDIT'])
   rows.append(dict(r,phase=phase))
  sm={}
  for scene in sorted(set(r['scene'] for r in rr)):
   arms={}
   for mode in [0,1]:
    a=[r for r in rr if r['scene']==scene and r['mode']==mode and r['rep']>0];times=[r['crossing'] for r in a if r['hit']]
    if not a:continue
    arms[str(mode)]=dict(hits=len(times),runs=len(a),median=statistics.median(times) if len(times)==len(a) else None,range=[min(times),max(times)] if times else None,matvecs=statistics.median(r['matvecs'] for r in a),avoided=statistics.median(r['avoided_candidate_matvecs'] for r in a),rejects=[r['rejects'] for r in a])
   if len(arms)==2:
    wins=sum(next(r for r in rr if r['scene']==scene and r['mode']==1 and r['rep']==rep)['crossing']<next(r for r in rr if r['scene']==scene and r['mode']==0 and r['rep']==rep)['crossing'] for rep in range(1,arms['0']['runs']+1))
    sm[scene]=dict(arms=arms,paired_wins=wins,speedup=arms['0']['median']/arms['1']['median'] if arms['0']['median'] and arms['1']['median'] else None)
  summaries[phase]=sm
 out=dict(endpoints=len(rows),native_seconds=sum(r['native'] for r in rows),process_seconds=sum(r['wall'] for r in rows),max_cost_error=max(r['audit_error'] for r in rows),curvature_checks=len(errors),max_curvature_error=max(errors),summaries=summaries)
 (ROOT/'verification.json').write_text(json.dumps(out,indent=2));(ROOT/'annotated-results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(out,indent=2))
if __name__=='__main__':main()
