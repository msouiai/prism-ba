#!/usr/bin/env python3
"""Complete and score every D15 camera solution on the archived full objective."""
from __future__ import annotations
import hashlib, importlib.util, json, pathlib, re, sys, time
import numpy as np

HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[2]
ARCHIVE=ROOT/'research/eta2_research_20260912/evidence/collect'
CAPTURE=pathlib.Path('/workspace/prism-wave6-d15')
sys.path[:0]=[str(ROOT/'research/eta2_wave2'),str(ROOT/'research/eta2_research_20260912/analysis'),str(ROOT/'research/eta2_research_20260912/coarse')]
from audit_capture import load_capture_state,CHART
from diagnostic import read_array
from spectrum import point_qr,point_inverse

spec=importlib.util.spec_from_file_location('d15_score_core',ROOT/'research/eta2_research_20260912/separable_rescue/core.py')
S=importlib.util.module_from_spec(spec);sys.modules[spec.name]=S;spec.loader.exec_module(S)

def sha(path):
    with pathlib.Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def aggregate(x,ids,n):
    flat=x.reshape(len(x),-1)
    return np.column_stack([np.bincount(ids,weights=flat[:,k],minlength=n) for k in range(flat.shape[1])]).reshape((n,)+x.shape[1:])

def camera_gate(ci,pi,nc):
    pairs=np.unique(ci.astype(np.int64)*(int(pi.max())+1)+pi)
    counts=np.bincount((pairs//(int(pi.max())+1)).astype(np.int64),minlength=nc)
    med=float(np.median(counts));q=(nc+99)//100
    order=sorted(range(nc),key=lambda c:(int(counts[c]),c))
    gate=np.zeros(nc,dtype=bool)
    for c in order[:q]:gate[c]=counts[c]<med/4
    return gate,counts,med

def score_rep(rep):
    start=time.perf_counter();source=ARCHIVE/f'final-3068-capture-{rep}';camera,X,meta=load_capture_state(source)
    nc,np_=len(camera.R),len(X);ci,pi,uv,dims=CHART.load_observations('/workspace/bal/final-3068.txt');assert dims==(nc,np_,len(ci))
    gate,counts,median_count=camera_gate(ci,pi,nc);E=read_array(source/'E.f64',(nc,9));cd=read_array(source/'Cdiag.f64',(np_,3))
    chart=CHART.make_chart(X,camera,'euclidean');r,Jc,Jp,_=CHART.observation_jacobians(camera,chart.H,chart.T,ci,pi,uv)
    diag=np.maximum(cd,.001*np.maximum(cd.mean(axis=1),1e-32)[:,None]);point_diag=meta['tau']*diag
    _,Ri,_=point_qr(Jp,pi,point_diag)
    def complete(z):
        dc=E*z;yc=np.einsum('nri,ni->nr',Jc,dc[ci]);rhs=aggregate(np.einsum('nri,nr->ni',Jp,r+yc),pi,np_)
        return dc,-point_inverse(Ri,rhs)
    folder=CAPTURE/f'final-3068-{rep}'/'prior-solutions';arms=['0','1','10','100','inf'];rows=[];raws={}
    for arm in arms:
        for run in range(3):
            stored=np.fromfile(folder/f'solution-a{arm}-r{run}.f64',dtype='<f8').reshape(nc,9)
            z=-stored;raws[(arm,run)]=z
    base=raws[('0',0)];base_free=float(np.linalg.norm(base[~gate]));base_gate=float(np.sum(base[gate]*base[gate]));base_total=float(np.sum(base*base))
    archived=-read_array(source/'eta2_raw_scaled.f64',(nc,9));direction_replay_error=float(np.linalg.norm(base-archived)/max(np.linalg.norm(archived),1e-300))
    archived_result=json.loads((source/'result.json').read_text());native=next(x for x in archived_result['directions'] if x['arm']=='eta2')
    for arm in arms:
        for run in range(3):
            z=raws[(arm,run)];raw_norm=float(np.linalg.norm(z));factor=min(1.,meta['radius']/max(raw_norm,1e-300));zc=z*factor;dc,dp=complete(zc);audit=S.audit(camera,X,ci,pi,uv,dc,dp,E)
            free=float(np.linalg.norm(z[~gate]));gate_energy=float(np.sum(z[gate]*z[gate]));total=float(np.sum(z*z))
            rows.append({'witness':rep,'arm':arm,'run':run,'raw_norm':raw_norm,'radius':meta['radius'],'raw_radius_ratio':raw_norm/meta['radius'],
                'global_clip_factor':factor,'gated_energy_fraction':gate_energy/max(total,1e-300),'ungated_raw_norm':free,
                'ungated_norm_retention':free/max(base_free,1e-300),'ungated_direction_cosine':float(np.sum(z[~gate]*base[~gate])/max(free*base_free,1e-300)),
                **{k:(v if not isinstance(v,float) or np.isfinite(v) else None) for k,v in audit.items()}})
    baseline=next(x for x in rows if x['arm']=='0' and x['run']==0)
    validation={'direction_replay_relative_error':direction_replay_error,
        'archived_native_decrease':float(native['decrease']),'replayed_decrease':baseline['true_decrease'],
        'decrease_absolute_error':abs(float(native['decrease'])-baseline['true_decrease']),
        'decrease_relative_error':abs(float(native['decrease'])-baseline['true_decrease'])/max(abs(float(native['decrease'])),1e-300),
        'initial_cost_relative_error':abs(baseline['score_init']-meta['cost'])/max(abs(meta['cost']),1.),
        'base_gated_energy_fraction':base_gate/max(base_total,1e-300)}
    if validation['initial_cost_relative_error']>1e-8 or (validation['decrease_absolute_error']>1e-6 and validation['decrease_relative_error']>1e-6):
        raise RuntimeError(('invalid D15 replay',rep,validation))
    return {'witness':rep,'metadata':meta,'gate_count':int(gate.sum()),'gate_ids':np.flatnonzero(gate).tolist(),
        'gate_counts':counts[gate].tolist(),'median_count':median_count,'validation':validation,'rows':rows,'seconds':time.perf_counter()-start}

def summarize(results):
    by={rep:{arm:next(x for x in result['rows'] if x['arm']==arm and x['run']==0) for arm in ['0','1','10','100','inf']}
        for rep,result in results.items()}
    dose_checks={}
    for arm in ['1','10','100']:
        checks={}
        for rep in [0,5,6]:
            base,row=by[rep]['0'],by[rep][arm]
            relative=(row['true_decrease']-base['true_decrease'])/max(abs(base['true_decrease']),1e-6)
            checks[str(rep)]={'relative_true_decrease_gain':relative,'rho_delta':row['rho']-base['rho'],
                'ungated_norm_retention':row['ungated_norm_retention'],'raw_radius_ratio':row['raw_radius_ratio'],
                'passes_high_ratio':rep not in (5,6) or (relative>.0015 and row['rho']>=base['rho']-1e-12 and row['ungated_norm_retention']>=.95),
                'passes_witness0':rep!=0 or abs(relative)<=.0015}
        dose_checks[arm]=checks
    selected=None
    for arm in ['1','10','100']:
        if all(dose_checks[arm][str(rep)]['passes_high_ratio'] and dose_checks[arm][str(rep)]['passes_witness0'] for rep in [0,5,6]):selected=arm;break
    compact=[]
    for rep in [0,5,6]:
        for arm in ['0','1','10','100','inf']:
            x=by[rep][arm];compact.append({k:x[k] for k in ['witness','arm','raw_radius_ratio','gated_energy_fraction','ungated_norm_retention','true_decrease','prediction','rho','cost']})
    return {'selected_finite_dose':selected,'fixed_gate_passed':selected is not None,'native_arm_earned':selected is not None,
        'dose_checks':dose_checks,'compact_rows':compact,
        'decision':'advance selected finite dose to native gate' if selected else 'stop count-gated prior at fixed-state negative'}

def main():
    results={rep:score_rep(rep) for rep in [0,5,6]};summary=summarize(results)
    provenance={'protocol_sha256':sha(ROOT/'research/eta2_wave6/D15_COUNT_PRIOR_PROTOCOL.md'),
        'capture_manifest_sha256':sha(HERE/'capture-manifest.json'),'build_manifest_sha256':sha(HERE/'build-manifest.json'),
        'fixed_run_manifest_sha256':sha(HERE/'fixed-run-manifest.json')}
    (ROOT/'research/eta2_wave6/d15-count-prior-results.json').write_text(json.dumps({'provenance':provenance,'witnesses':results},indent=2)+'\n')
    (ROOT/'research/eta2_wave6/d15-count-prior-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
