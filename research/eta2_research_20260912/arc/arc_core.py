"""Full D-whitened fixed-Krylov cubic witness reference; no native edits."""
import importlib.util
import sys
from pathlib import Path
import time
import hashlib
import numpy as np
from scipy.optimize import brentq
from scipy.linalg import norm as stable_norm

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ros_core_for_arc',ROOT/'rosenbrock/core.py')
ROS=importlib.util.module_from_spec(spec);sys.modules[spec.name]=ROS;spec.loader.exec_module(ROS)
Problem,Model,CHART=ROS.Problem,ROS.Model,ROS.CHART


def krylov(product,g,dimension=64):
    begin=time.perf_counter();n=len(g);k=min(dimension,n);gnorm=float(np.linalg.norm(g))
    if not np.isfinite(gnorm) or gnorm<=0:raise ValueError('nonzero finite gradient required')
    Q=np.empty((n,k),order='F');AQ=np.empty((n,k),order='F');Q[:,0]=-g/gnorm
    product_seconds=0.;orth_seconds=0.;breakdown=False;actual=k;beta_history=[]
    for j in range(k):
        start=time.perf_counter();w=np.asarray(product(Q[:,j]));product_seconds+=time.perf_counter()-start
        if not np.isfinite(w).all():raise FloatingPointError('nonfinite full-normal product')
        AQ[:,j]=w;scale=float(np.linalg.norm(w));start=time.perf_counter();basis=Q[:,:j+1]
        for _ in range(2):w=w-basis@(basis.T@w)
        beta=float(np.linalg.norm(w));beta_history.append(beta)
        if j+1<k:
            if beta<=1e-14*max(scale,1e-300):
                actual=j+1;breakdown=True;orth_seconds+=time.perf_counter()-start;break
            Q[:,j+1]=w/beta
        orth_seconds+=time.perf_counter()-start
    Q=Q[:,:actual];AQ=AQ[:,:actual];start=time.perf_counter()
    gram=Q.T@Q;orth_error=float(np.linalg.norm(gram-np.eye(actual),ord=2))
    Traw=Q.T@AQ;sym_error=float(np.linalg.norm(Traw-Traw.T)/max(np.linalg.norm(Traw),1e-300))
    T=.5*(Traw+Traw.T);gproj=Q.T@g;orth_seconds+=time.perf_counter()-start
    if orth_error>1e-10 or sym_error>1e-10:raise RuntimeError(f'invalid basis {orth_error=} {sym_error=}')
    return Q,T,gproj,dict(dimension_requested=dimension,dimension=actual,full_products=actual,
       full_product_seconds=product_seconds,orthogonalization_and_projection_seconds=orth_seconds,
       total_seconds=time.perf_counter()-begin,orthogonality_error=orth_error,projected_symmetry_error=sym_error,
       happy_breakdown=breakdown,beta_history=beta_history,basis_bytes=int(Q.nbytes),product_storage_bytes=int(AQ.nbytes))


def cubic_root(T,g,sigma):
    begin=time.perf_counter()
    if sigma<=0 or not np.isfinite(sigma):raise ValueError('positive finite sigma required')
    e,U=np.linalg.eigh(T);h=U.T@g;floor=max(0.,-float(e[0]));calls=0
    # The BA screen is PSD. Keep the generic positive-definite shifted branch
    # without rounding away a negative eigenvalue or silently solving a hard case.
    low=max(np.nextafter(floor,np.inf),1e-300)
    def f(lam):
        nonlocal calls
        calls+=1;den=e+lam
        if np.any(den<=0):return -np.inf
        return float(lam-sigma*stable_norm(h/den))
    if f(low)>0:raise RuntimeError('unresolved cubic hard case; no model alteration allowed')
    high=max(2*low,np.sqrt(sigma*float(np.linalg.norm(g))),1e-30)
    for _ in range(2048):
        if f(high)>=0:break
        high*=2
        if not np.isfinite(high):raise FloatingPointError('cubic root bracket overflow')
    else:raise RuntimeError('cubic root not bracketed')
    rootlog=brentq(lambda t:f(np.exp(t)),np.log(low),np.log(high),xtol=1e-13,rtol=1e-14,maxiter=256)
    lam=float(np.exp(rootlog));y=-U@(h/(e+lam));norm=float(np.linalg.norm(y))
    secular=float(abs(lam-sigma*norm)/max(lam,sigma*norm,1e-300))
    residual=float(np.linalg.norm((T+lam*np.eye(len(g)))@y+g)/max(np.linalg.norm(g),1e-300))
    if secular>1e-8 or not np.isfinite(y).all():raise RuntimeError('cubic secular certificate failed')
    return y,dict(lambda_value=lam,sigma=sigma,projected_norm=norm,secular_relative_residual=secular,
        projected_stationarity_relative_residual=residual,min_projected_eigenvalue=float(e[0]),
        max_projected_eigenvalue=float(e[-1]),min_shifted_eigenvalue=float(e[0]+lam),
        scalar_function_evaluations=calls,root_bracket=[low,high],seconds=time.perf_counter()-begin)


def score(model,Q,y,lam,sigma,kind,radius,shared_seconds):
    begin=time.perf_counter();p=model.p;rootD=np.sqrt(p.D);white=Q@y;d=white/rootD
    initial,invalid0=p.cost(model.q);cost,invalid=p.cost(model.q+d);pred=model.prediction(d)
    gain=initial-cost;rho=gain/pred if pred else np.nan
    accepted=bool(np.isfinite(cost) and pred>0 and gain>0 and rho>.1)
    prodstart=time.perf_counter();fresh=model.normal_product(d,lam);product_seconds=time.perf_counter()-prodstart
    residual=(fresh+model.g)/rootD;relative=float(np.linalg.norm(residual)/max(np.linalg.norm(model.g/rootD),1e-300))
    if not np.isfinite(relative):raise FloatingPointError('nonfinite full stationarity residual')
    fullnorm=float(np.linalg.norm(white));camera_norm=p.camera_norm(d)
    linear=float(model.g@d);hquad=.5*float(d@(fresh-lam*p.D*d))
    prior_quad=.5*float(np.sum(model.prior*d[:p.ncf].reshape(p.nc,9)**2))
    quadratic=linear+hquad;cubic=quadratic+sigma*fullnorm**3/3 if kind=='arc' else None
    return dict(arm=kind,score_init=initial,raw_cost=cost,accepted_cost=cost if accepted else initial,
      true_decrease=gain,accepted_decrease=gain if accepted else 0.,prediction=pred,rho=rho,accepted=accepted,
      full_D_norm=fullnorm,camera_E_norm=camera_norm,camera_norm_over_old_radius=camera_norm/radius,
      lambda_value=lam,sigma=sigma if kind=='arc' else None,quadratic_model_with_intrinsic_prior=quadratic,
      intrinsic_prior_quadratic=prior_quad,cubic_model=cubic,
      full_stationarity_relative_residual=relative,full_stationarity_absolute_norm=float(np.linalg.norm(residual)),
      verification_full_products=1,verification_product_seconds=product_seconds,
      invalid_initial_projections=invalid0,invalid_projections=invalid,
      direction_sha256=hashlib.sha256(d.tobytes()).hexdigest(),scoring_and_verification_seconds=time.perf_counter()-begin,
      shared_setup_seconds=shared_seconds)


def run_pair(problem,lam,radius,eta_step,order):
    start=time.perf_counter();model=Model(problem,np.zeros(problem.n));rootD=np.sqrt(problem.D)
    ghat=model.g/rootD
    Q,T,gproj,basis=krylov(lambda v:model.normal_product(v/rootD,0.)/rootD,ghat,64)
    norm=float(np.linalg.norm(rootD*eta_step));sigma=lam/max(norm,1e-30)
    shared=time.perf_counter()-start;rows=[]
    for arm in order:
        armstart=time.perf_counter()
        if arm=='arc':y,root=cubic_root(T,gproj,sigma);damping=root['lambda_value']
        else:
            s=time.perf_counter();y=np.linalg.solve(T+lam*np.eye(len(T)),-gproj);damping=lam
            root=dict(seconds=time.perf_counter()-s,projected_stationarity_relative_residual=float(np.linalg.norm((T+lam*np.eye(len(T)))@y+gproj)/np.linalg.norm(gproj)))
        row=score(model,Q,y,damping,sigma,arm,radius,shared)
        row.update(projected_solve=root,arm_incremental_seconds=time.perf_counter()-armstart)
        row['standalone_cpu_seconds']=shared+row['arm_incremental_seconds']
        row['accepted_decrease_per_standalone_cpu_second']=row['accepted_decrease']/row['standalone_cpu_seconds']
        rows.append(row)
    return rows,dict(assembly_seconds=model.assembly_seconds,basis=basis,shared_setup_seconds=shared,
      paired_actual_cpu_seconds=time.perf_counter()-start,eta2_full_D_norm=norm,sigma=sigma,
      white_gradient_norm=float(np.linalg.norm(ghat)),full_dimension=problem.n)
