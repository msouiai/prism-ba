import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import pathlib,sys,subprocess,json,numpy as np
P=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(P.parent/'astra_ultra'))
from cases import orbit_case
from geometry import project,retract

def write_input(path,s,tr,obs,dc,dp,D,tau):
    nc=len(s.R);np_=len(s.X);pi=obs[:,1].astype(int);order=np.argsort(pi,kind='stable');offset=np.r_[0,np.cumsum(np.bincount(pi,minlength=np_))]
    with path.open('wb') as f:
        for a,dt in [(np.array([nc,np_,len(obs)]),'<i4'),(offset,'<i4'),(order,'<i4'),(obs[:,0],'<i4'),(obs[:,2:],'<f8')]:np.asarray(a,dtype=dt).tofile(f)
        for st in [s,tr]:
            for a in [st.R,st.t,st.X,st.intr.T]:np.asarray(a,dtype='<f8').tofile(f)
        for a in [D,np.r_[dc.ravel(),dp.ravel()],tau]:np.asarray(a,dtype='<f8').tofile(f)

def oracle(s,tr,obs,dc,dp,D,tau,mode):
    ci=obs[:,0].astype(int);pi=obs[:,1].astype(int);out=dp.copy();np_=len(dp)
    if mode in [1,2]:
        r,q,Jc,Jp,*_=project(tr,obs,9,True)
        for p in range(np_):
            idx=np.flatnonzero(pi==p)
            if mode==2:
                C=-np.einsum('nji,nj->ni',tr.R[ci[idx]],tr.t[ci[idx]])
                rays=tr.X[p]-C;rays/=np.linalg.norm(rays,axis=1)[:,None]
                if len(idx)<2 or min(rays@rays[0])<np.cos(np.deg2rad(5)):continue
            J=Jp[idx].reshape(-1,3);e=r[idx].ravel();H=J.T@J
            H+=np.diag(1e-6*np.maximum(np.diag(H),1e-3*max(np.trace(H)/3,1e-30)))
            try:dx=np.linalg.solve(H,-J.T@e)
            except np.linalg.LinAlgError:continue
            best=.5*e@e
            for alpha in [1.,.5,.25]:
                st=tr.copy();st.X[p]+=alpha*dx
                er=project(st,obs[idx],9)[0];F=.5*np.sum(er**2)
                if F<best:out[p]=dp[p]+alpha*dx;best=F
    else:
        q=np.einsum('nij,nj->ni',s.R[ci],s.X[pi])+s.t[ci]
        dq=np.cross(dc[ci,:3],q-s.t[ci])+dc[ci,3:6]+np.einsum('nij,nj->ni',s.R[ci],dp[pi])
        u=-q[:,:2]/q[:,2,None];du=-(dq[:,:2]+u*dq[:,2,None])/q[:,2,None];vh=u+du
        rr=np.sum(u*u,axis=1);f,k1,k2=s.intr[ci].T;d=1+k1*rr+k2*rr*rr;h=k1+2*k2*rr
        W=f[:,None,None]*(d[:,None,None]*np.eye(2)+2*h[:,None,None]*u[:,:,None]*u[:,None,:])/q[:,2,None,None]
        B=np.tile(np.eye(2,3),(len(obs),1,1));B[:,:,2]=vh
        A=W@B@tr.R[ci];qlin=np.einsum('nij,nj->ni',tr.R[ci],tr.X[pi])+tr.t[ci]
        e=np.einsum('nij,nj->ni',W@B,qlin)
        for p in range(np_):
            ix=pi==p;J=A[ix].reshape(-1,3);er=e[ix].ravel();floor=tau*sum(D[p])/3;floor=floor if floor>0 else 1e-32
            H=J.T@J+np.diag(np.maximum(tau*D[p],1e-3*floor))
            try:out[p]+=np.linalg.solve(H,-J.T@er)
            except np.linalg.LinAlgError:pass
    return np.r_[dc.ravel(),out.ravel()]

def main():
    b=P/'build';cmd=['nvcc','-O2','-std=c++17','-arch=sm_89','-I'+str(P),'-I'+str(b),str(P/'kernel_check.cu'),'-o',str(b/'kernel-check')]
    subprocess.run(cmd,check=True)
    rows=[];rng=np.random.default_rng(911)
    for family,scale,degenerate in [('low_parallax',.04,False),('joint',.04,False),('depth',0.,False),('depth',.01,True)]:
        _,s,obs=orbit_case(510,family,np_=33)
        if degenerate:s.R[:]=s.R[0];s.t[:]=s.t[0]
        s.intr[:,1]=.03;s.intr[:,2]=-.002
        dc=rng.normal(0,scale,size=(len(s.R),9));dc[:,6]*=10;dc[:,7:]*=.001;dp=rng.normal(0,scale,size=s.X.shape)
        tr=retract(s,dc,dp);_,_,_,Jp,*_=project(s,obs,9,True);D=np.zeros_like(dp)
        np.add.at(D,obs[:,1].astype(int),np.sum(Jp*Jp,axis=1));tau=.003
        write_input(b/'check-input.bin',s,tr,obs,dc,dp,D,tau)
        for mode in [1,2,3]:
            p=subprocess.run([str(b/'kernel-check'),str(b/'check-input.bin'),str(b/'check-output.bin'),str(mode)],capture_output=True,text=True,check=True)
            got=np.fromfile(b/'check-output.bin',dtype='<f8');want=oracle(s,tr,obs,dc,dp,D,tau,mode)
            err=np.linalg.norm(got-want)/max(1.,np.linalg.norm(want));assert np.isfinite(got).all() and err<1e-7,(family,mode,err)
            assert np.array_equal(got[:dc.size],dc.ravel())
            rows.append(dict(family=family,scale=scale,degenerate=degenerate,mode=mode,relative_error=err,**json.loads(p.stdout)))
    (P/'kernel_validation.json').write_text(json.dumps(rows,indent=2)+'\n');print(rows)
if __name__=='__main__':main()
