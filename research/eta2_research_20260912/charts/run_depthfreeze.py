#!/usr/bin/env python3
"""Execute committed Brief2(c), one fixed mask and no depth release."""
from __future__ import annotations
import argparse,csv,json,os,statistics,sys,time
from pathlib import Path
import numpy as np
import reference
from run_witnesses import CASES,DIRECTIONS,ROOT,sha,timing_components,top_concentration
from audit_capture import load_capture_state,map_f64,sanitize,error_stats,geometry

OUT=Path(__file__).with_name('results_depthfreeze')


def freeze_rule(counts,angles,eigenvalues):
    small=counts<2
    low=angles<1.
    two=counts==2
    condition=np.full(len(counts),np.nan)
    nonpositive=two&(eigenvalues[:,0]<=0)
    positive=two&(eigenvalues[:,0]>0)
    condition[nonpositive]=np.inf
    condition[positive]=eigenvalues[positive,-1]/eigenvalues[positive,0]
    ill=two&(condition>=1e8)
    return small|low|ill,dict(small=small,low=low,ill=ill,nonpositive=nonpositive,condition=condition)


def prepare_mask(cameras,X,ci,pi,uv,chunk=50000):
    start=time.perf_counter();geo=geometry(cameras,X,ci,pi)
    counts=geo['track_lengths'];n=len(X);V=np.zeros((n,3,3))
    # Only length-two blocks enter the condition test, but every observation is
    # still retained by the candidate solve and scored objective below.
    model_start=time.perf_counter()
    for s in range(0,len(ci),chunk):
        sl=slice(s,s+chunk);c=ci[sl];p=pi[sl];use=counts[p]==2
        c=c[use];p=p[use]
        if not len(p):continue
        Y=np.einsum('nij,nj->ni',cameras.R[c],X[p])+cameras.t[c]
        Jp=reference.project_jacobian(Y,cameras.intrinsics[c])[1]@cameras.R[c]
        for a in range(3):
            for b in range(a,3):
                V[:,a,b]+=np.bincount(p,weights=np.einsum('ni,ni->n',Jp[:,:,a],Jp[:,:,b]),minlength=n)
    for a in range(3):
        for b in range(a):V[:,a,b]=V[:,b,a]
    eig=np.full((n,3),np.nan);two=counts==2
    if np.any(two):eig[two]=np.linalg.eigvalsh(V[two])
    if not np.isfinite(eig[two]).all():raise FloatingPointError('nonfinite two-observation eigenvalues')
    mask,reasons=freeze_rule(counts,geo['parallax_degrees'],eig)
    info={'frozen_points':int(mask.sum()),'total_points':n,'frozen_fraction':float(mask.mean()),
          'parallax_below_1_degree':int(reasons['low'].sum()),'two_track_condition_at_least_1e8':int(reasons['ill'].sum()),
          'fewer_than_two_observations':int(reasons['small'].sum()),'nonpositive_two_track_eigenvalue':int(reasons['nonpositive'].sum()),
          'undefined_parallax':int(np.count_nonzero(~np.isfinite(geo['parallax_degrees']))),
          'mask_sha256':__import__('hashlib').sha256(mask.tobytes()).hexdigest(),
          'cpu_geometry_seconds':geo['cpu_geometry_seconds'],'cpu_euclidean_condition_seconds':time.perf_counter()-model_start,
          'cpu_mask_setup_seconds':time.perf_counter()-start,
          'frozen_by_track_length':{label:int(np.count_nonzero(mask&select)) for label,select in {
              '0-1':counts<2,'2':counts==2,'3-5':(counts>=3)&(counts<=5),'>5':counts>5}.items()}}
    return mask,geo,info


def run_cell(cameras,X,ci,pi,uv,dc,lam,mask,geo):
    start=time.perf_counter()
    with timing_components() as times:
        ans=reference.evaluate_chart_step(cameras,X,ci,pi,uv,dc,lam,chart='inverse_depth',tau=lam,
                                         scene_radius=geo['scene_radius'],freeze_depth=mask)
    H=ans['H_candidate'];Xnew=reference.euclidean_from_homogeneous(H)
    oldr=np.linalg.norm(X-geo['camera_center_centroid'],axis=1);newr=np.linalg.norm(Xnew-geo['camera_center_centroid'],axis=1)
    large=ans['euclidean_displacement']>geo['scene_radius'];inward=large&(newr<oldr);outward=large&~inward
    proposal=cameras.retract(dc);front_back=back_front=0
    for s in range(0,len(ci),50000):
        sl=slice(s,s+50000);c=ci[sl];p=pi[sl]
        old_z=(np.einsum('nij,nj->ni',cameras.R[c],X[p])+cameras.t[c])[:,2]
        new_y=np.einsum('nij,nj->ni',proposal.R[c],H[p,:3])+proposal.t[c]*H[p,3,None]
        new_sign=np.sign(new_y[:,2])*np.sign(H[p,3])
        finite=H[p,3]!=0
        front_back+=int(np.count_nonzero(finite&(old_z<0)&(new_sign>0)))
        back_front+=int(np.count_nonzero(finite&(old_z>0)&(new_sign<0)))
    out=dict(status='ok',score_init=ans['score_init'],cost=ans['costs']['full'],prediction=ans['pred'],
             true_decrease=ans['true_decrease'],rho=ans['rho'],
             active_point_equation_relative_residual=ans['linear_relative_residual'],
             residual_scope='active bearing equations on frozen tracks; full three equations on other tracks',
             constrained_depth_reaction_norm=ans['constraint_reaction_norm'],
             frozen_depth_increment_max_abs=float(np.max(abs(ans['delta'][mask,2]))) if mask.any() else 0.,
             frozen_depth_count=ans['frozen_depth_count'],fling_count=ans['fling_count'],
             large_moves_inward=int(inward.sum()),large_moves_outward=int(outward.sum()),
             frozen_large_moves_inward=int(np.count_nonzero(mask&inward)),frozen_large_moves_outward=int(np.count_nonzero(mask&outward)),
             maximum_point_displacement=float(np.max(ans['euclidean_displacement'])),maximum_new_distance=float(newr.max()),
             maximum_old_distance=float(oldr.max()),scene_radius=geo['scene_radius'],
             front_to_behind_observations=front_back,behind_to_front_observations=back_front,
             cheirality_flip_observations=ans['cheirality_flip_observations'],
             invalid_projection_observations=ans['invalid_projection_observations'],
             exact_infinity_count=ans['exact_infinity_count'],near_infinity_count=ans['near_infinity_count'],
             model_error={key:error_stats(value) for key,value in ans['model_error_per_track'].items()},
             top200_point_error=top_concentration(ans['model_error_per_track']['point']),
             assembly_and_setup_seconds=times['conditional_total_seconds']-times['linear_solve_seconds'],
             linear_solve_seconds=times['linear_solve_seconds'])
    elapsed=time.perf_counter()-start
    out.update(scoring_and_diagnostics_seconds=elapsed-times['conditional_total_seconds'],cpu_candidate_seconds=elapsed)
    return out


METRICS=('score_init','cost','prediction','true_decrease','rho','cost_delta_pct_vs_euclidean','cost_delta_pct_vs_plain_id',
         'cost_increase_vs_plain_id','active_point_equation_relative_residual','constrained_depth_reaction_norm',
         'fling_count','large_moves_inward','large_moves_outward','frozen_large_moves_inward','frozen_large_moves_outward',
         'maximum_point_displacement','maximum_old_distance','maximum_new_distance','frozen_depth_count',
         'front_to_behind_observations','behind_to_front_observations','assembly_and_setup_seconds','linear_solve_seconds',
         'scoring_and_diagnostics_seconds','cpu_candidate_seconds','cpu_candidate_plus_unamortized_mask_seconds',
         'euclidean_outward_large_control','plain_id_inward_large_control','plain_id_outward_large_control')


def summarize(rows,outdir,manifest):
    agg=[]
    for scene,cap in CASES:
        for direction in DIRECTIONS:
            cell=[r for r in rows if (r['scene'],r['capture_rep'],r['camera_direction'])==(scene,cap,direction)]
            if not cell:continue
            good=[r for r in cell if r['status']=='ok']
            a=dict(scene=scene,capture_rep=cap,camera_direction=direction,repetitions=len(cell),valid=len(good),
                   initial_score_checks=all(r.get('score_init_agreement',False) for r in cell))
            for key in METRICS:
                nums=[r[key] for r in good if isinstance(r.get(key),(int,float)) and np.isfinite(r[key])]
                a[key+'_median']=statistics.median(nums) if len(nums)==len(cell) else None
                a[key+'_range']=[min(nums),max(nums)] if len(nums)==len(cell) else None
            agg.append(a)
    primary=[r for r in agg if r['camera_direction']=='eta2' and not(r['scene']=='ladybug-1197' and r['capture_rep']>0)]
    valid=lambda r:r['valid']==3 and r['repetitions']==3 and r['initial_score_checks']
    wins=[r for r in primary if valid(r) and r['cost_delta_pct_vs_euclidean_median']<-.15 and r['prediction_median']>0 and r['rho_median']>.1]
    losses=[r for r in primary if valid(r) and r['cost_delta_pct_vs_euclidean_median']>.15]
    lady=[r for r in agg if r['camera_direction']=='eta2' and r['scene']=='ladybug-1197']
    fling_pass=len(lady)==3 and all(valid(r) and r['euclidean_outward_large_control_median'] is not None
                                  and r['large_moves_outward_median']<r['euclidean_outward_large_control_median'] for r in lady)
    complete=len(rows)==54 and len(agg)==18 and all(valid(r) for r in agg)
    gate=complete and fling_pass and len(wins)>=2 and len({r['scene'] for r in wins})>=2 and not losses
    short=lambda data:[{key:r.get(key) for key in ('scene','capture_rep','cost_delta_pct_vs_euclidean_median','large_moves_outward_median')} for r in data]
    report=dict(scope='Fixed-state CPU chart diagnostics, not a GPU trajectory, hit rate, or speed claim',
                protocol=manifest['protocol'],rows=len(rows),expected_rows=54,expected_configurations=18,aggregates=agg,
                gate=dict(passed=gate,complete=complete,ladybug_strict_outward_reduction_passed=fling_pass,
                          primary_wins=short(wins),primary_regressions=short(losses),ladybug_rows=short(lady),
                          stop_tau_floor_removal_sweep=complete and not gate))
    (outdir/'summary.json').write_text(json.dumps(sanitize(report),indent=2,allow_nan=False)+'\n')
    if agg:
        fields=list(dict.fromkeys(key for r in agg for key in r))
        with (outdir/'ledger.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(agg)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,default=OUT);p.add_argument('--resume',action='store_true');args=p.parse_args()
    outdir=args.output_dir;outdir.mkdir(parents=True,exist_ok=True)
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        if os.environ.get(key)!='1':raise RuntimeError(f'{key} must explicitly be 1')
    begin=time.perf_counter();baseline=reference.verify_frozen_baseline()
    protocol=ROOT/'PROTOCOL_02C.md';oldrows_path=Path(__file__).with_name('results')/'rows.jsonl'
    controls=[json.loads(line) for line in oldrows_path.read_text().splitlines()]
    motion_path=Path(__file__).with_name('results')/'displacement_forensics_v2.json'
    old_motion=json.loads(motion_path.read_text())['rows']
    manifest=dict(protocol=dict(path=str(protocol),sha256=sha(protocol),registration_commit='f8d25e36ea3bb59d3e316a0422ed166bdd5788c4'),
                  baseline=baseline,source_sha256=sha(__file__),reference_sha256=sha(reference.__file__),
                  retained_controls_sha256=sha(oldrows_path),retained_motion_controls_sha256=sha(motion_path),
                  mask_rule='max initial parallax <1deg OR m=2 and cond(V_euclidean)>=1e8 OR m<2',
                  configuration=dict(chart='inverse_depth',anchor='first original-order observation',tau='lambda',release='none',threads=1,repetitions=3),
                  timing_scope='mask recomputed once per captured state and reused for fixed camera directions/repetitions; unamortized mask cost also added to each candidate row; no GPU performance inference',
                  capture_inputs=[])
    path=outdir/'rows.jsonl';rows=[]
    if path.exists():
        if not args.resume:raise RuntimeError('Refusing to overwrite existing rows')
        old=json.loads((outdir/'manifest.json').read_text())
        for key in ('source_sha256','reference_sha256','protocol','retained_controls_sha256','retained_motion_controls_sha256'):
            if old[key]!=manifest[key]:raise RuntimeError('Changed source/protocol/controls while resuming')
        rows=[json.loads(line) for line in path.read_text().splitlines()]
    for scene,cap in CASES:
        setup=time.perf_counter();folder=ROOT/'evidence/collect'/f'{scene}-capture-{cap}';bal=Path('/workspace/bal')/f'{scene}.txt'
        cameras,X,meta=load_capture_state(folder);ci,pi,uv,dims=reference.load_observations(bal)
        if dims!=(len(cameras.R),len(X),int(meta['nobs'])):raise ValueError('BAL dimensions')
        io_seconds=time.perf_counter()-setup;mask,geo,info=prepare_mask(cameras,X,ci,pi,uv)
        record=dict(scene=scene,capture_rep=cap,lambda_value=meta['lambda'],mask=info,setup_io_seconds=io_seconds,
                    bal_sha256=sha(bal),state_sha256={name:sha(folder/name) for name in ('R_state.f64','t_state.f64','X_state.f64','intr_state.f64','metadata.txt')})
        manifest['capture_inputs'].append(record)
        (outdir/'manifest.json').write_text(json.dumps(sanitize(manifest),indent=2,allow_nan=False)+'\n')
        print('MASK',scene,cap,json.dumps(info),flush=True)
        for direction in DIRECTIONS:
            step_path=folder/f'{direction}-0.step';dc=map_f64(step_path,(9*dims[0]+3*dims[1],))[:9*dims[0]].reshape(dims[0],9)
            eu=next(r for r in controls if(r['scene'],r['capture_rep'],r['camera_direction'],r['chart'],r['rep'])==(scene,cap,direction,'euclidean',0))
            plain=next(r for r in controls if(r['scene'],r['capture_rep'],r['camera_direction'],r['chart'],r['rep'])==(scene,cap,direction,'inverse_depth',0))
            for rep in range(3):
                if any((r['scene'],r['capture_rep'],r['camera_direction'],r['rep'])==(scene,cap,direction,rep) for r in rows):continue
                row=dict(scene=scene,capture_rep=cap,camera_direction=direction,chart='inverse_depth_frozen',rep=rep,
                         camera_source_sha256=sha(step_path),lambda_value=meta['lambda'],tau=meta['lambda'],mask_sha256=info['mask_sha256'],
                         euclidean_control_cost=eu['cost'],plain_id_control_cost=plain['cost'],score_init_cpu_baseline=eu['score_init_cpu_baseline'])
                if direction=='eta2':
                    for kind,prefix in (('euclidean','euclidean'),('inverse_depth','plain_id')):
                        motion=next((m for m in old_motion if(m['scene'],m['capture_rep'],m['chart'])==(scene,cap,kind)),None)
                        if motion is not None:
                            row[prefix+'_outward_large_control']=motion['large_moves_outward']
                            row[prefix+'_inward_large_control']=motion['large_moves_inward']
                attempt=time.perf_counter()
                try:
                    row.update(run_cell(cameras,X,ci,pi,uv,dc,meta['lambda'],mask,geo))
                    row['score_init_agreement']=abs(row['score_init']-row['score_init_cpu_baseline'])<=1e-8+5e-10*max(1,row['score_init_cpu_baseline'])
                    row['cost_delta_pct_vs_euclidean']=100*(row['cost']/eu['cost']-1)
                    row['cost_delta_pct_vs_plain_id']=100*(row['cost']/plain['cost']-1)
                    row['cost_increase_vs_plain_id']=row['cost']-plain['cost']
                    row['cpu_candidate_plus_unamortized_mask_seconds']=row['cpu_candidate_seconds']+info['cpu_mask_setup_seconds']
                except Exception as exc:
                    row.update(status='failed',error=type(exc).__name__+': '+str(exc),cpu_candidate_seconds=time.perf_counter()-attempt,score_init_agreement=False)
                row=sanitize(row);rows.append(row)
                with path.open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n');f.flush()
                summarize(rows,outdir,manifest)
                print('FROZEN',scene,cap,direction,rep,'status',row['status'],'cost',row.get('cost'),'delta_eu',row.get('cost_delta_pct_vs_euclidean'),
                      'rho',row.get('rho'),'in/out',row.get('large_moves_inward'),row.get('large_moves_outward'),'seconds',row['cpu_candidate_seconds'],flush=True)
    manifest['campaign_elapsed_seconds']=time.perf_counter()-begin
    (outdir/'manifest.json').write_text(json.dumps(sanitize(manifest),indent=2,allow_nan=False)+'\n')
    report=summarize(rows,outdir,manifest);print('COMPLETE',json.dumps(report['gate']),flush=True)


if __name__=='__main__':main()
