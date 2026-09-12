"""Fixed-chart, fixed-metric coherent FP64 ROS2/LM witness reference."""
from pathlib import Path
import hashlib
import sys
import time
import numpy as np
from scipy import sparse
from scipy.linalg import block_diag,cho_factor,cho_solve

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'analysis'))
from audit_capture import CHART
sys.path.insert(0,str(ROOT/'coarse'))
from spectrum import point_qr,point_inverse

GAMMA=1+1/np.sqrt(2)


def left_jacobian(q):
    q=np.asarray(q);theta=np.linalg.norm(q,axis=1);t2=theta*theta
    a=np.empty_like(theta);b=np.empty_like(theta);small=theta<1e-4
    a[small]=.5-t2[small]/24+t2[small]**2/720
    b[small]=1/6-t2[small]/120+t2[small]**2/5040
    a[~small]=(1-np.cos(theta[~small]))/t2[~small]
    b[~small]=(theta[~small]-np.sin(theta[~small]))/(theta[~small]*t2[~small])
    K=CHART.skew(q)
    return np.eye(3)[None]+a[:,None,None]*K+b[:,None,None]*(K@K)


def sums(values,indices,n):
    return np.column_stack([np.bincount(indices,weights=values[:,j],minlength=n) for j in range(values.shape[1])])


class Problem:
    def __init__(self,cameras,X,ci,pi,uv,E,Dp):
        self.base=cameras;self.X=X;self.ci=ci;self.pi=pi;self.uv=uv
        self.nc=len(cameras.R);self.np=len(X);self.ncf=9*self.nc;self.n=self.ncf+3*self.np
        self.E=np.asarray(E);self.Dp=np.asarray(Dp)
        self.D=np.r_[1/self.E.reshape(-1)**2,self.Dp.reshape(-1)]
        if np.any(self.D<=0) or not np.isfinite(self.D).all():raise ValueError('D must be positive and finite')

    def split(self,q):return q[:self.ncf].reshape(self.nc,9),q[self.ncf:].reshape(self.np,3)

    def state(self,q):
        dc,dp=self.split(q)
        return self.base.retract(dc),self.X+dp

    def jacobians(self,q):
        c,X=self.state(q);chart=CHART.make_chart(X,c,'euclidean')
        residual,Jc,Jp,Y=CHART.observation_jacobians(c,chart.H,chart.T,self.ci,self.pi,self.uv)
        qc,_=self.split(q);Jl=left_jacobian(qc[:,:3])
        Jc[:,:,:3]=Jc[:,:,:3]@Jl[self.ci]
        if not all(np.isfinite(x).all() for x in (residual,Jc,Jp,Y)):raise FloatingPointError('nonfinite stage residual/Jacobian')
        return c,residual,Jc,Jp,Y

    def gradient(self,q):
        _,r,Jc,Jp,_=self.jacobians(q)
        gc=sums(np.einsum('nri,nr->ni',Jc,r),self.ci,self.nc)
        gp=sums(np.einsum('nri,nr->ni',Jp,r),self.pi,self.np)
        return np.r_[gc.reshape(-1),gp.reshape(-1)]

    def cost(self,q):
        c,X=self.state(q);total=np.longdouble(0);invalid=0
        for start in range(0,len(self.ci),50000):
            sl=slice(start,start+50000);ci=self.ci[sl];pi=self.pi[sl]
            Y=np.einsum('nij,nj->ni',c.R[ci],X[pi])+c.t[ci]
            pred=CHART.project_jacobian(Y,c.intrinsics[ci])[0]
            r=pred-self.uv[sl];finite=np.isfinite(r).all(axis=1);invalid+=int(np.count_nonzero(~finite))
            total+=.5*np.sum(r*r,dtype=np.longdouble)
        return float(total) if not invalid else np.inf,invalid

    def camera_norm(self,d):return float(np.linalg.norm(d[:self.ncf]/self.E.reshape(-1)))


class Model:
    def __init__(self,problem,q):
        start=time.perf_counter();self.p=problem;self.q=q.copy()
        c,self.r,self.Jc,self.Jp,Y=problem.jacobians(q)
        ci,pi=problem.ci,problem.pi;nc,np_=problem.nc,problem.np
        counts=np.bincount(ci,minlength=nc)
        r2=np.sum((Y[:,:2]/Y[:,2,None])**2,axis=1)
        avg=np.maximum(np.bincount(ci,weights=r2,minlength=nc)/np.maximum(counts,1),1e-12)
        self.prior=np.zeros((nc,9));active=counts>0
        self.prior[active,6]=1/(.5*np.abs(c.intrinsics[active,0])+1e-3)**2
        self.prior[active,7]=avg[active]**2
        self.U=np.zeros((nc,9,9))
        for i in range(nc):
            loc=self.Jc[ci==i].reshape(-1,9)
            self.U[i]=loc.T@loc+np.diag(self.prior[i])
        gc=sums(np.einsum('nri,nr->ni',self.Jc,self.r),ci,nc)
        gp=sums(np.einsum('nri,nr->ni',self.Jp,self.r),pi,np_)
        self.g=np.r_[gc.reshape(-1),gp.reshape(-1)]
        cross=np.einsum('nri,nrj->nij',self.Jc,self.Jp)
        rows=np.broadcast_to(9*ci[:,None,None]+np.arange(9)[None,:,None],cross.shape).reshape(-1)
        cols=np.broadcast_to(3*pi[:,None,None]+np.arange(3)[None,None,:],cross.shape).reshape(-1)
        self.W=sparse.coo_matrix((cross.reshape(-1),(rows,cols)),shape=(9*nc,3*np_)).tocsr()
        self.assembly_seconds=time.perf_counter()-start

    def prediction(self,d):
        dc,dp=self.p.split(d)
        jd=np.einsum('nri,ni->nr',self.Jc,dc[self.p.ci])+np.einsum('nri,ni->nr',self.Jp,dp[self.p.pi])
        return -float(np.sum(self.r*jd+.5*jd*jd,dtype=np.longdouble))

    def normal_product(self,d,sigma):
        dc,dp=self.p.split(d);ci,pi=self.p.ci,self.p.pi
        jd=np.einsum('nri,ni->nr',self.Jc,dc[ci])+np.einsum('nri,ni->nr',self.Jp,dp[pi])
        camera=sums(np.einsum('nri,nr->ni',self.Jc,jd),ci,self.p.nc)+self.prior*dc
        point=sums(np.einsum('nri,nr->ni',self.Jp,jd),pi,self.p.np)
        return np.r_[camera.reshape(-1),point.reshape(-1)]+sigma*self.p.D*d


class System:
    def __init__(self,model,sigma):
        start=time.perf_counter();self.model=model;self.p=model.p;self.sigma=sigma
        if not sigma>0:raise ValueError('positive stage damping required')
        qr=time.perf_counter()
        self.R,self.Rinv,self.counts=point_qr(model.Jp,self.p.pi,sigma*self.p.Dp)
        self.point_qr_seconds=time.perf_counter()-qr
        ids=np.arange(self.p.np)
        Rsp=sparse.bsr_matrix((self.Rinv,ids,np.arange(self.p.np+1)),shape=(3*self.p.np,3*self.p.np)).tocsr()
        EW=model.W.multiply(self.p.E.reshape(-1,1)).tocsr();Q=EW@Rsp
        E=self.p.E
        A=block_diag(*[E[i,:,None]*model.U[i]*E[i,None,:]+sigma*np.eye(9) for i in range(self.p.nc)])
        A-=(Q@Q.T).toarray();self.symmetry_error=float(np.max(np.abs(A-A.T)))
        self.A=.5*(A+A.T)
        if not np.isfinite(self.A).all():raise FloatingPointError('nonfinite reduced system')
        self.factor=cho_factor(self.A,lower=True,check_finite=True)
        self.factor_seconds=time.perf_counter()-start
        self.solve_calls=0;self.refinement_corrections=0;self.solve_seconds=0

    def direct(self,rhs):
        bc,bp=self.p.split(rhs)
        point=point_inverse(self.Rinv,bp)
        reduced=self.p.E.reshape(-1)*(bc.reshape(-1)-self.model.W@point.reshape(-1))
        z=cho_solve(self.factor,reduced,check_finite=False)
        dc=self.p.E.reshape(-1)*z
        dp=point_inverse(self.Rinv,(bp.reshape(-1)-self.model.W.T@dc).reshape(self.p.np,3))
        return np.r_[dc,dp.reshape(-1)]

    def solve(self,rhs):
        start=time.perf_counter();self.solve_calls+=1
        if not np.isfinite(rhs).all():raise FloatingPointError('nonfinite stage RHS')
        step=self.direct(rhs);den=max(np.linalg.norm(rhs/np.sqrt(self.p.D)),1e-300)
        history=[]
        for attempt in range(6):
            residual=rhs-self.model.normal_product(step,self.sigma)
            rel=float(np.linalg.norm(residual/np.sqrt(self.p.D))/den);history.append(rel)
            if np.isfinite(rel) and rel<=1e-10:break
            if attempt==5 or not np.isfinite(residual).all():break
            step+=self.direct(residual);self.refinement_corrections+=1
        elapsed=time.perf_counter()-start;self.solve_seconds+=elapsed
        result=dict(relative_full_normal_residual=history[-1],refinement_history=history,
                    corrections=len(history)-1,seconds=elapsed,certified=bool(history[-1]<=1e-10 and np.isfinite(step).all()))
        if not result['certified']:raise LinearCertificateError(result)
        return step,result

    def feasible(self,raw,rhs,radius):
        norm=self.p.camera_norm(raw);alpha=min(1,radius/norm) if norm>0 else 1.
        dc=alpha*raw[:self.p.ncf];bp=rhs[self.p.ncf:]
        dp=point_inverse(self.Rinv,(bp-self.model.W.T@dc).reshape(self.p.np,3))
        return np.r_[dc,dp.reshape(-1)],dict(raw_camera_norm=norm,feasible_camera_norm=self.p.camera_norm(np.r_[dc,dp.reshape(-1)]),camera_clip_scale=alpha)


class LinearCertificateError(RuntimeError):
    def __init__(self,record):self.record=record;super().__init__('full normal residual certificate failed: '+str(record))


def trial(model,system,raw,rhs,radius):
    feasible,norms=system.feasible(raw,rhs,radius)
    completion=(model.normal_product(feasible,system.sigma)-rhs)[model.p.ncf:]
    denominator=max(np.linalg.norm(rhs/np.sqrt(model.p.D)),1e-300)
    completion_rel=float(np.linalg.norm(completion/np.sqrt(model.p.D[model.p.ncf:]))/denominator)
    if not np.isfinite(completion_rel) or completion_rel>1e-10:
        raise LinearCertificateError(dict(clipped_point_completion_relative_full_rhs=completion_rel))
    initial,invalid0=model.p.cost(model.q);rawcost,invalidraw=model.p.cost(model.q+raw)
    cost,invalid=model.p.cost(model.q+feasible);pred=model.prediction(feasible);rawpred=model.prediction(raw)
    gain=initial-cost;rho=gain/pred if pred!=0 else np.nan
    accepted=bool(np.isfinite(cost) and pred>0 and rho>.1 and gain>0)
    rec=dict(initial_cost=initial,raw_cost=rawcost,raw_prediction=rawpred,raw_true_decrease=initial-rawcost,
             raw_rho=(initial-rawcost)/rawpred if rawpred!=0 else np.nan,
             feasible_cost=cost,prediction=pred,true_decrease=gain,rho=rho,
             accepted=accepted,accepted_cost=cost if accepted else initial,
             accepted_decrease=gain if accepted else 0.,invalid_initial_projections=invalid0,
             invalid_raw_projections=invalidraw,invalid_feasible_projections=invalid,
             point_completion_relative_full_rhs=completion_rel,
             raw_direction_sha256=hashlib.sha256(raw.tobytes()).hexdigest(),
             feasible_direction_sha256=hashlib.sha256(feasible.tobytes()).hexdigest(),**norms)
    return model.q+feasible if accepted else model.q.copy(),rec


def run_arm(problem,lam,radius,arm):
    begin=time.perf_counter();q=np.zeros(problem.n);records=[];models=[];systems=[]
    if arm in ('lm1','lm2'):
        for _ in range(1 if arm=='lm1' else 2):
            m=Model(problem,q);s=System(m,lam);models.append(m);systems.append(s)
            raw,cert=s.solve(-m.g);q,record=trial(m,s,raw,-m.g,radius)
            record['linear_certificate']=cert;records.append(record)
    elif arm=='ros2':
        m=Model(problem,q);s=System(m,lam/GAMMA);models.append(m);systems.append(s)
        b1=-m.g;k1,cert1=s.solve(b1)
        stage=k1/GAMMA;grad_start=time.perf_counter();gstage=problem.gradient(stage)
        gradient_seconds=time.perf_counter()-grad_start
        b2=-gstage-2*(lam/GAMMA)*problem.D*k1;k2,cert2=s.solve(b2)
        raw=(3*k1+k2)/(2*GAMMA);br=(3*b1+b2)/(2*GAMMA)
        combined=br-m.normal_product(raw,lam/GAMMA)
        combined_relative=float(np.linalg.norm(combined/np.sqrt(problem.D))/max(np.linalg.norm(br/np.sqrt(problem.D)),1e-300))
        if not np.isfinite(combined_relative) or combined_relative>1e-10:raise LinearCertificateError(dict(combination_relative_residual=combined_relative))
        q,record=trial(m,s,raw,br,radius)
        record.update(stage1_linear_certificate=cert1,stage2_linear_certificate=cert2,
                      combination_relative_residual=combined_relative,
                      first_stage_camera_norm=problem.camera_norm(k1),second_stage_camera_norm=problem.camera_norm(k2),
                      first_stage_full_D_norm=float(np.linalg.norm(np.sqrt(problem.D)*k1)),
                      second_stage_full_D_norm=float(np.linalg.norm(np.sqrt(problem.D)*k2)),
                      internal_stage_camera_norm=problem.camera_norm(stage),internal_stage_cost=problem.cost(stage)[0],
                      stage_gradient_seconds=gradient_seconds,stage_damping=lam/GAMMA,
                      completion_rhs='(3*b1+b2)/(2*gamma)')
        records.append(record)
    else:raise ValueError(arm)
    initial=records[0]['initial_cost'];cost=records[-1]['accepted_cost'];elapsed=time.perf_counter()-begin
    return dict(status='ok',arm=arm,cost=cost,score_init=initial,accepted_decrease=initial-cost,
                accepted_decrease_per_cpu_second=(initial-cost)/elapsed,cpu_total_seconds=elapsed,steps=records,
                assembly_seconds=sum(m.assembly_seconds for m in models),factor_seconds=sum(s.factor_seconds for s in systems),
                point_qr_seconds=sum(s.point_qr_seconds for s in systems),linear_solve_seconds=sum(s.solve_seconds for s in systems),
                factor_count=len(systems),stage_solve_calls=sum(s.solve_calls for s in systems),
                refinement_corrections=sum(s.refinement_corrections for s in systems))
