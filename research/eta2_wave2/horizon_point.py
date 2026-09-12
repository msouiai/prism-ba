"""W6a/b first gate on the previously identified Ladybug explosion point."""
from pathlib import Path
import importlib.util,json,sys,time
import numpy as np
from scipy.optimize import minimize_scalar
P=Path(__file__).resolve().parent;C=P.parent/'eta2_research_20260912'
sys.path.insert(0,str(C/'analysis'))
from audit_capture import load_capture_state,CHART
spec=importlib.util.spec_from_file_location('point_newton_horizon',C/'point_newton/core.py');N=importlib.util.module_from_spec(spec);spec.loader.exec_module(N)

def main():
    cap=C/'evidence/collect/ladybug-1197-capture-0';camera,X,meta=load_capture_state(cap)
    ci,pi,uv,_=CHART.load_observations('/workspace/bal/ladybug-1197.txt');j=47270;ids=np.flatnonzero(pi==j);cams=ci[ids]
    state=CHART.CameraState(camera.R[cams].copy(),camera.t[cams].copy(),camera.intrinsics[cams].copy());x=X[j:j+1].copy();obs=uv[ids]
    nc=len(camera.R);first=np.fromfile(cap/'eta2-0.step',dtype='<f8');dc=first[:9*nc].reshape(nc,9)[cams]
    c=np.arange(len(ids));p=np.zeros(len(ids),dtype=int);lam=meta['lambda'];mu=.01*2*meta['cost']/meta['nobs']
    chart=CHART.make_chart(x,state,'euclidean');r,Jc,Jp,Y=CHART.observation_jacobians(state,chart.H,chart.T,c,p,obs)
    rc=r+np.einsum('nri,ni->nr',Jc,dc);V=np.einsum('nri,nrj->ij',Jp,Jp)
    Hess=state.R.transpose(0,2,1)@N.residual_hessian_Y(Y,state.intrinsics,r)@state.R
    Q=Hess.sum(axis=0);damping=N.point_damping(V[None],lam)[0];b=-np.einsum('nri,nr->i',Jp,rc)
    sel=N.select_blocks(V[None],Q[None],damping[None],lam);H=sel['matrix'][0]
    newton=np.linalg.solve(H,b);gn=np.linalg.solve(V+np.diag(damping),b)
    depthpoint=state.R[:,2,:]/Y[:,2,None]
    RX=Y-state.t;depthcamera=(np.cross(dc[:,:3],RX)[:,2]+dc[:,5])/Y[:,2]
    Hb=H+mu*(depthpoint.T@depthpoint);bb=b+mu*np.sum(depthpoint*(1-depthcamera)[:,None],axis=0)
    barrier=np.linalg.solve(Hb,bb)
    proposed=state.retract(dc)
    def score(d):
        Yn=np.einsum('nij,nj->ni',proposed.R,x[p]+d[None])+proposed.t
        res=CHART.project_jacobian(Yn,proposed.intrinsics)[0]-obs
        jd=np.einsum('nri,ni->nr',Jc,dc)+np.einsum('nri,i->nr',Jp,d)
        cost=.5*float(np.sum(res*res));initial=.5*float(np.sum(r*r));pred=-float(np.sum(r*jd+.5*jd*jd))
        return dict(cost=cost,initial_cost=initial,decrease=initial-cost,prediction=pred,rho=(initial-cost)/pred if pred else None,
                    depths=Yn[:,2].tolist(),depth_ratios=(Yn[:,2]/Y[:,2]).tolist(),displacement=float(np.linalg.norm(d)),
                    local_accept=bool(pred>0 and initial>cost and (initial-cost)/pred>.1))
    baseline=score(newton)
    old=json.loads((C/'point_newton/results/failure_forensics.json').read_text())['top_tracks'][0]
    assert old['point']==j and abs(baseline['cost']/old['cost_candidate']-1)<1e-8
    baseY=np.einsum('nij,nj->ni',proposed.R,x[p])+proposed.t
    rate=np.einsum('nij,j->ni',proposed.R,newton)[:,2]
    poles=np.divide(-baseY[:,2],rate,out=np.full(len(rate),np.inf),where=rate!=0);positive=poles[poles>0]
    capalpha=min(1.,.99*positive.min()) if len(positive) else 1.
    rows=[]
    for rep in range(3):
        search=minimize_scalar(lambda a:score(a*newton)['cost'],bounds=(0.,capalpha),method='bounded',options={'xatol':1e-12,'maxiter':64})
        alphas=[0.,capalpha,float(search.x)];alpha=min(alphas,key=lambda a:score(a*newton)['cost'])
        for name,d in [('point_newton',newton),('gn',gn),('shadow_barrier',barrier),('pole_ray_search',alpha*newton)]:
            rows.append(dict(rep=rep,arm=name,mu=mu,**score(d),alpha=alpha if name=='pole_ray_search' else 1.))
    result=dict(scene='ladybug-1197',point=j,observations=len(ids),lambda_value=lam,mu_rule='.01*2F/nobs',mu=mu,
        expected_bad_point_cost=old['cost_candidate'],first_positive_pole=float(positive.min()) if len(positive) else None,alpha_cap=capalpha,
        rows=rows,shadow_pass=score(barrier)['cost']<baseline['initial_cost'],
        scope='Single prescribed track; local acceptance is not global solver acceptance. Ray objective is exact, bounded minimizer is numerical, not globally certified.')
    (P/'horizon_point_results.json').write_text(json.dumps(result,indent=2)+'\n')
    for r in rows[:4]:print(r['arm'],'cost',r['cost'],'depth_ratio',min(r['depth_ratios']),'local_accept',r['local_accept'],flush=True)
if __name__=='__main__':main()
