import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,numpy as np
from paths import ROOT,load_packed,write_json
from reference_ba import Linearization,valid_cost
from geometry import retract,dot,project
from curvature import second_directional
from lm_checkpoints import solve
from stiffness import components,add_penalty,penalty_rows

rows=[];algebra=[]
cases=[c for c in json.loads((ROOT/'cases.json').read_text()) if c['family']!='bal']
for case in cases:
    initial,obs=load_packed(ROOT/case['input'])
    _,_,parents=solve(initial,obs,case['target'],capture=[2,4]);parents[0]={'state':initial,'lambda':.1}
    for k,parent in sorted(parents.items()):
        s=parent['state'];lam=parent['lambda'];lin=Linearization(s,obs);dc,dp=lin.factor(lam).solve()
        comp,K,b=components(s,lin,dc,dp)
        rel=abs(comp['total']-comp['direct'])/max(1.,abs(comp['direct']))
        assert rel<1e-10
        # Compare the analytic positive factor to a dense eigen-decomposition.
        eig,V=np.linalg.eigh(K);expected=(V*np.maximum(eig,0.)[:,None,:])@V.transpose(0,2,1)
        norm=np.linalg.norm(b,axis=1);kap=np.maximum(0,b[:,2]+norm);v=b.copy();v[:,2]+=norm
        nv=np.linalg.norm(v,axis=1);v=np.divide(v,nv[:,None],out=np.zeros_like(v),where=nv[:,None]>1e-30)
        actual=kap[:,None,None]*v[:,:,None]*v[:,None,:]
        err=np.linalg.norm(expected-actual)/max(np.linalg.norm(expected),1.)
        assert err<1e-12
        base_cost=valid_cost(retract(s,dc,dp),obs);augmented=[]
        for kind in ['stiffness','trace_depth']:
            new=Linearization(s,obs);old_gc=new.gc.copy();old_Dc=new.Dc.copy();old_Dp=new.Dp.copy()
            jc,jp,meta=add_penalty(s,new,kind);dca,dpa=new.factor(lam).solve()
            np.testing.assert_array_equal(new.gc,old_gc);np.testing.assert_array_equal(new.Dc,old_Dc);np.testing.assert_array_equal(new.Dp,old_Dp)
            jd=new.jd(dca,dpa);pred=-dot(new.r,jd)-.5*dot(jd,jd)
            penal=np.einsum('nki,ni->nk',jc,dca[new.ci])+np.einsum('nki,ni->nk',jp,dpa[new.pi])
            augmented.append({'kind':kind,'trial_cost':valid_cost(retract(s,dca,dpa),obs),'original_gn_prediction':pred,
                'augmented_prediction':pred-.5*dot(penal,penal),**meta})
        assert abs(augmented[0]['trace']-augmented[1]['trace'])<1e-8*max(1.,augmented[0]['trace'])
        row={'id':case['id'],'family':case['family'],'k':k,'lambda':lam,**comp,
            'excess_over_gn':comp['total']/comp['gn'],'perspective_fraction':comp['perspective']/comp['total'] if comp['total']!=0 else None,
            'severe':comp['total']>=comp['gn'],'baseline_trial_cost':base_cost,'augmented':augmented,
            'decomposition_relative_error':rel,'rank1_factor_relative_error':err}
        rows.append(row)
        if k==0:
            exact=second_directional(s,obs,dc,dp);r=project(s,obs,6)[0];errors=[]
            for h in [1e-2,3e-3,1e-3,3e-4,1e-4]:
                fd=(project(retract(s,dc,dp,h),obs,6)[0]-2*r+project(retract(s,dc,dp,-h),obs,6)[0])/h**2
                errors.append(np.linalg.norm(fd-exact)/max(np.linalg.norm(exact),1.))
            assert min(errors)<2e-5,(case['id'],errors)
            algebra.append({'id':case['id'],'finite_difference_errors':errors})
severe=[r for r in rows if r['severe']];families=sorted(set(r['family'] for r in severe))
fraction=np.median([r['perspective_fraction'] for r in severe]) if severe else None
gate=len(severe)>=4 and len(families)>=2 and fraction>=.5
write_json(ROOT/'stiffness_diagnostic.json',{'rows':rows,'finite_difference_checks':algebra,'algebra_passed':True,
    'gate':{'passed':gate,'severe_parents':len(severe),'families':families,'median_perspective_fraction':fraction}})
print('stiffness gate',gate,'severe',len(severe),'families',families,'median fraction',fraction,flush=True)
