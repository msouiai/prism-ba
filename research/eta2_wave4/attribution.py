"""O3/O4 fixed-state rational attribution on actual full native directions."""
from pathlib import Path
import argparse, hashlib, json, sys, tempfile, time
import numpy as np

P = Path(__file__).resolve().parent
W = P.parent/'eta2_wave3'
C = P.parent/'eta2_research_20260912'
sys.path.insert(0, str(W))
import forensics as F


def finite(value):
    value = float(value)
    return value if np.isfinite(value) else None


def evaluate(folder, problem, label, step_name='accepted.step'):
    start = time.perf_counter()
    cam, X, meta = F.load_capture_state(folder)
    nc, np_ = len(cam.R), len(X)
    step = F.read_array(folder/step_name, (9*nc+3*np_,))
    dc, dp = step[:9*nc].reshape(nc,9), step[9*nc:].reshape(np_,3)
    assert not np.any(dc[:,8])
    ci, pi, uv, dims = F.CHART.load_observations(problem)
    assert dims == (nc,np_,len(ci))
    new = cam.retract(dc)
    n = len(ci)
    c0=np.empty(n); linear=np.empty(n); rational=np.empty(n); true=np.empty(n)
    dzratio=np.empty(n); actual_zratio=np.empty(n); derivative=np.empty(n); invz=np.empty(n)
    residual_disagreement=np.empty(n); geometry_error=np.empty(n)
    oldz=np.empty(n); proposedz=np.empty(n); approxz=np.empty(n)
    intrinsic = cam.intrinsics + dc[:,6:9]
    for first in range(0,n,50000):
        sl=slice(first,min(first+50000,n));c=ci[sl];p=pi[sl]
        RX=np.einsum('nij,nj->ni',cam.R[c],X[p]);Y=RX+cam.t[c]
        pix,JY,JI=F.S.chart.project_jacobian(Y,cam.intrinsics[c]);r=pix-uv[sl]
        delta=np.cross(dc[c,:3],RX)+dc[c,3:6]+np.einsum('nij,nj->ni',cam.R[c],dp[p])
        jd=np.einsum('nij,nj->ni',JY,delta)+np.einsum('nij,nj->ni',JI,dc[c,6:9])
        approx=F.S.chart.project_jacobian(Y+delta,intrinsic[c])[0]-uv[sl]
        exact,Yn=F.S.residual(new,X[p]+dp[p],c,uv[sl])
        c0[sl]=.5*np.sum(r*r,axis=1)
        linear[sl]=.5*np.sum((r+jd)**2,axis=1)
        rational[sl]=.5*np.sum(approx*approx,axis=1)
        true[sl]=.5*np.sum(exact*exact,axis=1)
        residual_disagreement[sl]=np.sum((approx-r-jd)**2,axis=1)
        geometry_error[sl]=np.sum((approx-exact)**2,axis=1)
        oldz[sl]=Y[:,2];proposedz[sl]=Yn[:,2];approxz[sl]=(Y+delta)[:,2]
        dzratio[sl]=abs(delta[:,2])/np.maximum(abs(Y[:,2]),1e-300)
        actual_zratio[sl]=Yn[:,2]/Y[:,2]
        # R is orthogonal, hence ||J_point||_F == ||J_Y||_F.
        derivative[sl]=np.sum(JY*JY,axis=(1,2))
        invz[sl]=1/np.maximum(Y[:,2]**2,1e-300)
    median_sq=max(2*float(np.median(c0)),1e-24)
    relative=residual_disagreement/np.maximum(2*c0,median_sq)
    flags=relative>.5
    sensitivity=derivative/max(float(np.median(derivative)),1e-300)
    inverse_depth=invz/max(float(np.median(invz)),1e-300)
    discrepancy=rational-linear
    point_gap=np.bincount(pi,weights=discrepancy,minlength=np_)
    magnitude=np.bincount(pi,weights=abs(discrepancy),minlength=np_)
    order=np.argsort(magnitude)[::-1]
    ids=np.argsort(abs(discrepancy))[-30:][::-1]
    tracked=250233 if label.startswith('final') else None
    if tracked is not None:ids=np.unique(np.r_[ids,np.flatnonzero(pi==tracked)])
    examples=[]
    for i in ids:
        examples.append(dict(observation=int(i),point=int(pi[i]),camera=int(ci[i]),
            current_cost=finite(c0[i]),linear_cost=finite(linear[i]),rational_cost=finite(rational[i]),true_cost=finite(true[i]),
            model_error=finite(discrepancy[i]),relative_disagreement=finite(relative[i]),flagged=bool(flags[i]),
            old_depth=finite(oldz[i]),linear_depth=finite(approxz[i]),actual_depth=finite(proposedz[i]),
            relative_linear_depth_change=finite(dzratio[i]),actual_depth_ratio=finite(actual_zratio[i]),
            sensitivity_ratio=finite(sensitivity[i]),inverse_depth_squared_ratio=finite(inverse_depth[i])))
    initial=float(np.sum(c0,dtype=np.longdouble))
    assert abs(initial-meta['cost'])/max(1,initial)<1e-8,(initial,meta['cost'])
    predicted=float(np.sum(c0-linear,dtype=np.longdouble))
    gain=float(np.sum(c0-true,dtype=np.longdouble))
    result=dict(label=label, metadata=meta,step_name=step_name,
        source_hashes={p.name:F.sha(p) for p in folder.iterdir() if p.is_file()},
        input_sha256=F.sha(problem),observations=n,points=np_,cameras=nc,score_init=initial,
        direction_scope='Actual recorded native joint direction',
        prediction=predicted,true_decrease=gain,rho=finite(gain/predicted) if predicted else None,
        rational_predicted_decrease=finite(np.sum(c0-rational,dtype=np.longdouble)),
        rational_true_cost_error=finite(np.sum(rational-true,dtype=np.longdouble)),
        rational_linear_absolute_cost_error=finite(np.sum(abs(discrepancy),dtype=np.longdouble)),
        rational_true_residual_error_squared=finite(np.sum(geometry_error,dtype=np.longdouble)),
        flagged_observations=int(flags.sum()),flagged_fraction=float(flags.mean()),
        denominator_caps=[dict(kappa=k,violations=int(np.count_nonzero(dzratio>k)),fraction=float(np.mean(dzratio>k))) for k in [.3,.5]],
        sensitivity_trigger_count=int(np.count_nonzero(sensitivity>1e4)),sensitivity_trigger_fraction=float(np.mean(sensitivity>1e4)),
        inverse_depth_trigger_count=int(np.count_nonzero(inverse_depth>1e4)),inverse_depth_trigger_fraction=float(np.mean(inverse_depth>1e4)),
        actual_depth_sign_changes=int(np.count_nonzero(oldz*proposedz<0)),
        actual_depth_ratio_quantiles=[finite(v) for v in np.quantile(actual_zratio,[0,.001,.01,.5,.99,1])],
        top_points=[dict(point=int(j),signed_model_gap=finite(point_gap[j]),absolute_model_gap=finite(magnitude[j]),
                        observations=int(np.count_nonzero(pi==j))) for j in order[:30]],
        tracked_point=tracked,tracked_point_rank=(int(np.flatnonzero(order==tracked)[0])+1) if tracked is not None else None,
        tracked_point_flagged=bool(np.any(flags[pi==tracked])) if tracked is not None else None,
        observation_examples=examples,seconds=time.perf_counter()-start,
        scope='Attribution at fixed recorded states; no constrained solve or continued-trajectory rescue claim')
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['e4','witness','healthy']);args=ap.parse_args()
    F.verify_baseline();out=P/'attribution';out.mkdir(exist_ok=True)
    def run(folder,problem,label,step='accepted.step'):
        dest=out/(label+'.json')
        if dest.exists():return
        print('ATTRIBUTION START',label,flush=True)
        r=evaluate(folder,problem,label,step);F.write(dest,r)
        print('ATTRIBUTION DONE',label,'flags',r['flagged_fraction'],'caps',r['denominator_caps'],
              'rank',r['tracked_point_rank'],'sensitivity',r['sensitivity_trigger_fraction'],flush=True)
    if args.stage=='witness':
        for rep in [0,5,6]:
            run(C/'evidence/collect'/f'final-3068-capture-{rep}',Path('/workspace/bal/final-3068.txt'),f'final-stop-{rep}','eta2.step')
    elif args.stage=='e4':
        rec=json.loads((W/'miss-forensics/decision.json').read_text())
        assert F.sha(rec['archive'])==rec['sha256']
        wanted={'hit/6','hit/7','miss/6','miss/8'}
        with tempfile.TemporaryDirectory(prefix='o3-e4-',dir='/dev/shm') as t:
            root=Path(t)
            for name,raw in F.FA.decoded(rec['archive']):
                if str(Path(name).parent) in wanted:
                    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
            for name in sorted(wanted):run(root/name,Path('/workspace/bal/final-3068.txt'),'final-e4-'+name.replace('/','-'))
    else:
        reg=json.loads((W/'registration.json').read_text())
        problem=Path(next(c['path'] for c in reg['practical'] if c['cell']=='ladybug-539-1.005'))
        for rec in json.loads((P/'healthy-captures/index.json').read_text()):
            assert F.sha(rec['archive'])==rec['sha256']
            with tempfile.TemporaryDirectory(prefix='o3-healthy-',dir='/dev/shm') as t:
                root=Path(t);F.FA.restore(rec['archive'],root)
                for attempt in rec['selected_attempts']:
                    run(root/str(attempt),problem,f'ladybug-healthy-{rec["rep"]}-{attempt}')


if __name__=='__main__':main()
