#!/usr/bin/env python3
"""Run only the committed Brief10 three-witness separable rescue screen."""
from pathlib import Path
import argparse,csv,hashlib,json,os,statistics,time
import numpy as np
import core
from audit_capture import load_capture_state,map_f64,read_native_rows,roundoff_compare,sanitize

ROOT=Path(__file__).resolve().parents[1]
ARMS=('binary','point_fractions','point_then_camera')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def aggregate(rows,outdir,manifest):
    aggs=[]
    metrics=('cost','true_decrease','prediction','rho','score_init','additional_decrease_vs_binary',
             'cost_delta_pct_vs_binary','point_selection_seconds','camera_selection_seconds','cpu_scoring_audit_seconds',
             'cpu_total_seconds','point_keep_count','point_quarter_count','point_half_count','point_full_count','camera_keep_count',
             'camera_scaled_norm','maximum_point_displacement','large_moves_inward','large_moves_outward',
             'front_to_behind_observations','behind_to_front_observations')
    for cap in (0,5,6):
        for arm in ARMS:
            cell=[r for r in rows if(r['capture_rep'],r['arm'])==(cap,arm)]
            if not cell:continue
            good=[r for r in cell if r['status']=='ok']
            a=dict(scene='final-3068',capture_rep=cap,arm=arm,repetitions=len(cell),valid_runs=len(good),
                   accepted_runs=sum(r.get('accepted',False) for r in good),rescued_binary_rejection_runs=sum(r.get('rescued_rejected_binary',False) for r in good),
                   score_init_checks=all(r.get('score_init_check',{}).get('status')=='within_budget' for r in cell),
                   direct_separable_cost_checks=all(r.get('separable_cost_check',{}).get('status')=='within_budget' for r in cell),
                   no_worse_cost_checks=all(r.get('no_worse_than_binary',False) for r in cell),
                   point_displacement_bound_checks=all(r.get('point_displacement_bound',False) for r in cell),
                   camera_radius_bound_checks=all(r.get('camera_radius_bound',False) for r in cell))
            for metric in metrics:
                nums=[r[metric] for r in good if isinstance(r.get(metric),(int,float)) and np.isfinite(r[metric])]
                a[metric+'_median']=statistics.median(nums) if len(nums)==len(cell) else None
                a[metric+'_range']=[min(nums),max(nums)] if len(nums)==len(cell) else None
            aggs.append(a)
    complete=len(rows)==27 and len(aggs)==9 and all(r['valid_runs']==3 for r in aggs)
    rejected=[r['capture_rep'] for r in aggs if r['arm']=='binary' and r['valid_runs']==3 and r['accepted_runs']==0]
    gates={}
    for arm in ARMS[1:]:
        selected=[r for r in aggs if r['arm']==arm]
        rescued=[r['capture_rep'] for r in selected if r['rescued_binary_rejection_runs']==3]
        gates[arm]=dict(passed=complete and bool(rescued),rescued_witnesses=rescued,
                        binary_rejected_opportunity_witnesses=rejected,
                        disposition='pending' if not complete else ('survives witness gate only' if rescued else 'killed on registered panel; no native rollout'),
                        inference_limit='If the binary rejected set is empty this panel has no eligible rescue opportunity; it does not establish ineffectiveness on rejected proposals.')
    summary=dict(protocol=manifest['protocol'],scope='Fixed-state CPU diagnostics, no endpoint hit rate or GPU speed claim',
                 row_count=len(rows),expected_rows=27,aggregates=aggs,complete=complete,gates=gates)
    (outdir/'summary.json').write_text(json.dumps(sanitize(summary),indent=2,allow_nan=False)+'\n')
    if aggs:
        with (outdir/'ledger.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(aggs[0]));w.writeheader();w.writerows(aggs)
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,default=Path(__file__).with_name('results'));args=p.parse_args()
    out=args.output_dir;out.mkdir(exist_ok=True);rowpath=out/'rows.jsonl'
    if rowpath.exists():raise RuntimeError('Refusing overwrite of existing evidence')
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        if os.environ.get(key)!='1':raise RuntimeError(f'{key} must be explicitly 1')
    start=time.perf_counter();baseline=core.chart.verify_frozen_baseline()
    protocol=ROOT/'PROTOCOL_10.md';bal=Path('/workspace/bal/final-3068.txt')
    ci,pi,uv,dims=core.chart.load_observations(bal)
    manifest=dict(protocol=dict(path=str(protocol),sha256=sha(protocol),registration_commit='64be3cad3cbaef91e827d8f18e970c15a798ef4b'),
                  baseline=baseline,source_sha256=sha(__file__),core_sha256=sha(core.__file__),chart_reference_sha256=sha(core.chart.__file__),
                  bal_sha256=sha(bal),configuration=dict(arms=ARMS,source_direction='eta2-0.step before native point safeguard',
                  point_fractions=[0,.25,.5,1],ties='prefer full or larger alpha; prefer moved camera',repetitions=3,threads=1),
                  setup_io_seconds=time.perf_counter()-start,capture_inputs=[])
    rows=[]
    for cap in (0,5,6):
        begin=time.perf_counter();folder=ROOT/'evidence/collect'/f'final-3068-capture-{cap}'
        c,X,meta=load_capture_state(folder)
        if dims!=(len(c.R),len(X),int(meta['nobs'])):raise ValueError('dimension mismatch')
        step=map_f64(folder/'eta2-0.step',(9*dims[0]+3*dims[1],));dc=step[:9*dims[0]].reshape(dims[0],9);dp=step[9*dims[0]:].reshape(dims[1],3)
        E=map_f64(folder/'E.f64',(dims[0],9));native=next(r for r in read_native_rows(folder/'native_directions.csv') if r['arm']=='eta2')
        raw=core.audit(c,X,ci,pi,uv,dc,dp,E)
        rawchecks=dict(cost=roundoff_compare(raw['cost'],native['cost'],raw['cost']),
                       prediction=roundoff_compare(raw['prediction'],native['prediction'],raw['prediction_absolute_term_scale']),
                       score_init=roundoff_compare(raw['score_init'],meta['cost'],raw['score_init']))
        if not all(v['status']=='within_budget' for v in rawchecks.values()):raise RuntimeError('raw native source parity failed; preserve diagnostic before comparison')
        manifest['capture_inputs'].append(dict(capture_rep=cap,metadata=meta,native_unguarded=native,raw_cpu_unguarded=raw,
             raw_source_parity=rawchecks,setup_and_raw_audit_seconds=time.perf_counter()-begin,
             sha256={name:sha(folder/name) for name in ('R_state.f64','t_state.f64','X_state.f64','intr_state.f64','metadata.txt','E.f64','eta2-0.step')}))
        (out/'manifest.json').write_text(json.dumps(sanitize(manifest),indent=2,allow_nan=False)+'\n')
        for rep in range(3):
            binary=None
            for arm in ARMS:
                begin=time.perf_counter();row=dict(scene='final-3068',capture_rep=cap,rep=rep,arm=arm,source_step_sha256=sha(folder/'eta2-0.step'))
                try:
                    selection=core.choose_arm(c,X,dc,dp,ci,pi,uv,arm)
                    row.update(core.audit(c,X,ci,pi,uv,selection['dc'],selection['dp'],E))
                    row.update(point_selection_seconds=selection['point_selection_seconds'],camera_selection_seconds=selection['camera_selection_seconds'],
                               separable_selected_cost=selection['separable_cost'],binary_point_then_camera_cost=selection['binary_point_then_camera_cost'],
                               alpha_sha256=hashlib.sha256(selection['alpha'].tobytes()).hexdigest(),camera_mask_sha256=hashlib.sha256(selection['camera_move'].tobytes()).hexdigest())
                    for alpha,label in ((0.,'keep'),(.25,'quarter'),(.5,'half'),(1.,'full')):
                        row['point_'+label+'_count']=int(np.count_nonzero(selection['alpha']==alpha))
                    row['camera_keep_count']=int(np.count_nonzero(~selection['camera_move']))
                    row['point_displacement_bound']=bool(np.all(np.linalg.norm(selection['dp'],axis=1)<=np.linalg.norm(dp,axis=1)*(1+1e-14)))
                    row['camera_radius_bound']=row['camera_scaled_norm']<=raw['camera_scaled_norm']*(1+1e-12)+1e-14
                    row['separable_cost_check']=roundoff_compare(row['cost'],selection['separable_cost'],row['cost'])
                    row['score_init_check']=roundoff_compare(row['score_init'],meta['cost'],row['score_init'])
                    if arm=='binary':binary=row.copy()
                    row['binary_accepted']=binary['accepted'];row['rescued_rejected_binary']=bool(not binary['accepted'] and row['accepted'])
                    row['additional_decrease_vs_binary']=row['true_decrease']-binary['true_decrease']
                    row['cost_delta_pct_vs_binary']=100*(row['cost']/binary['cost']-1)
                    row['no_worse_than_binary']=row['cost']<=binary['cost']+1e-8+5e-10*max(1,row['cost'],binary['cost'])
                    row['status']='ok'
                    if row['changed_k2_entries'] or not(row['point_displacement_bound'] and row['camera_radius_bound'] and row['no_worse_than_binary']):
                        row['status']='guarantee_failure'
                    del selection
                except Exception as exc:row.update(status='failed',error=type(exc).__name__+': '+str(exc))
                row['cpu_total_seconds']=time.perf_counter()-begin;row=sanitize(row);rows.append(row)
                with rowpath.open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n');f.flush()
                aggregate(rows,out,manifest)
                print('RESCUE',cap,rep,arm,'status',row['status'],'cost',row.get('cost'),'gain',row.get('true_decrease'),'rho',row.get('rho'),
                      'accepted',row.get('accepted'),'vs_binary_gain',row.get('additional_decrease_vs_binary'),'point0/.25/.5',
                      row.get('point_keep_count'),row.get('point_quarter_count'),row.get('point_half_count'),'cam_keep',row.get('camera_keep_count'),flush=True)
    manifest['campaign_elapsed_seconds']=time.perf_counter()-start
    (out/'manifest.json').write_text(json.dumps(sanitize(manifest),indent=2,allow_nan=False)+'\n')
    summary=aggregate(rows,out,manifest);print('COMPLETE',json.dumps(summary['gates']),flush=True)


if __name__=='__main__':main()
