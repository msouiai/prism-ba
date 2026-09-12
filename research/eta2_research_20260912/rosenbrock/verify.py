#!/usr/bin/env python3
"""ROS2 order, fixed-chart derivatives and coherent-system checks, before BAL."""
import json
from pathlib import Path
import numpy as np
from scipy.linalg import expm
from scipy.spatial.transform import Rotation
from core import CHART,GAMMA,Problem,Model,System,left_jacobian

P=Path(__file__).resolve().parent


def ros_step(x,h,D,Happrox,gradient):
    K=Happrox+np.diag(D)/(GAMMA*h)
    k1=np.linalg.solve(K,-gradient(x));stage=x+k1/GAMMA
    k2=np.linalg.solve(K,-gradient(stage)-2*D*k1/(GAMMA*h))
    return x+(3*k1+k2)/(2*GAMMA)


def orders(errors,hs):return [float(np.log(errors[i]/errors[i+1])/np.log(hs[i]/hs[i+1])) for i in range(len(hs)-1)]


def main():
    baseline=CHART.verify_frozen_baseline();rng=np.random.default_rng(20260912)
    hs=np.array([.01,.005,.0025,.00125]);x=np.array([.7,-.4]);D=np.array([2.,.7])
    A=np.array([[3.,.4],[.4,1.5]])
    approx=np.array([[.8,-.3],[-.3,4.]])
    quadratic=[float(np.linalg.norm(ros_step(x,h,D,approx,lambda y:A@y)-expm(-np.diag(1/D)@A*h)@x)) for h in hs]
    oq=orders(quadratic,hs);assert min(oq)>2.85,oq
    # Scalar quartic potential has xdot=-x^3/D and a closed-form flow.
    nonlinear=[]
    for h in hs:
        initial=np.array([.8]);end=ros_step(initial,h,np.array([2.]),np.array([[4.]]),lambda y:y**3)
        exact=initial/np.sqrt(1+initial**2*h)
        nonlinear.append(float(np.linalg.norm(end-exact)))
    on=orders(nonlinear,hs);assert min(on)>2.85,on
    arbitrary=[]
    for B in (np.zeros((2,2)),np.eye(2)*-2,np.array([[5.,1.],[1.,3.]])):
        errors=[float(np.linalg.norm(ros_step(x,h,D,B,lambda y:A@y)-expm(-np.diag(1/D)@A*h)@x)) for h in hs]
        o=orders(errors,hs);assert min(o)>2.8,o;arbitrary.append(dict(approximate_H=B.tolist(),local_orders=o))
    # FD Exp(q+epsilon v) = Exp(epsilon J_left(q) v) Exp(q).
    q=rng.normal(size=(32,3));q*=rng.uniform(0,3,size=(32,1))/np.maximum(np.linalg.norm(q,axis=1,keepdims=True),1e-300)
    v=rng.normal(size=(32,3));eps=1e-6
    R=Rotation.from_rotvec(q).as_matrix();dR=(Rotation.from_rotvec(q+eps*v).as_matrix()-Rotation.from_rotvec(q-eps*v).as_matrix())/(2*eps)
    analytic=CHART.skew(np.einsum('nij,nj->ni',left_jacobian(q),v))@R
    transport=float(np.linalg.norm(dR-analytic)/np.linalg.norm(analytic));assert transport<2e-8,transport
    nc,np_=3,5
    cameras=CHART.CameraState(Rotation.from_rotvec(rng.normal(scale=.05,size=(nc,3))).as_matrix(),
                             rng.normal(scale=.1,size=(nc,3)),
                             np.column_stack([np.full(nc,300.),np.full(nc,.01),np.zeros(nc)]))
    X=rng.normal(scale=.3,size=(np_,3));X[:,2]-=3
    ci=np.tile(np.arange(nc),np_);pi=np.repeat(np.arange(np_),nc)
    pc=CHART.make_chart(X,cameras,'euclidean')
    uv=CHART.observation_jacobians(cameras,pc.H,pc.T,ci,pi,np.zeros((len(ci),2)))[0]+rng.normal(size=(len(ci),2))
    p=Problem(cameras,X,ci,pi,uv,np.ones((nc,9)),np.ones((np_,3)))
    baseq=rng.normal(scale=.02,size=p.n);baseq[:p.ncf].reshape(nc,9)[:,8]=0
    direction=rng.normal(size=p.n);direction[:p.ncf].reshape(nc,9)[:,8]=0
    m=Model(p,baseq);gc=p.gradient(baseq)
    fd=(p.cost(baseq+1e-6*direction)[0]-p.cost(baseq-1e-6*direction)[0])/(2e-6)
    graderror=float(abs(fd-gc@direction)/max(1,abs(fd)));assert graderror<2e-7,graderror
    # Explicit full coherent normal matrix against independently scattered J.
    J=np.zeros((2*len(ci),p.n))
    for o,(cam,point) in enumerate(zip(ci,pi)):
        J[2*o:2*o+2,9*cam:9*cam+9]=m.Jc[o]
        J[2*o:2*o+2,p.ncf+3*point:p.ncf+3*point+3]=m.Jp[o]
    prior=np.r_[m.prior.reshape(-1),np.zeros(3*np_)];sigma=.7
    K=J.T@J+np.diag(prior+sigma*p.D);system=System(m,sigma)
    rhs=rng.normal(size=p.n);rhs[:p.ncf].reshape(nc,9)[:,8]=0
    d,cert=system.solve(rhs);dense=np.linalg.solve(K,rhs)
    error=float(np.linalg.norm(d-dense)/np.linalg.norm(dense));assert error<1e-9,error
    inside,insideinfo=system.feasible(d,rhs,2*p.camera_norm(d))
    insideerror=float(np.linalg.norm(inside-d)/np.linalg.norm(d));assert insideerror<1e-10,insideerror
    clipped,clipinfo=system.feasible(d,rhs,.25*p.camera_norm(d))
    pointres=(m.normal_product(clipped,sigma)-rhs)[p.ncf:]
    cliperror=float(np.linalg.norm(pointres)/np.linalg.norm(rhs[p.ncf:]));assert cliperror<1e-10,cliperror
    result=dict(status='passed',baseline=baseline,seed=20260912,
      coefficient_source='https://kpp.readthedocs.io/en/stable/num_methods/rosenbrock-methods.html',gamma=GAMMA,
      quadratic_local_orders=oq,nonlinear_local_orders=on,arbitrary_approximate_jacobian_cases=arbitrary,
      so3_left_jacobian_relative_error=transport,fixed_chart_gradient_relative_error=graderror,
      dense_vs_schur_direction_relative_error=error,full_normal_certificate=cert,
      unclipped_combined_rhs_completion_error=insideerror,clipped_combined_rhs_point_equation_error=cliperror,
      gpu_used=False)
    (P/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='baseline'},indent=2))


if __name__=='__main__':main()
