import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,numpy as np
from paths import ROOT,load_packed,write_json
from reference_ba import Linearization,valid_cost
from scipy.linalg import cho_solve
from geometry import dot,retract
from lm_checkpoints import solve

RULES=['eta05','eta08','nash','oracle_full','oracle_camera','bound_full','bound_camera']

def eligible(rule,relative,gain,P0,epsilon,bound,k,last_gain):
    if rule=='eta05':return relative<=.5
    if rule=='eta08':return relative<=.8
    if rule=='nash':return gain>0 and k*(gain-last_gain)/gain<.1
    credit=gain+(P0 if rule.endswith('full') else 0.)
    error=epsilon if rule.startswith('oracle') else bound
    return credit>0 and error<=.1*credit

def frozen(s,obs,lam):
    lin=Linearization(s,obs);fac=lin.factor(lam);S=fac.S
    gp=lin.gp.copy();gp[0,2]=0;cp=fac.point_solve(gp[...,None])[...,0]
    b=-lin.gc[1:].ravel()+fac.E@cp.ravel();P0=.5*dot(gp,cp)
    D=lam*lin.Dc[1:].ravel();minbound=np.linalg.eigvalsh(S-np.diag(D)).min()
    assert minbound>=-1e-9*max(np.linalg.norm(S),1.)
    camera=lin.B[1:].copy();camera[:,np.arange(6),np.arange(6)]+=lam*lin.Dc[1:]
    L=np.linalg.cholesky(camera)
    def pre(r):return np.linalg.solve(L.transpose(0,2,1),np.linalg.solve(L,r.reshape(-1,6,1))).ravel()
    nb=np.linalg.norm(b);x=np.zeros_like(b);r=b.copy();z=pre(r);p=z.copy();rz=dot(r,z)
    optimum=P0+.5*dot(b,cho_solve(fac.factor,b))
    records=[];chosen={};attempted={a:0 for a in RULES};last_true_gain=last_rec_gain=0.
    F0=valid_cost(s,obs);max_identity=0.;max_bound_violation=0.
    for k in range(1,129):
        ap=S@p;den=dot(p,ap)
        if not (den>0 and np.isfinite(den)):break
        alpha=rz/den;x+=alpha*p;r-=alpha*ap
        if k%10==0:r=b-S@x
        # True residual/energy below are oracle instrumentation, separately costed.
        true=b-S@x;relative=np.linalg.norm(true)/nb;rec_relative=np.linalg.norm(r)/nb
        gain=.5*dot(x,b+true);rec_gain=.5*dot(x,b+r)
        epsilon=.5*dot(true,cho_solve(fac.factor,true));bound=.5*np.sum(true*true/D);rec_bound=.5*np.sum(r*r/D)
        assert epsilon<=bound*(1+1e-9)+1e-8*max(optimum,1.)
        max_bound_violation=max(max_bound_violation,epsilon-bound)
        assert abs(gain+P0+epsilon-optimum)<1e-7*max(optimum,1.)
        accepted=[]
        for rule in RULES:
            if rule in chosen:continue
            # Exact epsilon is deliberately oracle-only; all other screens are cheap.
            screen=eligible(rule,rec_relative,rec_gain,P0,epsilon,rec_bound,k,last_rec_gain)
            if not screen:continue
            if k%10:attempted[rule]+=1
            if not eligible(rule,relative,gain,P0,epsilon,bound,k,last_true_gain):continue
            dc=np.zeros((lin.nc,6));dc[1:]=x.reshape(-1,6)
            dp=-fac.point_solve((gp+(fac.E.T@x).reshape(lin.np,3))[...,None])[...,0]
            jd=lin.jd(dc,dp)
            physical=-dot(lin.gc,dc)-dot(gp,dp)-.5*dot(jd,jd)-.5*lam*(dot(lin.Dc*dc,dc)+dot(lin.Dp*dp,dp))
            err=abs(physical-(P0+gain))/max(1.,abs(P0+gain));max_identity=max(max_identity,err)
            assert err<1e-9
            trial_cost=valid_cost(retract(s,dc,dp),obs)
            pred=-dot(lin.r,jd)-.5*dot(jd,jd)
            chosen[rule]={'iteration':k,'products':k+k//10+attempted[rule],'true_exit_checks':attempted[rule],
                'relative_residual':relative,'full_gain':P0+gain,'camera_gain':gain,'epsilon':epsilon,'upper_bound':bound,
                'fraction_optimal_full_decrement':(P0+gain)/optimum,'trial_cost':trial_cost,'valid':np.isfinite(trial_cost),
                'true_cost_decrease':F0-trial_cost,'rho':(F0-trial_cost)/pred if pred>0 else None,'selected':True}
            accepted.append(rule)
        records.append({'iteration':k,'relative_residual':relative,'recurrence_relative':rec_relative,'camera_gain':gain,
            'full_gain':P0+gain,'epsilon':epsilon,'upper_bound':bound,'selected_rules':accepted})
        if relative<=1e-10 or len(chosen)==len(RULES):break
        z=pre(r);nrz=dot(r,z)
        if not (nrz>0 and np.isfinite(nrz)):break
        p=z+(nrz/rz)*p;rz=nrz;last_true_gain=gain;last_rec_gain=rec_gain
    for rule in RULES:
        if rule not in chosen:chosen[rule]={'selected':False,'exit_checks':attempted[rule]}
    return {'P0':P0,'optimal_full_decrement':optimum,'point_credit_fraction':P0/optimum,
        'camera_dof':len(b),'lambda':lam,'initial_cost':F0,'lower_bound_min_eigenvalue':minbound,
        'quadratic_identity_max_relative_error':max_identity,'max_bound_violation':max_bound_violation,
        'rules':chosen,'trace':records}

if __name__=='__main__':
    rows=[]
    for case in json.loads((ROOT/'cases.json').read_text()):
        root=ROOT.parent if case.get('input_from_research_root') else ROOT
        s,obs=load_packed(root/case['input']);_,_,parents=solve(s,obs,case['target'],capture=[2,4]);parents[0]={'state':s,'lambda':.1}
        for k,parent in sorted(parents.items()):
            row={'id':case['id'],'family':case['family'],'k':k,**frozen(parent['state'],obs,parent['lambda'])}
            rows.append(row)
        write_json(ROOT/'energy_results.json',{'rows':rows})
        print('energy',case['id'],flush=True)
    summary=[]
    for rule in RULES:
        valid=[];opportunities=[];new_invalid=[];offset=[]
        for r in rows:
            a=r['rules'][rule];b=r['rules']['eta05']
            if not a['selected'] or not b['selected']:continue
            valid.append((a,b))
            if b['valid'] and not a['valid']:new_invalid.append((r['id'],r['k']))
            if a['products']<=.8*b['products'] and b['true_cost_decrease']>0 and a['true_cost_decrease']>=.9*b['true_cost_decrease']:
                opportunities.append((r['id'],r['family'],r['k']))
                other=r['rules']['bound_camera']
                if rule=='bound_full' and other['selected'] and a['iteration']<other['iteration']:offset.append((r['id'],r['k']))
        families=sorted(set(x[1] for x in opportunities))
        summary.append({'rule':rule,'selected':sum(r['rules'][rule]['selected'] for r in rows),'parents':len(rows),
            'median_products':np.median([a['products'] for a,b in valid]),'median_products_vs_eta05':np.median([a['products']/b['products'] for a,b in valid]),
            'opportunities':opportunities,'opportunity_families':families,'new_invalid':new_invalid,'offset_changes_in_opportunities':offset,
            'gate':len(opportunities)>=4 and len(families)>=2 and not new_invalid and (rule!='bound_full' or bool(offset))})
    write_json(ROOT/'energy_summary.json',summary);print(summary,flush=True)
