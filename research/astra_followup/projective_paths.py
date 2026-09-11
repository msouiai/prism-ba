"""Same-tangent, same-objective point retractions; CPU research reference."""
import time
import numpy as np
from paths import ROOT
from geometry import retract, dot
from reference_ba import Linearization, valid_cost

def chart_vectors(state, lin, arm):
    if arm == 'anchored':
        first = np.full(lin.np, len(lin.pi), dtype=int)
        np.minimum.at(first, lin.pi, np.arange(len(lin.pi)))
        if np.any(first == len(lin.pi)): raise ValueError('unobserved point')
        cam = lin.ci[first]
        centers = -np.einsum('nji,nj->ni', state.R[cam], state.t[cam])
        ray = state.X-centers
        v = ray/np.sum(ray*ray, axis=1)[:, None]
    elif arm == 'mean_view':
        v = np.zeros_like(state.X)
        np.add.at(v, lin.pi, state.R[lin.ci, 2, :]/lin.q[:, 2, None])
        v /= np.bincount(lin.pi, minlength=lin.np)[:, None]
    else: raise ValueError(arm)
    v[0] = 0
    return v

def projective_retract(state, dc, dp, v, alpha=1., margin=.25):
    h = np.einsum('ij,ij->i', v, dp)
    den = 1-alpha*h
    bad = ~np.isfinite(den) | (den < margin)
    den[bad] = 1.
    # v[0]=0 is required by the caller, and enforced independently here.
    den[0] = 1.
    return retract(state, dc, dp/den[:, None], alpha), int(np.count_nonzero(bad))

def solve(initial, obs, target, arm='xyz', cap=2., max_attempts=80):
    start=time.perf_counter(); state=initial.copy(); F=valid_cost(state,obs)
    lin=None; v=None; lam=.1; accepted=rejected=invalid=fallbacks=0
    feature_seconds=path_seconds=0.; attempts=[]; trace=[{'seconds':0.,'cost':F}]
    for i in range(max_attempts):
        if F<=target or time.perf_counter()-start>=cap: break
        if lin is None:
            lin=Linearization(state,obs)
            if arm!='xyz':
                ts=time.perf_counter();v=chart_vectors(state,lin,arm)
                feature_seconds+=time.perf_counter()-ts
        factor=lin.factor(lam);dc,dp=factor.solve()
        ts=time.perf_counter()
        if arm=='xyz': trial=retract(state,dc,dp); count=0
        else: trial,count=projective_retract(state,dc,dp,v)
        path_seconds+=time.perf_counter()-ts;fallbacks+=count
        cost=valid_cost(trial,obs); invalid+=not np.isfinite(cost)
        jd=lin.jd(dc,dp);pred=-dot(lin.r,jd)-.5*dot(jd,jd)
        rho=(F-cost)/pred if pred>0 else -np.inf
        good=np.isfinite(cost) and pred>0 and rho>.1
        attempts.append({'lambda':lam,'parent_cost':F,'cost':cost,'prediction':pred,
                         'rho':rho,'accepted':good,'fallback_points':count})
        if good:
            state=trial;F=cost;accepted+=1;lin=None
            lam=min(1e8,max(1e-8,lam*(.5 if rho>.75 else 2. if rho<.25 else 1.)))
            trace.append({'seconds':time.perf_counter()-start,'cost':F})
        else:rejected+=1;lam=min(1e8,lam*4.)
    elapsed=time.perf_counter()-start
    return state,{'cost':F,'hit':F<=target,'seconds':elapsed,'accepted':accepted,'rejected':rejected,
        'invalid_trials':invalid,'fallback_points':fallbacks,'feature_seconds':feature_seconds,
        'path_seconds':path_seconds,'attempts':attempts,'trace':trace,'lambda':lam}
