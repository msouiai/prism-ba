"""Independent nonlinear and full-normal audit of saved W5 proposals."""
from pathlib import Path
import gzip,json,sys,time,tarfile
import numpy as np
P=Path(__file__).resolve().parent;C=P.parent/'eta2_research_20260912'
sys.path[:0]=[str(C/'analysis'),str(C/'coarse'),str(C/'separable_rescue')]
from audit_capture import load_capture_state,CHART
from diagnostic import read_array,verify_baseline
from core import audit

def read(folder,name,n):
    p=folder/(name+'.step.gz')
    if p.exists():
        with gzip.open(p,'rb') as f:data=f.read()
    else:
        with tarfile.open(folder/'steps.tar.xz') as tf:
            with tf.extractfile(p.name) as f:data=gzip.decompress(f.read())
    return np.frombuffer(data,dtype='<f8').copy().reshape(n)

def run(scene,rep,folder=None,analytic=False):
    cap=C/'evidence/collect'/f'{scene}-capture-{rep}';folder=folder or P/'witness_proposals'/f'{scene}-{rep}'
    camera,X,meta=load_capture_state(cap);nc,np_=len(camera.R),len(X);n=9*nc+3*np_
    ci,pi,uv,_=CHART.load_observations('/workspace/bal/'+scene+'.txt')
    E=read_array(cap/'E.f64',(nc,9));cd=read_array(cap/'Cdiag.f64',(np_,3))
    Dp=np.maximum(cd,.001*np.maximum(cd.mean(axis=1),1e-32)[:,None]);lam=meta['lambda']
    rows=[]
    def add(result,index,values):
        for k in range(values.shape[1]):result[:,k]+=np.bincount(index,weights=values[:,k],minlength=len(result))
    for r in range(3):
        start=time.perf_counter();first=read(folder,'first-'+str(r),(n,));second=read(folder,'second-'+str(r),(n,));candidate=read(folder,'geodesic-'+str(r),(n,))
        dc,dp=second[:9*nc].reshape(nc,9),second[9*nc:].reshape(np_,3)
        fdc,fdp=first[:9*nc].reshape(nc,9),first[9*nc:].reshape(np_,3)
        h=.1;stage=camera.retract(h*fdc);normal_c=np.zeros((nc,9));normal_p=np.zeros((np_,3));rhs_c=np.zeros_like(normal_c);rhs_p=np.zeros_like(normal_p)
        r2sum=np.zeros(nc);count=np.bincount(ci,minlength=nc)
        for startobs in range(0,len(ci),50000):
            sl=slice(startobs,startobs+50000);c=ci[sl];p=pi[sl]
            Y=np.einsum('nij,nj->ni',camera.R[c],X[p])+camera.t[c]
            pred,dY,dintr=CHART.project_jacobian(Y,camera.intrinsics[c]);res=pred-uv[sl]
            RX=Y-camera.t[c];Jc=np.concatenate((dY@(-CHART.skew(RX)),dY,dintr),axis=2);Jc[:,:,8]=0
            Jp=dY@camera.R[c]
            jd1=np.einsum('nri,ni->nr',Jc,fdc[c])+np.einsum('nri,ni->nr',Jp,fdp[p])
            Yh=np.einsum('nij,nj->ni',stage.R[c],X[p]+h*fdp[p])+stage.t[c]
            rh=CHART.project_jacobian(Yh,stage.intrinsics[c])[0]-uv[sl]
            if analytic:
                from geodesic_math import second_residual
                rsecond=second_residual(camera.R[c],camera.t[c],X[p],camera.intrinsics[c],fdc[c],fdp[p])
            else:rsecond=2*(rh-res-h*jd1)/h**2
            jd2=np.einsum('nri,ni->nr',Jc,dc[c])+np.einsum('nri,ni->nr',Jp,dp[p])
            add(normal_c,c,np.einsum('nri,nr->ni',Jc,jd2+rsecond));add(normal_p,p,np.einsum('nri,nr->ni',Jp,jd2+rsecond))
            add(rhs_c,c,-np.einsum('nri,nr->ni',Jc,rsecond));add(rhs_p,p,-np.einsum('nri,nr->ni',Jp,rsecond))
            r2sum+=np.bincount(c,weights=np.sum((Y[:,:2]/Y[:,2,None])**2,axis=1),minlength=nc)
        prior=np.zeros((nc,9));active=count>0;prior[active,6]=1/(.5*np.abs(camera.intrinsics[active,0])+1e-3)**2
        prior[active,7]=np.maximum(r2sum[active]/count[active],1e-12)**2
        normal_c+=(lam/E**2+prior)*dc;normal_p+=lam*Dp*dp
        numerator=np.sqrt(np.sum((normal_c*E)**2)+np.sum(normal_p**2/Dp))
        denominator=np.sqrt(np.sum((rhs_c*E)**2)+np.sum(rhs_p**2/Dp))
        cc,cp=candidate[:9*nc].reshape(nc,9),candidate[9*nc:].reshape(np_,3)
        score=audit(camera,X,ci,pi,uv,cc,cp,E)
        control=audit(camera,X,ci,pi,uv,fdc,fdp,E)
        rows.append(dict(rep=r,second_full_normal_relative=float(numerator/max(denominator,1e-300)),candidate=score,first=control,seconds=time.perf_counter()-start))
    answer=dict(scene=scene,capture_rep=rep,rows=rows,analytic_second_derivative=analytic,
        caveat=('Analytic directional RHS is recomputed independently using the actual retraction.' if analytic else
                'Finite-difference RHS is recomputed independently; cancellation in rsecond may dominate relative residual when the correction RHS is very small.'))
    (folder/'independent_geodesic.json').write_text(json.dumps(answer,indent=2,allow_nan=False)+'\n')
    print(scene,rep,'relative',[x['second_full_normal_relative'] for x in rows],'rho',[x['candidate']['rho'] for x in rows],flush=True)

if __name__=='__main__':
    verify_baseline()
    for scene,rep in [('venice-52',0)]+[('final-3068',r) for r in (0,5,6)]:run(scene,rep)
