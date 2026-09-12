#!/usr/bin/env python3
"""Registered fixed64 ARC versus matched projected LM; full Venice CPU states."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import statistics
import time
import numpy as np
from arc_core import ROOT,CHART,Problem,run_pair
from audit_capture import load_capture_state,map_f64,sanitize

P=Path(__file__).resolve().parent


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def write(path,data):path.write_text(json.dumps(sanitize(data),indent=2,allow_nan=False)+'\n')


def summarize(pairs,out):
    rows=[]
    for pair in pairs:
        for row in pair.get('rows',[]):rows.append(dict(capture_rep=pair['capture_rep'],rep=pair['rep'],status=pair['status'],**row))
    cells=[]
    for cap in range(3):
        for arm in ('lm','arc'):
            rr=[r for r in rows if r['capture_rep']==cap and r['arm']==arm]
            if not rr:continue
            cell=dict(capture_rep=cap,arm=arm,repetitions=len(rr),valid=sum(r['status']=='ok' for r in rr),accepted=sum(r['accepted'] for r in rr))
            for f in ('accepted_cost','raw_cost','true_decrease','accepted_decrease','standalone_cpu_seconds',
                      'accepted_decrease_per_standalone_cpu_second','full_stationarity_relative_residual','lambda_value',
                      'camera_norm_over_old_radius','full_D_norm'):
                vals=[r[f] for r in rr if r.get(f) is not None]
                if vals:cell.update({f+'_median':statistics.median(vals),f+'_min':min(vals),f+'_max':max(vals)})
            cells.append(cell)
    gates=[]
    for cap in range(3):
        a=next((c for c in cells if c['capture_rep']==cap and c['arm']=='arc'),None)
        b=next((c for c in cells if c['capture_rep']==cap and c['arm']=='lm'),None)
        if a is None or b is None:continue
        valid=a['valid']==3 and b['valid']==3
        delta=100*(a['accepted_cost_median']/b['accepted_cost_median']-1)
        gates.append(dict(capture_rep=cap,all_N3_valid=valid,
          arc_gain_over_lm_20pct=valid and a['accepted_decrease_median']>1.2*b['accepted_decrease_median'],
          lm_gain_over_arc_20pct=valid and b['accepted_decrease_median']>1.2*a['accepted_decrease_median'],
          cost_delta_percent_vs_lm=delta,cost_regression_over_015pct=delta>.15))
    result=dict(expected_pairs=9,completed_pairs=len(pairs),valid_pairs=sum(p['status']=='ok' for p in pairs),
      completed_rows=len(rows),cells=cells,gates=gates,
      screening_wins=sum(g['arc_gain_over_lm_20pct'] for g in gates),
      screen_passed=len(pairs)==9 and sum(g['arc_gain_over_lm_20pct'] for g in gates)>=2 and not any(g['cost_regression_over_015pct'] for g in gates),
      score_init_checks_passed=all(p.get('score_init_agreement',False) for p in pairs),
      shared_actual_cpu_seconds=sum(p['paired_actual_cpu_seconds'] for p in pairs),
      total_full_products=sum(p.get('basis',{}).get('full_products',0)+sum(r.get('verification_full_products',0) for r in p.get('rows',[])) for p in pairs),
      scope='Full original Venice witnesses; fixed64 full-normal CPU diagnostic, no native/GPU target-speed claim')
    write(out/'summary.json',result)
    if rows:
        simple=[{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in rows]
        keys=list(dict.fromkeys(k for r in simple for k in r))
        with (out/'ledger.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(simple)
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--resume',action='store_true');args=ap.parse_args()
    for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        if os.environ.get(k,'1')!='1':raise RuntimeError(k+' must be1')
    verification=json.loads((P/'verification.json').read_text());assert verification['status']=='passed'
    for n,h in verification['source_sha256'].items():assert sha(P/n)==h,n
    baseline=CHART.verify_frozen_baseline();out=P/'results';out.mkdir(exist_ok=True)
    manifest=dict(protocol_sha256=sha(ROOT/'PROTOCOL_07.md'),interpretation_sha256=sha(P/'INTERPRETATION.md'),
      source_sha256={n:sha(P/n) for n in ('arc_core.py','verify.py','run_witnesses.py')},
      reused_sources={n:sha(ROOT/n) for n in ('rosenbrock/core.py','analysis/audit_capture.py','charts/reference.py','coarse/spectrum.py')},
      verification_sha256=sha(P/'verification.json'),baseline=baseline,
      config=dict(krylov_dimension=64,reorthogonalization_passes=2,secular_relative_tolerance=1e-8,
        sigma_rule='lambda_saved/max(captured_eta2_full_D_norm,1e-30)',threads=1,repetitions=3,
        no_radius_clipping=True,no_point_replacement=True,arm_order='rep0 LM,ARC; rep1 ARC,LM; rep2 LM,ARC'),inputs=[])
    pairs=[];path=out/'pairs.jsonl'
    if path.exists():
        if not args.resume:raise RuntimeError('Existing data requires --resume')
        old=json.loads((out/'manifest.json').read_text())
        for k in ('protocol_sha256','interpretation_sha256','source_sha256','reused_sources','verification_sha256'):assert old[k]==manifest[k],k
        pairs=[json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    done={(r['capture_rep'],r['rep']) for r in pairs};start=time.perf_counter()
    bal=Path('/workspace/bal/venice-52.txt');ci,pi,uv,dims=CHART.load_observations(bal)
    context=[]
    for cap in range(3):
        capture=ROOT/'evidence/collect'/f'venice-52-capture-{cap}';cameras,X,meta=load_capture_state(capture)
        E=map_f64(capture/'E.f64',(dims[0],9));Cdiag=map_f64(capture/'Cdiag.f64',(dims[1],3));lam=meta['lambda']
        floor=lam*np.sum(Cdiag,axis=1)/3;floor=np.where(floor>0,floor,1e-32)
        Dp=np.maximum(lam*Cdiag,1e-3*floor[:,None])/lam
        problem=Problem(cameras,X,ci,pi,uv,E,Dp);eta=map_f64(capture/'eta2-0.step',(problem.n,))
        score_init=problem.cost(np.zeros(problem.n))[0]
        manifest['inputs'].append(dict(capture_rep=cap,bal_sha256=sha(bal),
          witness_files={n:sha(capture/n) for n in ('R_state.f64','t_state.f64','X_state.f64','intr_state.f64','E.f64','Cdiag.f64','eta2-0.step','metadata.txt')},
          lambda_value=lam,radius=meta['radius'],score_init=score_init))
        source=ROOT/'analysis/results'/f'venice-52-{cap}.json';audit=json.loads(source.read_text())
        context.append(dict(capture_rep=cap,source=str(source.relative_to(ROOT)),source_sha256=sha(source),
          rows=[dict(arm=r['arm'],rep=r['rep'],direction_label=r['direction_label'],cost=r['costs']['full'],
            true_decrease=r['true_decreases']['full'],rho=r['rho']['full'],native=r['native']) for r in audit['rows']],
          scope='Separately measured captured Eta2/coherent context, never matched timings'))
        write(out/'context.json',context);write(out/'manifest.json',manifest)
        for rep in range(3):
            if (cap,rep) in done:continue
            pair=dict(scene='venice-52',capture_rep=cap,rep=rep,lambda_saved=lam,radius_saved=meta['radius']);begin=time.perf_counter()
            try:
                rows,work=run_pair(problem,lam,meta['radius'],eta,('lm','arc') if rep%2==0 else ('arc','lm'))
                pair.update(work,rows=rows,status='ok',score_init_agreement=all(abs(r['score_init']-score_init)<=1e-8+5e-10*score_init for r in rows))
                assert pair['score_init_agreement'],'score_init mismatch'
            except Exception as exc:
                pair.update(status='invalid',error=f'{type(exc).__name__}: {exc}',paired_actual_cpu_seconds=time.perf_counter()-begin,
                  score_init_agreement=False,rows=[dict(arm=a,accepted=False,score_init=score_init,accepted_cost=score_init,
                    accepted_decrease=0.) for a in ('lm','arc')])
            pair=sanitize(pair);pairs.append(pair)
            with path.open('a') as f:f.write(json.dumps(pair,allow_nan=False)+'\n')
            summarize(pairs,out)
            print('ARC',cap,rep,pair['status'],[(r['arm'],r.get('raw_cost'),r.get('accepted_decrease'),r.get('full_stationarity_relative_residual')) for r in pair['rows']],
                  'cpu',pair['paired_actual_cpu_seconds'],'error',pair.get('error'),flush=True)
    manifest['campaign_elapsed_seconds']=time.perf_counter()-start;write(out/'manifest.json',manifest)
    s=summarize(pairs,out);print('COMPLETE',len(pairs),'wins',s['screening_wins'],'passed',s['screen_passed'],flush=True)


if __name__=='__main__':main()
