#!/usr/bin/env python3
"""Audit the one/five-shift trust-region ablation."""
import json,pathlib,re,statistics
from expanded_caspar_screen import sha,write
from camera_tr_width_study import ROOT,SCENES
def main():
 p=json.loads((ROOT/'protocol.json').read_text());rows=json.loads((ROOT/'results.json').read_text())
 assert len(rows)==16 and [r['name'] for r in rows]==[j['name'] for j in p['jobs']]
 for name,h in p['tooling_sha256'].items():assert sha(name)==h and sha(ROOT/'tooling'/pathlib.Path(name).name)==h
 for a,b in p['binaries'].items():assert sha(b)==p['binary_sha256'][a]
 assert sha(ROOT/'source-tr.cu')==p['source_sha256']
 assert sha(ROOT/'source-before.cu')==sha('/workspace/prism-camera-tr/source-tr.cu')
 assert sha('/workspace/prism-camera-tr/source-before.cu')==sha(pathlib.Path(__file__).parents[1]/'gpu/oca_cuda.cu')
 assert len(set(p['binary_sha256'].values()))==1
 before=(ROOT/'source-before.cu').read_text()
 expected=before.replace('L!=5 || demand_mode!=0 || full_model_rho || repair_damping_mode || point_trust_mode ||','(L!=1 && L!=5) || demand_mode!=0 || full_model_rho || repair_damping_mode || point_trust_mode ||').replace('camera TR requires plain FP64 diagonal five-shift mode with point safeguard 1','camera TR requires plain FP64 diagonal one/five-shift mode with point safeguard 1')
 assert (ROOT/'source-tr.cu').read_text()==expected
 for scene,h in p['data_sha256'].items():assert sha(pathlib.Path('/workspace/bal')/(scene+'.txt'))==h
 for r,j in zip(rows,p['jobs']):
  assert all(r[k]==v for k,v in j.items())
  m=json.loads((ROOT/(r['name']+'.manifest.json')).read_text())
  assert m['job']==j and m['binary_sha256']==p['binary_sha256'][j['arm']]
  assert m['data_sha256']==p['data_sha256'][j['scene']]
  flags=dict(p['flags'],OCA_NSHIFTS='1' if j['arm']=='tr1' else '5',OCA_TARGET_COST=str(j['target']),OCA_MAX_SECONDS=str(j['cap']))
  if j['arm'] in ['tr1','tr5']:flags['OCA_CAMERA_TR']='1'
  assert flags==m['flags'] and r['audit_error']<1e-7
  assert r['hit']==(r['crossing'] is not None and r['crossing']<=r['cap'] and r['cost']<=r['target']*(1-1e-8))
  log=(ROOT/(r['name']+'.log')).read_text()
  ps=re.search(r'POINT_SAFE summary calls=(\d+) evals=(\d+) wins=(\d+)',log);assert ps
  r.update(point_calls=int(ps[1]),point_evals=int(ps[2]),point_wins=int(ps[3]),state_sha256=sha(ROOT/(r['name']+'.state')))
  if j['arm'] in ['tr1','tr5']:
   assert len(r['tr_trace'])==r['accepts']+r['rejects']
   assert sum(x['accept'] for x in r['tr_trace'])==r['accepts']
   assert sum(x['reuse'] for x in r['tr_trace'])==r['reuses']
   for d in r['tr_trace']:
    assert 0<d['radius'] and 0<d['next_radius'] and d['bank']<=64
    if d['accept']:assert d['norm']<=d['radius']*(1+1e-8) and d['rho']>=.1 and d['prediction']>0
   assert r['model_matvecs']<=r['matvecs']
  r['initial_radius']=r['tr_trace'][0]['radius']
  r['lambda_trace']=[float(v) for v in re.findall(r'MFCG it\s+\d+ cost=\S+ lam=(\S+)',log)]
  r['gain_per_native_second']=(r['initial']-r['cost'])/r['seconds']
 cells=[]
 for scene,_ in SCENES:
  for arm in ['tr1','tr5']:
   rr=[r for r in rows if not r['sanity'] and r['scene']==scene and r['arm']==arm];assert len(rr)==3
   hits=[r['crossing'] for r in rr if r['hit']]
   c=dict(scene=scene,arm=arm,hits=len(hits),median_crossing=statistics.median(hits) if len(hits)==3 else None,crossing_range=[min(hits),max(hits)] if hits else None)
   for k in ['cost','seconds','process_wall','accepts','matvecs','model_matvecs','total_scored','full_predictions','point_calls','point_evals','point_wins','gain_per_native_second']:c['median_'+k]=statistics.median(r[k] for r in rr)
   c['initial_radius_range']=[min(r['initial_radius'] for r in rr),max(r['initial_radius'] for r in rr)]
   c['last_logged_lambda_values']=[r['lambda_trace'][-1] if r['lambda_trace'] else None for r in rr]
   c['rejects']=sum(r['rejects'] for r in rr);c['reuses']=sum(r['reuses'] for r in rr);cells.append(c)
 summary=dict(cells=cells,native_measurement_seconds=sum(r['seconds'] for r in rows if not r['sanity']),native_sanity_seconds=sum(r['seconds'] for r in rows if r['sanity']),max_audit_error=max(r['audit_error'] for r in rows),max_accepted_radius_ratio=max(d['norm']/d['radius'] for r in rows for d in r['tr_trace'] if d['accept']))
 write(ROOT/'annotated-results.json',rows);write(ROOT/'summary.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
