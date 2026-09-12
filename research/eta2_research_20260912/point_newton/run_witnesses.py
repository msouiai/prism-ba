#!/usr/bin/env python3
"""Run only registered PROTOCOL_08's 54 conditional CPU witness tests."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import statistics
import time
import numpy as np
from core import ROOT,CHART,evaluate
from audit_capture import load_capture_state,map_f64,sanitize,error_stats

P=Path(__file__).resolve().parent
CASES=[('venice-52',r) for r in (0,1,2)]+[('final-3068',r) for r in (0,5,6)]+[('ladybug-1197',r) for r in (0,1,2)]
DIRECTIONS=('eta2','exact_clip')


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def write(p,value):p.write_text(json.dumps(sanitize(value),indent=2,allow_nan=False)+'\n')


def evaluate_cell(cameras,X,ci,pi,uv,dc,lam,radius):
    start=time.perf_counter()
    a=evaluate(cameras,X,ci,pi,uv,dc,lam,tau=lam,scene_radius=radius)
    cpu=time.perf_counter()-start
    counts=np.bincount(pi,minlength=len(X))
    masks={name:dict(points=int(np.count_nonzero(mask)),point_fraction=float(np.mean(mask)),
                    observations=int(np.sum(counts[mask])),observation_fraction=float(np.sum(counts[mask])/len(ci)))
           for name,mask in a['masks'].items()}
    Xnew=CHART.euclidean_from_homogeneous(a['H_candidate'])
    center=np.mean(cameras.centers(),axis=0)
    oldrad=np.linalg.norm(X-center,axis=1);newrad=np.linalg.norm(Xnew-center,axis=1)
    inward=newrad<oldrad;large=a['euclidean_displacement']>radius
    out=dict(status='ok',score_init=a['score_init'],cost=a['costs']['full'],
       true_decrease=a['true_decrease'],prediction_gn=a['prediction_gn'],prediction_hybrid=a['prediction_hybrid'],
       rho_gn=a['rho_gn'],rho_hybrid=a['rho_hybrid'],
       accepted_by_gn_checks=bool(a['true_decrease']>0 and a['prediction_gn']>0 and a['rho_gn']>.1),
       accepted_by_hybrid_checks=bool(a['true_decrease']>0 and a['prediction_hybrid']>0 and a['rho_hybrid']>.1),
       active_second_order_model_term=a['active_second_order_model_term'],
       masks=masks,point_equation_relative_residual=a['linear_relative_residual'],
       point_equation_whitened_relative_residual=a['linear_whitened_relative_residual'],
       maximum_point_normwise_backward_error=a['maximum_point_normwise_backward_error'],
       model_error_gn={k:error_stats(v) for k,v in a['model_error_per_track'].items()},
       model_error_hybrid={k:error_stats(v) for k,v in a['model_error_hybrid_per_track'].items()},
       scene_radius=radius,maximum_point_displacement=float(np.max(a['euclidean_displacement'])),
       median_point_displacement=float(np.median(a['euclidean_displacement'])),
       large_moves=int(np.count_nonzero(large)),large_moves_inward=int(np.count_nonzero(large & inward)),
       large_moves_outward=int(np.count_nonzero(large & ~inward)),
       all_moves_inward=int(np.count_nonzero(inward)),all_moves_outward=int(np.count_nonzero(newrad>oldrad)),
       maximum_old_point_radius=float(np.max(oldrad)),maximum_new_point_radius=float(np.max(newrad)),
       invalid_projection_observations=a['invalid_projection_observations'],
       cheirality_flip_observations=a['cheirality_flip_observations'],
       assembly_seconds=a['assembly_seconds'],spd_decision_seconds=a['spd_decision_seconds'],
       linear_solve_seconds=a['linear_solve_seconds'],scoring_and_diagnostics_seconds=cpu-a['cpu_solve_seconds'],
       cpu_total_seconds=cpu)
    return out


def summarize(rows,outdir):
    groups={}
    for row in rows:groups.setdefault((row['scene'],row['capture_rep'],row['camera_direction']),[]).append(row)
    cells=[]
    for key,rr in groups.items():
        good=[r for r in rr if r['status']=='ok']
        cell=dict(zip(('scene','capture_rep','camera_direction'),key));cell.update(repetitions=len(rr),valid=len(good))
        if good:
            for field in ('cost','true_decrease','prediction_gn','prediction_hybrid','rho_gn','rho_hybrid',
                          'cost_delta_pct_vs_euclidean','cpu_total_seconds','point_equation_relative_residual',
                          'point_equation_whitened_relative_residual','maximum_point_normwise_backward_error'):
                values=[r[field] for r in good]
                cell[field+'_median']=statistics.median(values)
                cell[field+'_min']=min(values);cell[field+'_max']=max(values)
            cell.update(fallback_point_fraction=good[0]['masks']['fallback']['point_fraction'],
                        fallback_observation_fraction=good[0]['masks']['fallback']['observation_fraction'],
                        raw_indefinite_point_fraction=good[0]['masks']['raw_indefinite']['point_fraction'],
                        hybrid_accepts=sum(r['accepted_by_hybrid_checks'] for r in good),
                        model_agreement_improved=all(r['hybrid_model_agreement_improved'] for r in good),
                        large_moves_inward=good[0]['large_moves_inward'],large_moves_outward=good[0]['large_moves_outward'])
        cells.append(cell)
    primary=[r for r in rows if r['status']=='ok' and r['witness_role']=='primary']
    lady=[r for r in primary if r['scene']=='ladybug-1197']
    regressions=[(r['scene'],r['capture_rep'],r['camera_direction'],r['rep'],r['cost_delta_pct_vs_euclidean'])
                 for r in primary if r['cost_delta_pct_vs_euclidean']>.15]
    result=dict(expected_rows=54,completed_rows=len(rows),valid_rows=sum(r['status']=='ok' for r in rows),cells=cells,
                primary_regressions_over_015pct=regressions,
                ladybug_fallback_over_5pct=any(r['masks']['fallback']['point_fraction']>.05 for r in lady),
                ladybug_accepted_improved_model_all_directions=bool(lady) and all(r['accepted_by_hybrid_checks'] and r['hybrid_model_agreement_improved'] for r in lady),
                score_init_checks_passed=all(r.get('score_init_agreement',False) for r in rows),
                total_registered_cpu_seconds=sum(r.get('cpu_total_seconds',0) for r in rows),
                scope='Conditional fixed-camera point solver; no native trajectory, GPU timing, or hit-rate claim')
    result['complete']=len(rows)==54
    result['screen_killed']=result['complete'] and (len(regressions)>0 or result['ladybug_fallback_over_5pct'] or not result['ladybug_accepted_improved_model_all_directions'])
    write(outdir/'summary.json',result)
    if cells:
        keys=list(dict.fromkeys(k for row in cells for k in row))
        with (outdir/'ledger.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(cells)
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--resume',action='store_true');args=ap.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        if os.environ.get(key,'1')!='1':raise RuntimeError(f'{key} must be 1')
    verification=json.loads((P/'verification.json').read_text());assert verification['status']=='passed'
    baseline=CHART.verify_frozen_baseline();outdir=P/'results';outdir.mkdir(exist_ok=True)
    control_path=ROOT/'charts/results/rows.jsonl'
    controls=[json.loads(x) for x in control_path.read_text().splitlines() if x.strip()]
    controls={(r['scene'],r['capture_rep'],r['camera_direction'],r['rep']):r for r in controls if r['chart']=='euclidean'}
    assert len(controls)==54
    manifest=dict(protocol_sha256=sha(ROOT/'PROTOCOL_08.md'),registration_commit='ddf798c',
                  baseline=baseline,verification_sha256=sha(P/'verification.json'),
                  source_sha256={n:sha(P/n) for n in ('core.py','run_witnesses.py','verify.py')},
                  scoring_reference_sha256=sha(ROOT/'charts/reference.py'),
                  immutable_euclidean_controls_sha256=sha(control_path),
                  config=dict(repetitions=3,camera_directions=DIRECTIONS,threads=1,tau_equals_lambda=True,
                    spd_threshold=1e-12,fallback='original damped GN block',objective='full SIMPLE_RADIAL k2=0 original observations'),
                  capture_inputs=[])
    rowfile=outdir/'rows.jsonl';rows=[]
    if rowfile.exists():
        if not args.resume:raise RuntimeError('Use --resume rather than overwrite results')
        old=json.loads((outdir/'manifest.json').read_text())
        for k in ('protocol_sha256','source_sha256','scoring_reference_sha256','immutable_euclidean_controls_sha256'):
            assert old[k]==manifest[k],f'resume mismatch: {k}'
        rows=[json.loads(x) for x in rowfile.read_text().splitlines() if x.strip()]
    completed={(r['scene'],r['capture_rep'],r['camera_direction'],r['rep']) for r in rows}
    bal_cache={};begin=time.perf_counter()
    for scene,capture_rep in CASES:
        capture=ROOT/'evidence/collect'/f'{scene}-capture-{capture_rep}'
        cameras,X,meta=load_capture_state(capture)
        if scene not in bal_cache:
            bal=Path('/workspace/bal')/(scene+'.txt')
            bal_cache[scene]=(*CHART.load_observations(bal),sha(bal))
        ci,pi,uv,dims,bal_sha=bal_cache[scene]
        assert dims==(len(cameras.R),len(X),int(meta['nobs']))
        centers=cameras.centers();radius=float(np.max(np.linalg.norm(centers-np.mean(centers,axis=0),axis=1)))
        manifest['capture_inputs'].append(dict(scene=scene,capture_rep=capture_rep,bal_sha256=bal_sha,
          state_sha256={n:sha(capture/n) for n in ('R_state.f64','t_state.f64','X_state.f64','intr_state.f64','metadata.txt')},lambda_value=meta['lambda']))
        write(outdir/'manifest.json',manifest)
        for direction in DIRECTIONS:
            step_path=capture/f'{direction}-0.step';step=map_f64(step_path,(9*dims[0]+3*dims[1],));dc=step[:9*dims[0]].reshape(dims[0],9)
            for rep in range(3):
                key=(scene,capture_rep,direction,rep)
                if key in completed:continue
                control=controls[key];assert control['status']=='ok' and control['camera_source_sha256']==sha(step_path)
                row=dict(scene=scene,capture_rep=capture_rep,camera_direction=direction,rep=rep,
                         witness_role='repeat_control' if scene=='ladybug-1197' and capture_rep>0 else 'primary',
                         lambda_value=meta['lambda'],camera_source_sha256=sha(step_path),
                         euclidean_control=dict(cost=control['cost'],prediction=control['prediction'],rho=control['rho'],
                           point_model_error=control['model_error']['point'],score_init=control['score_init'],
                           cpu_total_seconds=control['cpu_total_seconds']))
                start=time.perf_counter()
                try:
                    row.update(evaluate_cell(cameras,X,ci,pi,uv,dc,meta['lambda'],radius))
                    row['score_init_agreement']=abs(row['score_init']-control['score_init'])<=1e-8+5e-10*max(1,control['score_init'])
                    row['cost_delta_pct_vs_euclidean']=100*(row['cost']/control['cost']-1)
                    row['hybrid_model_agreement_improved']=abs(1-row['rho_hybrid'])<abs(1-control['rho'])
                    row['gn_model_agreement_improved']=abs(1-row['rho_gn'])<abs(1-control['rho'])
                    assert row['score_init_agreement'],'initial objective mismatch'
                except Exception as exc:
                    row.update(status='failed',error=f'{type(exc).__name__}: {exc}',cpu_total_seconds=time.perf_counter()-start)
                row=sanitize(row);rows.append(row);completed.add(key)
                with rowfile.open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n')
                summarize(rows,outdir)
                print('POINT_NEWTON',scene,capture_rep,direction,rep,row['status'],'cost',row.get('cost'),
                      'delta_pct',row.get('cost_delta_pct_vs_euclidean'),'rho_H',row.get('rho_hybrid'),
                      'fallback',row.get('masks',{}).get('fallback',{}).get('point_fraction'),'cpu',row['cpu_total_seconds'],flush=True)
    manifest['campaign_cpu_wall_seconds']=time.perf_counter()-begin;write(outdir/'manifest.json',manifest)
    summary=summarize(rows,outdir);print('COMPLETE rows',len(rows),'killed',summary['screen_killed'],flush=True)


if __name__=='__main__':main()
