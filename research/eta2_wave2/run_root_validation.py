"""Independent full-normal/score audit before native radius-fitting grid."""
from pathlib import Path
import csv,fcntl,json,os,subprocess,sys,time
import numpy as np
P=Path(__file__).resolve().parent;C=P.parent/'eta2_research_20260912';F=P.parent/'eta2_champion'
sys.path[:0]=[str(C/'analysis'),str(C/'coarse'),str(C/'separable_rescue')]
from audit_capture import load_capture_state,CHART
from diagnostic import read_array,verify_baseline,sha256
from core import audit

def run(scene,rep):
    old=P/'witness_proposals'/f'{scene}-{rep}';out=P/'root_validation'/f'{scene}-{rep}';out.mkdir(parents=True,exist_ok=True)
    if (out/'audit.json').exists():return json.loads((out/'audit.json').read_text())
    manifest=json.loads((old/'manifest.json').read_text());flags=dict(manifest['flags']);flags.pop('OCA_W2_GEODESIC',None);flags['OCA_W2_OUTPUT']=str(out)
    binary=P/'build/prism-root-validation';bm=json.loads((P/'root_validation_manifest.json').read_text());assert sha256(binary)==bm['binary_sha256']
    cmd=[str(binary),*manifest['command'][1:]];env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','MF_DEBUG'))};env.update(flags)
    (out/'manifest.json').write_text(json.dumps(dict(command=cmd,flags=flags,build_manifest=bm,capture=manifest),indent=2)+'\n')
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        with (out/'stdout.log').open('w') as log,(out/'stderr.log').open('w') as err:subprocess.run(cmd,env=env,stdout=log,stderr=err,check=True,timeout=3600)
    cap=Path(flags['OCA_W2_WITNESS']);camera,X,meta=load_capture_state(cap);nc,np_=len(camera.R),len(X);n=9*nc+3*np_
    ci,pi,uv,_=CHART.load_observations('/workspace/bal/'+scene+'.txt');E=read_array(cap/'E.f64',(nc,9));cd=read_array(cap/'Cdiag.f64',(np_,3));Dp=np.maximum(cd,.001*np.maximum(cd.mean(axis=1),1e-32)[:,None])
    native=list(csv.DictReader((out/'directions.csv').open()));rows=[]
    for name,arm in [('coupled','lambda_coupled'),('frozen','lambda_frozen_tau')]:
        row=next(r for r in native if r['arm']==arm and r['rep']=='0');lam,tau=float(row['lambda']),float(row['tau'])
        raw=np.fromfile(out/(name+'_raw.step'),dtype='<f8');d=np.fromfile(out/(name+'.step'),dtype='<f8');assert len(d)==n
        dc,dp=raw[:9*nc].reshape(nc,9),raw[9*nc:].reshape(np_,3)
        normal_c=np.zeros((nc,9));normal_p=np.zeros((np_,3));g_c=np.zeros_like(normal_c);g_p=np.zeros_like(normal_p);r2sum=np.zeros(nc);count=np.bincount(ci,minlength=nc)
        def add(dest,ids,x):
            for k in range(x.shape[1]):dest[:,k]+=np.bincount(ids,weights=x[:,k],minlength=len(dest))
        for start in range(0,len(ci),50000):
            sl=slice(start,start+50000);c=ci[sl];p=pi[sl]
            Y=np.einsum('nij,nj->ni',camera.R[c],X[p])+camera.t[c];pix,dY,di=CHART.project_jacobian(Y,camera.intrinsics[c]);r=pix-uv[sl]
            jc=np.concatenate((dY@(-CHART.skew(Y-camera.t[c])),dY,di),axis=2);jc[:,:,8]=0;jp=dY@camera.R[c]
            jd=np.einsum('nri,ni->nr',jc,dc[c])+np.einsum('nri,ni->nr',jp,dp[p])
            add(normal_c,c,np.einsum('nri,nr->ni',jc,jd+r));add(normal_p,p,np.einsum('nri,nr->ni',jp,jd+r))
            add(g_c,c,np.einsum('nri,nr->ni',jc,r));add(g_p,p,np.einsum('nri,nr->ni',jp,r))
            r2sum+=np.bincount(c,weights=np.sum((Y[:,:2]/Y[:,2,None])**2,axis=1),minlength=nc)
        prior=np.zeros((nc,9));active=count>0;prior[active,6]=1/(.5*np.abs(camera.intrinsics[active,0])+1e-3)**2;prior[active,7]=np.maximum(r2sum[active]/count[active],1e-12)**2
        normal_c+=(lam/E**2+prior)*dc;normal_p+=tau*Dp*dp
        nr=np.sqrt(np.sum((normal_c*E)**2)+np.sum(normal_p**2/Dp));ng=np.sqrt(np.sum((g_c*E)**2)+np.sum(g_p**2/Dp))
        score=audit(camera,X,ci,pi,uv,d[:9*nc].reshape(nc,9),d[9*nc:].reshape(np_,3),E)
        delta=abs(score['cost']-float(row['cost']))/max(1,score['cost'])
        rows.append(dict(arm=arm,lambda_value=lam,tau=tau,full_normal_relative=float(nr/ng),score=score,native_score_relative_error=delta,
                         native_source_certified=bool(int(row['certified'])),raw_sha256=sha256(out/(name+'_raw.step')),step_sha256=sha256(out/(name+'.step'))))
    ans=dict(scene=scene,rep=rep,rows=rows,passed=all(r['native_score_relative_error']<1e-8 and r['full_normal_relative']<1e-5 for r in rows),
      qualification='Source reduced solves certify1e-10; CPU full-normal1e-5 validation gate allows previously measured independent point/row arithmetic sensitivity and is not an exact-full-step claim.')
    (out/'audit.json').write_text(json.dumps(ans,indent=2)+'\n');print(scene,rep,'passed',ans['passed'],'normal',[r['full_normal_relative'] for r in rows],flush=True)
    return ans
if __name__=='__main__':
    verify_baseline();rows=[run(s,r) for s,r in [('venice-52',1)]+[('final-3068',r) for r in (0,5,6)]]
    (P/'root_validation_summary.json').write_text(json.dumps(dict(rows=rows,passed=all(r['passed'] for r in rows)),indent=2)+'\n')
