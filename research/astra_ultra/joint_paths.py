import numpy as np
from paths import ROOT
from geometry import retract
from projective_paths import chart_vectors,projective_retract
from point_relaxation import polish

def hosts(lin):
    first=np.full(lin.np,len(lin.pi),int)
    np.minimum.at(first,lin.pi,np.arange(len(lin.pi)))
    if np.any(first==len(lin.pi)):raise ValueError('unobserved point')
    return lin.ci[first]

def velocity(s,lin,dc,dp):
    RX=lin.q-s.t[lin.ci]
    return np.cross(dc[lin.ci,:3],RX)+dc[lin.ci,3:]+np.einsum('nij,nj->ni',s.R[lin.ci],dp[lin.pi])

def candidate(s,lin,dc,dp,lam,arm,alpha=1.,oracle=False):
    trial=retract(s,dc,dp,alpha);meta={'fallback_points':0}
    if arm=='xyz':return trial,meta
    if arm=='anchored':
        trial,meta['fallback_points']=projective_retract(s,dc,dp,chart_vectors(s,lin,'anchored'),alpha)
        return trial,meta
    if arm=='moving_host':
        a=hosts(lin);RX=np.einsum('nij,nj->ni',s.R[a],s.X);q=RX+s.t[a]
        dq=np.cross(dc[a,:3],RX)+dc[a,3:]+np.einsum('nij,nj->ni',s.R[a],dp)
        h=np.einsum('ij,ij->i',q,dq)/np.sum(q*q,axis=1)
        den=1-alpha*h;bad=(den<.25)|~np.isfinite(den);den[bad]=1.
        qs=q+alpha*dq/den[:,None]
        X=np.einsum('nji,nj->ni',trial.R[a],qs-trial.t[a])
        bad|=~np.isfinite(X).all(axis=1);bad[0]=True
        X[bad]=trial.X[bad];trial.X=X
        meta['fallback_points']=int(np.count_nonzero(bad[1:]));return trial,meta
    if arm=='observed_polish':return polish(trial,lin.obs,steps=1),meta
    if arm!='virtual_ray':raise ValueError(arm)
    dq=velocity(s,lin,dc,dp);q=lin.q
    u=-q[:,:2]/q[:,2,None]
    du=-dq[:,:2]/q[:,2,None]+q[:,:2]*dq[:,2,None]/q[:,2,None]**2
    virtual=u+alpha*du
    B=np.zeros((len(q),2,3));B[:,0,0]=1;B[:,1,1]=1;B[:,:,2]=virtual
    weight=s.intr[lin.ci,0]/q[:,2]
    A=(B@trial.R[lin.ci])*weight[:,None,None]
    qlin=np.einsum('nij,nj->ni',trial.R[lin.ci],trial.X[lin.pi])+trial.t[lin.ci]
    residual=np.einsum('nij,nj->ni',B,qlin)*weight[:,None]
    H=np.zeros((lin.np,3,3));g=np.zeros((lin.np,3))
    np.add.at(H,lin.pi,np.einsum('nki,nkj->nij',A,A))
    np.add.at(g,lin.pi,np.einsum('nki,nk->ni',A,residual))
    mu=0. if oracle else lam
    H[:,np.arange(3),np.arange(3)]+=mu*lin.Dp
    good=np.isfinite(H).all(axis=(1,2))&np.isfinite(g).all(axis=1);good[0]=False
    if oracle:
        inv=1/np.sqrt(lin.Dp);e=np.linalg.eigvalsh(H*inv[:,:,None]*inv[:,None,:])
        good&=e[:,0]>1e-10*e[:,-1]
    delta=np.zeros_like(g)
    try:
        L=np.linalg.cholesky(H[good]);delta[good]=np.linalg.solve(L.transpose(0,2,1),np.linalg.solve(L,-g[good,:,None]))[...,0]
    except np.linalg.LinAlgError:
        # Rare per-point fallback preserves healthy tracks if one block fails.
        for p in np.flatnonzero(good):
            try:
                L=np.linalg.cholesky(H[p]);delta[p]=np.linalg.solve(L.T,np.linalg.solve(L,-g[p]))
            except np.linalg.LinAlgError:good[p]=False
    good&=np.isfinite(delta).all(axis=1);delta[~good]=0
    trial.X+=delta
    meta['fallback_points']=int(np.count_nonzero(~good[1:]));return trial,meta
