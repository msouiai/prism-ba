"""Analytic rank-one positive perspective curvature and exact decomposition."""
import numpy as np
from paths import ROOT
from geometry import project,skew,dot
from reference_ba import accumulate
from curvature import second_directional
from joint_paths import velocity

def components(s,lin,dc,dp):
    r,q,_,_,P,W=project(s,lin.obs,6,True)
    if np.any(s.intr[:,1:]!=0):raise ValueError('pinhole diagnostic only')
    Jq=W@P;a=np.einsum('nki,nk->ni',Jq,r);b=-a/q[:,2,None]
    e=np.array([0.,0.,1.]);K=b[:,:,None]*e[None,None,:]+e[None,:,None]*b[:,None,:]
    dq=velocity(s,lin,dc,dp)
    RX=q-s.t[lin.ci];RdX=np.einsum('nij,nj->ni',s.R[lin.ci],dp[lin.pi]);omega=dc[lin.ci,:3]
    q2=np.cross(omega,np.cross(omega,RX))+2*np.cross(omega,RdX)
    persp=dot(dq,np.einsum('nij,nj->ni',K,dq));pose=dot(a,q2)
    direct=dot(r,second_directional(s,lin.obs,dc,dp));jd=lin.jd(dc,dp)
    return {'gn':dot(jd,jd),'perspective':persp,'pose':pose,'total':persp+pose,'direct':direct},K,b

def penalty_rows(s,lin,kind='stiffness'):
    r,q,_,_,P,W=project(s,lin.obs,6,True)
    if np.any(s.intr[:,1:]!=0):raise ValueError('pinhole positive-curvature candidate only')
    a=np.einsum('nki,nk->ni',W@P,r);b=-a/q[:,2,None];norm=np.linalg.norm(b,axis=1)
    kappa=np.maximum(0.,b[:,2]+norm);v=b.copy();v[:,2]+=norm
    vn=np.linalg.norm(v,axis=1);v=np.divide(v,vn[:,None],out=np.zeros_like(v),where=vn[:,None]>1e-30)
    row=np.sqrt(kappa)[:,None]*v
    RX=q-s.t[lin.ci]
    def make(l):
        jc=np.zeros((len(q),1,6));jp=np.zeros((len(q),1,3))
        jc[:,0,:3]=np.einsum('ni,nij->nj',l,-skew(RX));jc[:,0,3:]=l
        jp[:,0,:]=np.einsum('ni,nij->nj',l,s.R[lin.ci])
        jc[lin.ci==0]=0;jp[lin.pi==0,:,2]=0
        trace=np.sum(jc[:,0,:]**2/lin.Dc[lin.ci])+np.sum(jp[:,0,:]**2/lin.Dp[lin.pi])
        return jc,jp,trace
    jc,jp,tr=make(row)
    if kind=='trace_depth':
        depth=np.zeros_like(row);depth[:,2]=1/q[:,2]
        dc,dp,trdepth=make(depth);factor=np.sqrt(tr/trdepth) if trdepth>0 else 0.
        return dc*factor,dp*factor,{'trace':tr,'depth_multiplier':factor**2}
    if kind!='stiffness':raise ValueError(kind)
    return jc,jp,{'trace':tr,'positive_eigenvalue_max':np.max(kappa)}

def add_penalty(s,lin,kind='stiffness'):
    jc,jp,meta=penalty_rows(s,lin,kind)
    B,C,E=accumulate(lin.ci,lin.pi,jc,jp,lin.nc,lin.np)
    lin.B+=B;lin.C+=C;lin.E+=E
    return jc,jp,meta
