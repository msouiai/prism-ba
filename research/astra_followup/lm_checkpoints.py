"""Ordinary reference LM with faithful accepted-state checkpoints."""
import time
from paths import ROOT
from geometry import retract,dot
from reference_ba import Linearization,valid_cost

def solve(initial,obs,target,lam=.1,known_cost=None,capture=(),cap=3.,max_attempts=200):
    start=time.perf_counter(); state=initial.copy()
    F=valid_cost(state,obs) if known_cost is None else known_cost
    lin=None; accepted=rejected=0; trace=[{'seconds':0.,'cost':F}]; checkpoints={}; attempts=[]
    for i in range(max_attempts):
        if F<=target or time.perf_counter()-start>=cap:break
        if lin is None:lin=Linearization(state,obs)
        factor=lin.factor(lam);dc,dp=factor.solve();trial=retract(state,dc,dp)
        cost=valid_cost(trial,obs);jd=lin.jd(dc,dp);pred=-dot(lin.r,jd)-.5*dot(jd,jd)
        rho=(F-cost)/pred if pred>0 else float('-inf')
        good=pred>0 and rho>.1
        attempts.append({'lambda':lam,'parent_cost':F,'cost':cost,'prediction':pred,'rho':rho,'accepted':good})
        if good:
            state=trial;F=cost;accepted+=1;lin=None
            lam=min(1e8,max(1e-8,lam*(.5 if rho>.75 else 2. if rho<.25 else 1.)))
            trace.append({'seconds':time.perf_counter()-start,'cost':F})
            if accepted in capture:
                checkpoints[accepted]={'state':state.copy(),'cost':F,'lambda':lam,
                    'accepted':accepted,'rejected':rejected,'prefix_seconds':time.perf_counter()-start}
        else:rejected+=1;lam=min(1e8,lam*4.)
    elapsed=time.perf_counter()-start
    return state,{'cost':F,'lambda':lam,'hit':F<=target,'seconds':elapsed,'accepted':accepted,'rejected':rejected,
                  'attempts':attempts,'trace':trace},checkpoints
