"""Exact directional second residual derivative for Snavely k2=0 retraction."""
import numpy as np
def second_residual(R,t,X,intr,dc,dp):
    RX=np.einsum('nij,nj->ni',R,X);Rp=np.einsum('nij,nj->ni',R,dp)
    w=dc[:,:3];Y=RX+t;v=np.cross(w,RX)+dc[:,3:6]+Rp
    a=np.cross(w,np.cross(w,RX))+2*np.cross(w,Rp)
    z=Y[:,2,None];u=-Y[:,:2]/z
    du=-(v[:,:2]+u*v[:,2,None])/z
    ddu=-(a[:,:2]+u*a[:,2,None]+2*du*v[:,2,None])/z
    q=np.sum(u*u,axis=1);dq=2*np.sum(u*du,axis=1)
    ddq=2*np.sum(du*du+u*ddu,axis=1)
    f,k=intr[:,0,None],intr[:,1];df,dk=dc[:,6,None],dc[:,7]
    h=(1+k*q)[:,None];dh=(dk*q+k*dq)[:,None];ddh=(2*dk*dq+k*ddq)[:,None]
    return f*(ddu*h+2*du*dh+u*ddh)+2*df*(du*h+u*dh)

def check():
    from scipy.spatial.transform import Rotation
    rng=np.random.default_rng(20260912);n=50
    R=Rotation.from_rotvec(.1*rng.normal(size=(n,3))).as_matrix();t=.1*rng.normal(size=(n,3));X=rng.normal(size=(n,3));X[:,2]-=10
    intr=np.c_[np.full(n,500.),np.full(n,.01),np.zeros(n)]
    dc=.03*rng.normal(size=(n,9));dc[:,8]=0;dp=.03*rng.normal(size=(n,3))
    def residual(h):
        Rh=Rotation.from_rotvec(h*dc[:,:3]).as_matrix()@R
        Y=np.einsum('nij,nj->ni',Rh,X+h*dp)+t+h*dc[:,3:6]
        u=-Y[:,:2]/Y[:,2,None];q=(u*u).sum(axis=1);ih=intr+h*dc[:,6:9]
        return ih[:,0,None]*u*(1+ih[:,1]*q)[:,None]
    exact=second_residual(R,t,X,intr,dc,dp);errors=[]
    for h in [.01,.005,.0025]:
        fd=(residual(h)-2*residual(0)+residual(-h))/h**2
        errors.append(float(np.linalg.norm(fd-exact)/np.linalg.norm(exact)))
    assert errors[-1]<1e-6,errors
    return dict(passed=True,h=[.01,.005,.0025],relative_errors=errors)
if __name__=='__main__':
    import json
    print(json.dumps(check(),indent=2))
