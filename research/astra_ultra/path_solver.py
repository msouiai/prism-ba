import time,numpy as np
from paths import ROOT
from geometry import dot
from reference_ba import Linearization,valid_cost
from joint_paths import candidate

def solve(initial,obs,target,arm='xyz',cap=3.,max_attempts=160,capture=()):
    start=time.perf_counter();s=initial.copy();F=valid_cost(s,obs);lam=.1;lin=None
    accepted=rejected=invalid=fallbacks=0;path_seconds=0.;trace=[{'seconds':0.,'cost':F}];attempts=[];parents={}
    for k in range(max_attempts):
        if F<=target or time.perf_counter()-start>=cap:break
        if lin is None:lin=Linearization(s,obs)
        fac=lin.factor(lam);dc,dp=fac.solve()
        ts=time.perf_counter();trial,meta=candidate(s,lin,dc,dp,lam,arm);path_seconds+=time.perf_counter()-ts
        cost=valid_cost(trial,obs);invalid+=not np.isfinite(cost);fallbacks+=meta['fallback_points']
        model_dp=trial.X-s.X if arm=='observed_polish' else dp
        jd=lin.jd(dc,model_dp);pred=-dot(lin.r,jd)-.5*dot(jd,jd)
        rho=(F-cost)/pred if pred>0 else -np.inf;good=np.isfinite(cost) and pred>0 and rho>.1
        attempts.append({'lambda':lam,'parent_cost':F,'trial_cost':cost,'prediction':pred,'rho':rho,'accepted':good,**meta})
        if good:
            s=trial;F=cost;accepted+=1;lin=None
            lam=min(1e8,max(1e-8,lam*(.5 if rho>.75 else 2. if rho<.25 else 1.)))
            trace.append({'seconds':time.perf_counter()-start,'cost':F})
            if accepted in capture:parents[accepted]={'state':s.copy(),'lambda':lam,'cost':F}
        else:rejected+=1;lam=min(1e8,lam*4.)
    elapsed=time.perf_counter()-start
    return s,{'cost':F,'hit':F<=target,'seconds':elapsed,'accepted':accepted,'rejected':rejected,'invalid_trials':invalid,
        'fallback_points':fallbacks,'path_seconds':path_seconds,'lambda':lam,'trace':trace,'attempts':attempts},parents
