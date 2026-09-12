#!/usr/bin/env python3
from pathlib import Path
import json,hashlib
import numpy as np
import core
from verify_reference import fixture,independent_residual


def direct_cost(cameras,X,ci,pi,uv):
    r=independent_residual(cameras,np.c_[X,np.ones(len(X))],ci,pi,uv)
    return .5*np.sum(r*r)


def main():
    rng,c,X,ci,pi,uv,dc=fixture();dc*=4;dp=rng.normal(size=X.shape)*.06
    baseline=core.chart.verify_frozen_baseline();tests={};answers={}
    for arm in ('binary','point_fractions','point_then_camera'):
        ans=core.choose_arm(c,X,dc,dp,ci,pi,uv,arm);score=core.audit(c,X,ci,pi,uv,ans['dc'],ans['dp'],np.ones_like(dc))
        exact=direct_cost(c.retract(ans['dc']),X+ans['dp'],ci,pi,uv)
        assert abs(exact-score['cost'])<1e-10*max(1,exact)
        assert abs(exact-ans['separable_cost'])<1e-10*max(1,exact)
        assert np.all(np.linalg.norm(ans['dp'],axis=1)<=np.linalg.norm(dp,axis=1)*(1+1e-14))
        assert np.linalg.norm(ans['dc'])<=np.linalg.norm(dc)*(1+1e-14)
        fractions=(0.,.25,.5,1.) if arm=='point_fractions' else (0.,1.)
        prop=c.retract(dc)
        for j in range(len(X)):
            opts=[]
            for alpha in sorted(fractions,reverse=True):
                xx=X.copy();xx[j]+=alpha*dp[j];keep=pi==j
                opts.append((direct_cost(prop,xx,ci[keep],pi[keep],uv[keep]),alpha))
            best=min(opts,key=lambda a:a[0])[1]
            assert ans['alpha'][j]==best
        if arm=='point_then_camera':
            chosenX=X+ans['dp']
            for i in range(len(dc)):
                keep=ci==i;old=direct_cost(c,chosenX,ci[keep],pi[keep],uv[keep]);moved=direct_cost(prop,chosenX,ci[keep],pi[keep],uv[keep])
                assert ans['camera_move'][i]==(not(old<moved))
        # Central directional finite difference verifies original-coordinate Jd
        # independently of the direct GN expression in core.audit.
        e=1e-6;Hp=np.c_[X+e*ans['dp'],np.ones(len(X))];Hm=np.c_[X-e*ans['dp'],np.ones(len(X))]
        rp=independent_residual(c.retract(e*ans['dc']),Hp,ci,pi,uv);rm=independent_residual(c.retract(-e*ans['dc']),Hm,ci,pi,uv)
        jd=(rp-rm)/(2*e);r0=independent_residual(c,np.c_[X,np.ones(len(X))],ci,pi,uv)
        pred=-np.sum(r0*jd)-.5*np.sum(jd*jd)
        rel=abs(pred-score['prediction'])/max(1,abs(pred));assert rel<1e-7
        tests[arm]=dict(cost=score['cost'],prediction=score['prediction'],fd_prediction_relative_error=rel)
        answers[arm]=score
    for arm in ('point_fractions','point_then_camera'):
        assert answers[arm]['cost']<=answers['binary']['cost']+1e-10
    # Exact ties choose full point movement and moved camera, including an unseen
    # synthetic point. A zero source step creates exact ties without epsilon.
    XX=np.vstack((X,[[2.,3.,-8.]]));zero_p=np.zeros_like(XX);zero_c=np.zeros_like(dc)
    for arm in ('binary','point_fractions','point_then_camera'):
        ans=core.choose_arm(c,XX,zero_c,zero_p,ci,pi,uv,arm)
        assert np.all(ans['alpha']==1) and np.all(ans['camera_move'])
    # Candidate horizon is scored as infinity, never dropped; old point remains
    # available. Camera geometry is simple so the full candidate hits z=0 exactly.
    hc=core.CameraState(np.eye(3)[None],np.zeros((1,3)),np.array([[100.,0.,0.]]));hx=np.array([[.2,.1,-1.]])
    hdp=np.array([[0.,0.,1.]]);idx=np.array([0]);huv=np.array([[20.,10.]])
    ans=core.choose_arm(hc,hx,np.zeros((1,9)),hdp,idx,idx,huv,'point_fractions')
    assert ans['alpha'][0]==0 and np.isfinite(ans['separable_cost'])
    outdir=Path(__file__).with_name('results');outdir.mkdir(exist_ok=True)
    report=dict(status='all checks passed',baseline=baseline,tests=tests,exact_tie_and_unseen_rules_verified=True,
                nonfinite_candidate_not_dropped=True,point_and_camera_nonincrease_guarantees_verified=True,
                source_sha256=hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest())
    (outdir/'verification.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps(tests,indent=2))


if __name__=='__main__':main()
