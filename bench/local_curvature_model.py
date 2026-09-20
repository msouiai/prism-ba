"""Fixed-state BAL retraction and exact 2D box minimization (including indefinite H)."""
import numpy as np,struct,pathlib

def box_minimum(g,H,radius):
 """Global quadratic min on [0,radius]^2 by edges and interior stationarity."""
 g=np.asarray(g,dtype=np.longdouble);H=np.asarray(H,dtype=np.longdouble)
 candidates=[np.array([a,b],dtype=np.longdouble) for a in [0,radius] for b in [0,radius]]
 for i in [0,1]:
  j=1-i
  if H[i,i]>0:
   for fixed in [0,radius]:
    z=np.zeros(2,dtype=np.longdouble);z[j]=fixed;z[i]=np.clip(-(g[i]+H[i,j]*fixed)/H[i,i],0,radius);candidates.append(z)
 det=H[0,0]*H[1,1]-H[0,1]**2
 if det>0 and H[0,0]>0:
  z=np.array([(H[0,1]*g[1]-H[1,1]*g[0])/det,(H[0,1]*g[0]-H[0,0]*g[1])/det])
  if np.all(z>=0) and np.all(z<=radius):candidates.append(z)
 q=lambda z:g@z+np.longdouble(.5)*z@H@z
 return np.asarray(min(candidates,key=q),dtype=float)

class FixedDirection:
 def __init__(self,stem,obs):
  stem=pathlib.Path(stem)
  with stem.with_suffix('.state').open('rb') as f:
   assert f.read(8)==b'PRISMS01';self.nc,self.np,self.no=struct.unpack('<QQQ',f.read(24))
   self.R=np.fromfile(f,'<f8',9*self.nc).reshape(self.nc,3,3);self.t=np.fromfile(f,'<f8',3*self.nc).reshape(self.nc,3)
   X=np.fromfile(f,'<f8',3*self.np).reshape(self.np,3);self.intr=np.fromfile(f,'<f8',3*self.nc).reshape(3,self.nc);assert not f.read(1)
  d=np.fromfile(stem.with_suffix('.step'),'<f8');assert len(d)==9*self.nc+3*self.np
  self.dc=d[:9*self.nc].reshape(self.nc,9);dp=d[9*self.nc:].reshape(self.np,3)
  self.ci=obs[:,0].astype(int);pi=obs[:,1].astype(int);self.pi=pi;self.uv=obs[:,2:4]
  assert len(obs)==self.no and np.all(self.intr[2]==0)
  self.RX=np.einsum('nij,nj->ni',self.R[self.ci],X[pi]);self.RdX=np.einsum('nij,nj->ni',self.R[self.ci],dp[pi])
  self.z0=(self.RX+self.t[self.ci])[:,2];self.cache={};self.evals=0
 def residual(self,a,b):
  w=a*self.dc[:,:3];K=np.zeros((self.nc,3,3));K[:,0,1]=-w[:,2];K[:,0,2]=w[:,1];K[:,1,0]=w[:,2];K[:,1,2]=-w[:,0];K[:,2,0]=-w[:,1];K[:,2,1]=w[:,0]
  theta=np.linalg.norm(w,axis=1);E=np.eye(3)+np.sinc(theta/np.pi)[:,None,None]*K+(.5*np.sinc(theta/(2*np.pi))**2)[:,None,None]*(K@K)
  q=np.einsum('nij,nj->ni',E[self.ci],self.RX+(b if np.ndim(b)==0 else b[self.pi,None])*self.RdX)+self.t[self.ci]+a*self.dc[self.ci,3:6]
  with np.errstate(over='ignore',divide='ignore',invalid='ignore'):
   xy=-q[:,:2]/q[:,2,None];r2=np.sum(xy*xy,axis=1);intr=self.intr.T[self.ci]+a*self.dc[self.ci,6:9]*np.array([1,1,0]);scale=intr[:,0]*(1+intr[:,1]*r2+intr[:,2]*r2*r2);res=xy*scale[:,None]-self.uv
  return res,q[:,2]
 def jacobian_directions(self,a=0.,b=0.):
  w=a*self.dc[:,:3];K=np.zeros((self.nc,3,3));K[:,0,1]=-w[:,2];K[:,0,2]=w[:,1];K[:,1,0]=w[:,2];K[:,1,2]=-w[:,0];K[:,2,0]=-w[:,1];K[:,2,1]=w[:,0]
  theta=np.linalg.norm(w,axis=1);E=np.eye(3)+np.sinc(theta/np.pi)[:,None,None]*K+(.5*np.sinc(theta/(2*np.pi))**2)[:,None,None]*(K@K)
  rotated=np.einsum('nij,nj->ni',E[self.ci],self.RX+(b if np.ndim(b)==0 else b[self.pi,None])*self.RdX)
  q=rotated+self.t[self.ci]+a*self.dc[self.ci,3:6];xy=-q[:,:2]/q[:,2,None];r2=np.sum(xy*xy,axis=1)
  intr=self.intr.T[self.ci]+a*self.dc[self.ci,6:9]*np.array([1,1,0]);f=intr[:,0];k=intr[:,1];scale=f*(1+k*r2)
  camera=np.cross(self.dc[self.ci,:3],rotated)+self.dc[self.ci,3:6]
  point=np.einsum('nij,nj->ni',E[self.ci],self.RdX)
  result=[]
  for dq,is_camera in [(camera,True),(point,False)]:
   dxy=-(dq[:,:2]*q[:,2,None]-q[:,:2]*dq[:,2,None])/q[:,2,None]**2
   dr2=2*np.sum(xy*dxy,axis=1);ds=f*k*dr2
   if is_camera:ds+=self.dc[self.ci,6]*(1+k*r2)+f*self.dc[self.ci,7]*r2
   result.append(scale[:,None]*dxy+xy*ds[:,None])
  return result
 def evaluate(self,a,b):
  key=(float(a),float(b))
  if key not in self.cache:
   res,z=self.residual(a,b);per=.5*np.sum(res*res,axis=1);total=float(np.sum(per,dtype=np.longdouble));top=min(10,len(per));ids=np.argpartition(per,-top)[-top:]
   self.cache[key]=dict(a=key[0],b=key[1],cost=total,depth_flips=int(np.sum(z*self.z0<0)),min_abs_depth=float(np.min(np.abs(z))),top10_cost_share=float(np.sum(per[ids])/total) if total>0 else 0,top10_ids=ids.tolist());self.evals+=1
  return self.cache[key]
