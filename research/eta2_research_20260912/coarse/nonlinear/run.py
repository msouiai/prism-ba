#!/usr/bin/env python3
"""N=3 fixed-witness CPU nonlinear passenger coarse diagnostic."""
import argparse
import json
from pathlib import Path
import time
import numpy as np
import model as m

def run(capture,bal,rep):
    start=time.perf_counter();baseline=m.geometry.verify_baseline()
    meta=m.geometry.read_metadata(capture/'metadata.txt');nc,np_,no=[int(meta[k]) for k in ('ncam','npt','nobs')]
    shapes={'R_state.f64':(nc,3,3),'t_state.f64':(nc,3),'X_state.f64':(np_,3),'intr_state.f64':(3,nc),'E.f64':(nc,9),'Cdiag.f64':(np_,3)}
    data={name:m.geometry.read_array(capture/name,shape) for name,shape in shapes.items()}
    camera=m.charts.CameraState(data['R_state.f64'],data['t_state.f64'],data['intr_state.f64'].T);X=data['X_state.f64'];E=data['E.f64'];lam=meta['lambda']
    assert lam>0 and meta['tau']==lam and np.all(E>0)
    ci,pi,uv,dims=m.charts.load_observations(bal);assert dims==(nc,np_,no)
    manifest=json.loads((capture/'manifest.json').read_text());balhash=m.geometry.sha256(bal);assert balhash==manifest['input_sha256']
    rows=m.audit.read_native_rows(capture/'native_directions.csv');control=next(row for row in rows if row['arm']=='eta2' and row['rep']==0)
    labels,clustering=m.geometry.cluster_centers(camera.centers(),8);membership=m.anchors(ci,pi,np_,labels)
    floor=lam*np.sum(data['Cdiag.f64'],axis=1)/3;floor=np.where(floor>0,floor,1e-32)
    Dp=np.maximum(lam*data['Cdiag.f64'],1e-3*floor[:,None])/lam
    blocks,rank=m.fixed_metric(camera,X,E,Dp,labels,membership)
    setup_seconds=time.perf_counter()-start
    result,_,_=m.episode(camera,X,E,ci,pi,uv,labels,membership,blocks,rank,lam,meta['radius'])
    gain=result['cumulative']['gain'];ratio=gain/control['decrease']
    serial_blocks=[{k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in b.items() if k not in ('cameras','points','T')} | dict(ncamera=len(b['cameras']),npoint=len(b['points'])) for b in blocks]
    result.update(kind='registered nonlinear passenger-cluster witness pretest',capture=str(capture),rep=rep,metadata=meta,baseline=baseline,
                  rank=rank,clustering=clustering,basis=serial_blocks,unobserved_points=int(np.sum(membership<0)),setup_cpu_seconds=setup_seconds,
                  total_cpu_seconds=time.perf_counter()-start,eta2_native_gain=control['decrease'],gain_over_eta2=ratio,mechanism_gate=bool(gain>2*control['decrease']),
                  score_init_relative_error=abs(result['cumulative']['score_init']-meta['cost'])/max(1.,abs(meta['cost'])),
                  protocol_sha256=m.geometry.sha256(m.CAMPAIGN/'PROTOCOL_09_NONLINEAR.md'),
                  input_sha256={**{name:m.geometry.sha256(capture/name) for name in shapes},'metadata.txt':m.geometry.sha256(capture/'metadata.txt'),'BAL':balhash},
                  implementation_sha256={p.name:m.geometry.sha256(p) for p in (Path(__file__),Path(m.__file__),m.HERE/'IMPLEMENTATION_NOTES.md')},
                  baseline_numerical_qualification='Original mismatches retained in analysis/retained_mismatches.json; coherent coarse model does not replace compact champion operator.',
                  limitation='Deterministic fixed-state CPU N3, not independent trajectories, endpoint quality, hit-rate or GPU speed.')
    if result['score_init_relative_error']>1e-10:raise ValueError('captured full objective parity failed')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True);p.add_argument('--bal',type=Path,required=True);p.add_argument('--rep',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    r=run(a.capture,a.bal,a.rep);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:r[k] for k in ('capture','rep','rank','eta2_native_gain','gain_over_eta2','mechanism_gate','total_cpu_seconds')} | dict(cumulative=r['cumulative'],attempts=[dict(iteration=x['iteration'],decrement=x['decrement'],accepted=x['accepted'],trials=x['trials']) for x in r['attempts']]),indent=2))
