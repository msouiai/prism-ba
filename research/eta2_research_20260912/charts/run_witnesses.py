#!/usr/bin/env python3
"""Execute only the registered Brief2 conditional chart witness pre-test.

No GPU, optimizer rollout, anchor search, tau sweep, depth freezing or tuning.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time

import numpy as np

import reference

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'analysis'))
from audit_capture import load_capture_state,map_f64,read_native_rows,sanitize,error_stats

CASES=[('venice-52',rep) for rep in (0,1,2)]+[('final-3068',rep) for rep in (0,5,6)]+[('ladybug-1197',rep) for rep in (0,1,2)]
CHARTS=('euclidean','homogeneous','inverse_depth')
DIRECTIONS=('eta2','exact_clip')


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


@contextmanager
def timing_components():
    """Time existing reference assembly/setup, dense point solve and scoring.

    Instrumentation wraps calls without changing numerical arguments or results.
    One process runs one cell at a time, so no concurrent monkey-patching occurs.
    """
    times={'linear_solve_seconds':0.,'conditional_total_seconds':0.}
    original_solve=np.linalg.solve
    original_conditional=reference.conditional_point_solve
    def solve(*args,**kwargs):
        start=time.perf_counter()
        try:return original_solve(*args,**kwargs)
        finally:times['linear_solve_seconds']+=time.perf_counter()-start
    def conditional(*args,**kwargs):
        start=time.perf_counter()
        try:return original_conditional(*args,**kwargs)
        finally:times['conditional_total_seconds']+=time.perf_counter()-start
    np.linalg.solve=solve;reference.conditional_point_solve=conditional
    try:yield times
    finally:np.linalg.solve=original_solve;reference.conditional_point_solve=original_conditional


def top_concentration(values):
    absolute=abs(values);n=min(200,len(values));idx=np.argpartition(absolute,len(values)-n)[-n:] if n else np.array([],dtype=int)
    total=float(np.sum(absolute,dtype=np.longdouble));part=float(np.sum(absolute[idx],dtype=np.longdouble))
    return {'points':n,'absolute_sum':part,'signed_sum':float(np.sum(values[idx],dtype=np.longdouble)),
            'fraction_of_absolute_point_error':part/total if total>0 and np.isfinite(total) else None}


def run_cell(cameras,X,ci,pi,uv,dc,lam,radius,chart):
    begin=time.perf_counter()
    with timing_components() as times:
        ans=reference.evaluate_chart_step(cameras,X,ci,pi,uv,dc,lam,chart=chart,tau=lam,scene_radius=radius)
    elapsed=time.perf_counter()-begin
    point=ans['model_error_per_track']['point']
    out={'status':'ok','score_init':ans['score_init'],'cost':ans['costs']['full'],
         'true_decrease':ans['true_decrease'],'prediction':ans['pred'],'rho':ans['rho'],
         'point_equation_relative_residual':ans['linear_relative_residual'],
         'maximum_point_displacement':float(np.max(ans['euclidean_displacement'])),
         'fling_count':ans['fling_count'],'scene_radius':radius,
         'exact_infinity_count':ans['exact_infinity_count'],'near_infinity_count':ans['near_infinity_count'],
         'invalid_projection_observations':ans['invalid_projection_observations'],
         'cheirality_flip_observations':ans['cheirality_flip_observations'],
         'model_error':{name:error_stats(value) for name,value in ans['model_error_per_track'].items()},
         'top200_point_error':top_concentration(point),
         'assembly_and_setup_seconds':times['conditional_total_seconds']-times['linear_solve_seconds'],
         'linear_solve_seconds':times['linear_solve_seconds'],
         'scoring_and_diagnostics_seconds':elapsed-times['conditional_total_seconds'],
         'cpu_total_seconds':elapsed}
    del ans
    return out


def aggregate(rows):
    groups={}
    for row in rows:
        key=(row['scene'],row['capture_rep'],row['camera_direction'],row['chart'])
        groups.setdefault(key,[]).append(row)
    result=[]
    scalar=('score_init','cost','true_decrease','prediction','rho','cost_delta_pct_vs_euclidean',
            'point_equation_relative_residual','maximum_point_displacement','fling_count',
            'assembly_and_setup_seconds','linear_solve_seconds','scoring_and_diagnostics_seconds','cpu_total_seconds')
    for key,values in groups.items():
        out=dict(zip(('scene','capture_rep','camera_direction','chart'),key));out['repetitions']=len(values)
        good=[r for r in values if r['status']=='ok'];out['successful_diagnostics']=len(good)
        out['score_init_checks_pass']=all(r.get('score_init_agreement',False) for r in good) and len(good)==len(values)
        for metric in scalar:
            numbers=[r[metric] for r in good if isinstance(r.get(metric),(int,float)) and np.isfinite(r[metric])]
            if len(numbers)==len(values):
                out[metric+'_median']=statistics.median(numbers);out[metric+'_range']=[min(numbers),max(numbers)]
            else:out[metric+'_median']=None;out[metric+'_range']=None
        result.append(out)
    return result


def gates(aggregates):
    out={}
    for chart in CHARTS[1:]:
        cells=[r for r in aggregates if r['camera_direction']=='eta2' and r['chart']==chart]
        primary=[r for r in cells if not (r['scene']=='ladybug-1197' and r['capture_rep']>0)]
        valid=lambda r:r['successful_diagnostics']==3 and r['score_init_checks_pass'] and r.get('cost_delta_pct_vs_euclidean_median') is not None
        wins=[r for r in primary if valid(r) and r['cost_delta_pct_vs_euclidean_median']<-.15 and r['prediction_median']>0 and r['rho_median']>.1]
        losses=[r for r in primary if valid(r) and r['cost_delta_pct_vs_euclidean_median']>.15]
        failures=[r for r in primary if not valid(r)]
        families=sorted({r['scene'] for r in wins})
        short=lambda rs:[dict(scene=r['scene'],capture_rep=r['capture_rep'],cost_delta_pct=r.get('cost_delta_pct_vs_euclidean_median')) for r in rs]
        passed=len(wins)>=2 and len(families)>=2 and not losses and not failures
        out[chart]={'always_on_witness_gate_passed':passed,'winning_primary_states':short(wins),
                    'winning_families':families,'regressing_primary_states':short(losses),'failed_primary_cells':short(failures),
                    'rule':'cost improvement >0.15% at >=2 primary states and >=2 scene families, positive prediction/rho>.1, no >0.15% primary regression, all cells valid',
                    'scope':'screen for a native rollout, not a solver promotion or measured target-speed claim'}
    return out


def report_results(rows,outdir,manifest):
    aggs=aggregate(rows);gate=gates(aggs)
    result={'registered_protocol':manifest['protocol'],'row_count':len(rows),'expected_rows':162,
            'aggregates':aggs,'gates':gate,'scope':'CPU conditional witness pre-test, no optimizer trajectory and no GPU timing'}
    (outdir/'summary.json').write_text(json.dumps(sanitize(result),indent=2,allow_nan=False)+'\n')
    if aggs:
        with (outdir/'ledger.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(aggs[0]));w.writeheader();w.writerows(aggs)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=Path(__file__).with_name('results'))
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();outdir=args.output_dir;outdir.mkdir(parents=True,exist_ok=True)
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        if os.environ.get(key,'1')!='1':raise RuntimeError(f'{key} must be 1')
    start=time.perf_counter();baseline=reference.verify_frozen_baseline()
    protocol=ROOT/'PROTOCOL_02_PRETEST.md'
    manifest={'protocol':{'path':str(protocol),'sha256':sha(protocol),'registration_commit':'304f991'},
              'baseline':baseline,'source_sha256':sha(__file__),'reference_sha256':sha(Path(reference.__file__)),
              'configuration':{'charts':CHARTS,'directions':DIRECTIONS,'repetitions':3,'tau_rule':'tau=lambda',
                               'anchor_rule':'first original-order observation','camera_source_reference_rep':0,
                               'threads':1,'scene_radius_rule':'max_i ||C_i-mean(C)||2'},'capture_inputs':[]}
    existing=[]
    rowsfile=outdir/'rows.jsonl'
    if args.resume and rowsfile.exists():
        old=json.loads((outdir/'manifest.json').read_text())
        if old['source_sha256']!=manifest['source_sha256'] or old['reference_sha256']!=manifest['reference_sha256'] or old['protocol']!=manifest['protocol']:
            raise RuntimeError('Refusing resume with different source/protocol')
        existing=[json.loads(line) for line in rowsfile.read_text().splitlines() if line.strip()]
    elif rowsfile.exists():raise RuntimeError('Existing rows; use --resume rather than overwrite')
    completed={(r['scene'],r['capture_rep'],r['camera_direction'],r['chart'],r['rep']) for r in existing}
    rows=existing;balhash={}
    for scene,capture_rep in CASES:
        setup_begin=time.perf_counter();capture=ROOT/'evidence/collect'/f'{scene}-capture-{capture_rep}'
        bal=Path('/workspace/bal')/f'{scene}.txt'
        cameras,X,meta=load_capture_state(capture);ci,pi,uv,dims=reference.load_observations(bal)
        if dims!=(len(cameras.R),len(X),int(meta['nobs'])):raise ValueError('dimension mismatch')
        if scene not in balhash:balhash[scene]=sha(bal)
        audit=json.loads((ROOT/'analysis/results'/f'{scene}-{capture_rep}.json').read_text())
        initial=next(r for r in audit['rows'] if r['arm']=='eta2')['costs']['initial']
        centers=cameras.centers();radius=float(np.max(np.linalg.norm(centers-np.mean(centers,axis=0),axis=1)))
        native=read_native_rows(capture/'native_directions.csv')
        input_record={'scene':scene,'capture_rep':capture_rep,'bal_sha256':balhash[scene],
                      'state_sha256':{name:sha(capture/name) for name in ('R_state.f64','t_state.f64','X_state.f64','intr_state.f64','metadata.txt')},
                      'lambda':meta['lambda'],'scene_radius':radius,'setup_io_seconds':time.perf_counter()-setup_begin}
        manifest['capture_inputs'].append(input_record)
        (outdir/'manifest.json').write_text(json.dumps(sanitize(manifest),indent=2,allow_nan=False)+'\n')
        for direction in DIRECTIONS:
            path=capture/f'{direction}-0.step';step=map_f64(path,(9*dims[0]+3*dims[1],));dc=step[:9*dims[0]].reshape(dims[0],9)
            native_row=next(r for r in native if r['arm']==direction and r['rep']==0)
            for rep in range(3):
                euclidean=None
                for chart in CHARTS:
                    key=(scene,capture_rep,direction,chart,rep)
                    if key in completed:
                        row=next(r for r in rows if (r['scene'],r['capture_rep'],r['camera_direction'],r['chart'],r['rep'])==key)
                        if chart=='euclidean' and row['status']=='ok':euclidean=row['cost']
                        continue
                    row={'scene':scene,'capture_rep':capture_rep,'witness_role':'repeat_control' if scene=='ladybug-1197' and capture_rep>0 else 'primary',
                         'camera_direction':direction,'chart':chart,'rep':rep,'lambda':meta['lambda'],'tau':meta['lambda'],
                         'camera_source_sha256':sha(path),'native_full_direction_reference':native_row,
                         'source_certificate_scope':'source unclipped reduced solve only' if direction=='exact_clip' else 'native inexact direction'}
                    begin=time.perf_counter()
                    try:
                        row.update(run_cell(cameras,X,ci,pi,uv,dc,meta['lambda'],radius,chart))
                        row['score_init_agreement']=abs(row['score_init']-initial)<=1e-8+5e-10*max(1,initial)
                        row['score_init_cpu_baseline']=initial
                        if chart=='euclidean':euclidean=row['cost']
                        row['cost_delta_pct_vs_euclidean']=100*(row['cost']/euclidean-1) if euclidean and np.isfinite(euclidean) else None
                        row['cost_delta_pct_vs_native_full_direction']=100*(row['cost']/native_row['cost']-1)
                    except Exception as exc:
                        row.update(status='failed',error=type(exc).__name__+': '+str(exc),cpu_total_seconds=time.perf_counter()-begin,
                                   score_init_cpu_baseline=initial,score_init_agreement=False)
                    row=sanitize(row);rows.append(row);completed.add(key)
                    with rowsfile.open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n');f.flush()
                    report_results(rows,outdir,manifest)
                    print('CHART',scene,capture_rep,direction,chart,rep,'status',row['status'],'cost',row.get('cost'),
                          'delta_pct',row.get('cost_delta_pct_vs_euclidean'),'rho',row.get('rho'),'seconds',row['cpu_total_seconds'],flush=True)
    manifest['campaign_elapsed_seconds']=time.perf_counter()-start
    (outdir/'manifest.json').write_text(json.dumps(sanitize(manifest),indent=2,allow_nan=False)+'\n')
    summary=report_results(rows,outdir,manifest)
    print('COMPLETE',json.dumps(summary['gates']),flush=True)


if __name__=='__main__':main()
