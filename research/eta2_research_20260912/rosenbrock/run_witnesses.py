#!/usr/bin/env python3
"""Registered Brief12 three-witness/three-arm/N3 CPU grid; no GPU work."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import statistics
import time
import numpy as np
from core import ROOT,CHART,GAMMA,Problem,run_arm,LinearCertificateError
from audit_capture import load_capture_state,map_f64,sanitize

P=Path(__file__).resolve().parent
ARMS=('lm1','lm2','ros2')


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def write(p,value):p.write_text(json.dumps(sanitize(value),indent=2,allow_nan=False)+'\n')


def summary(rows,out):
    cells=[];group={}
    for r in rows:group.setdefault((r['capture_rep'],r['arm']),[]).append(r)
    for (capture,arm),rr in group.items():
        good=[r for r in rr if r['status']=='ok']
        cell=dict(capture_rep=capture,arm=arm,repetitions=len(rr),valid=len(good))
        for field in ('cost','accepted_decrease','accepted_decrease_per_cpu_second','cpu_total_seconds'):
            values=[r[field] for r in rr if r.get(field) is not None]
            if values:cell.update({field+'_median':statistics.median(values),field+'_min':min(values),field+'_max':max(values)})
        if good:
            cell.update(refinement_corrections=sum(r['refinement_corrections'] for r in good),
                        accepted_steps=sum(sum(s['accepted'] for s in r['steps']) for r in good))
        cells.append(cell)
    gates=[]
    for capture in range(3):
        a=next((x for x in cells if x['capture_rep']==capture and x['arm']=='ros2'),None)
        b=next((x for x in cells if x['capture_rep']==capture and x['arm']=='lm2'),None)
        if not a or not b:continue
        valid=a['valid']==3 and b['valid']==3
        gain_better=valid and a['accepted_decrease_per_cpu_second_min']>b['accepted_decrease_per_cpu_second_max']
        gain_worse=valid and a['accepted_decrease_per_cpu_second_max']<b['accepted_decrease_per_cpu_second_min']
        delta=100*(a['cost_median']/b['cost_median']-1) if valid else None
        gates.append(dict(capture_rep=capture,all_N3_valid=valid,ros_gain_per_wall_disjoint_better=gain_better,
                          ros_gain_per_wall_disjoint_worse=gain_worse,cost_delta_percent_vs_lm2=delta,
                          cost_regression_over_015pct=bool(delta is not None and delta>.15)))
    wins=sum(x['ros_gain_per_wall_disjoint_better'] for x in gates)
    complete=len(rows)==27
    result=dict(expected_rows=27,completed_rows=len(rows),valid_rows=sum(r['status']=='ok' for r in rows),complete=complete,
                cells=cells,gates=gates,winning_witnesses=wins,
                screen_passed=complete and wins>=2 and not any(x['cost_regression_over_015pct'] for x in gates),
                score_init_checks_passed=all(r.get('score_init_agreement',False) for r in rows if r['status']=='ok'),
                registered_cpu_seconds=sum(r['cpu_total_seconds'] for r in rows),
                scope='Full Venice witnesses, fixed-chart coherent CPU controls, no native Eta2 or GPU-speed claim')
    write(out/'summary.json',result)
    if cells:
        keys=list(dict.fromkeys(k for r in cells for k in r))
        with (out/'ledger.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(cells)
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--resume',action='store_true');args=ap.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        if os.environ.get(key,'1')!='1':raise RuntimeError(f'{key} must be 1')
    verify=json.loads((P/'verification.json').read_text());assert verify['status']=='passed'
    baseline=CHART.verify_frozen_baseline();out=P/'results';out.mkdir(exist_ok=True)
    manifest=dict(protocol_sha256=sha(ROOT/'PROTOCOL_12.md'),interpretation_sha256=sha(P/'INTERPRETATION.md'),
       source_sha256={n:sha(P/n) for n in ('core.py','verify.py','run_witnesses.py')},
       reused_sources={n:sha(ROOT/n) for n in ('analysis/audit_capture.py','charts/reference.py','coarse/spectrum.py')},
       baseline=baseline,verification_sha256=sha(P/'verification.json'),
       config=dict(gamma=GAMMA,h_rule='1/lambda_champion',stage_lambda_rule='lambda_champion/gamma',
                   arms=ARMS,repetitions=3,threads=1,full_residual_tolerance=1e-10,max_refinement_corrections=5,
                   order='rep0 LM1,LM2,ROS2; rep1 LM2,ROS2,LM1; rep2 ROS2,LM1,LM2',
                   matrix_factorization='dense camera Schur Cholesky, augmented point QR',
                   clipping='camera E norm; point completion from each method own combined RHS'),
       inputs=[])
    rowsfile=out/'rows.jsonl';rows=[]
    if rowsfile.exists():
        if not args.resume:raise RuntimeError('Existing rows require --resume')
        old=json.loads((out/'manifest.json').read_text())
        for k in ('protocol_sha256','interpretation_sha256','source_sha256','reused_sources'):assert old[k]==manifest[k],k
        rows=[json.loads(x) for x in rowsfile.read_text().splitlines() if x.strip()]
    done={(r['capture_rep'],r['rep'],r['arm']) for r in rows}
    start=time.perf_counter();bal=Path('/workspace/bal/venice-52.txt');ci,pi,uv,dims=CHART.load_observations(bal)
    for capture_rep in range(3):
        capture=ROOT/'evidence/collect'/f'venice-52-capture-{capture_rep}'
        cameras,X,meta=load_capture_state(capture)
        E=map_f64(capture/'E.f64',(dims[0],9));Cdiag=map_f64(capture/'Cdiag.f64',(dims[1],3))
        lam=meta['lambda'];floor=lam*np.sum(Cdiag,axis=1)/3;floor=np.where(floor>0,floor,1e-32)
        Dp=np.maximum(lam*Cdiag,1e-3*floor[:,None])/lam
        problem=Problem(cameras,X,ci,pi,uv,E,Dp);radius=meta['radius']
        initial=problem.cost(np.zeros(problem.n))[0]
        manifest['inputs'].append(dict(capture_rep=capture_rep,bal_sha256=sha(bal),
          witness_files={n:sha(capture/n) for n in ('R_state.f64','t_state.f64','X_state.f64','intr_state.f64','E.f64','Cdiag.f64','metadata.txt')},
          lambda_value=lam,radius=radius,score_init=initial))
        write(out/'manifest.json',manifest)
        for rep in range(3):
            order=ARMS[rep:]+ARMS[:rep]
            for arm in order:
                if (capture_rep,rep,arm) in done:continue
                row=dict(scene='venice-52',capture_rep=capture_rep,rep=rep,arm=arm,lambda_value=lam,saved_camera_radius=radius)
                begin=time.perf_counter()
                try:
                    row.update(run_arm(problem,lam,radius,arm))
                    row['score_init_agreement']=abs(row['score_init']-initial)<=1e-8+5e-10*max(initial,1)
                    assert row['score_init_agreement'],'initial objective mismatch'
                except Exception as exc:
                    row.update(status='invalid',error=f'{type(exc).__name__}: {exc}',score_init=initial,
                               cost=initial,accepted_decrease=0.,accepted_decrease_per_cpu_second=0.,
                               cpu_total_seconds=time.perf_counter()-begin)
                    if isinstance(exc,LinearCertificateError):row['failed_certificate']=exc.record
                row=sanitize(row);rows.append(row);done.add((capture_rep,rep,arm))
                with rowsfile.open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n')
                summary(rows,out)
                print('ROS2',capture_rep,rep,arm,row['status'],'cost',row['cost'],'gain/sec',row['accepted_decrease_per_cpu_second'],
                      'cpu',row['cpu_total_seconds'],'error',row.get('error'),flush=True)
    manifest['campaign_cpu_wall_seconds']=time.perf_counter()-start;write(out/'manifest.json',manifest)
    result=summary(rows,out);print('COMPLETE',len(rows),'passed',result['screen_passed'],'wins',result['winning_witnesses'],flush=True)


if __name__=='__main__':main()
