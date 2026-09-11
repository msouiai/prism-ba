import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import pathlib,sys,subprocess,json,numpy as np
P=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(P.parent/'astra_ultra'))
from cases import orbit_case
from reference_ba import Linearization

def main():
    b=P/'build';b.mkdir(exist_ok=True)
    subprocess.run(['nvcc','-O2','-std=c++17','-arch=sm_89','-I'+str(P),str(P/'check_sweep.cu'),'-o',str(b/'check-sweep'),'-lcublas'],check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    rng=np.random.default_rng(91131);cases=[]
    for n,lo,center in [(33,.1,.01),(63,1e-6,.01),(127,1e-8,.1)]:
        Q,_=np.linalg.qr(rng.normal(size=(n,n)));H=(Q*np.geomspace(lo,1,n))@Q.T
        cases.append((f'spd-{n}',H,rng.normal(size=n),center,1e-10,512,True))
    for family in ['depth','joint','low_parallax']:
        _,s,obs=orbit_case(520,family,np_=100);lin=Linearization(s,obs);center=.01;fac=lin.factor(center)
        D=lin.Dc[1:].ravel();E=1/np.sqrt(D);H=(fac.S-np.diag(center*D))*E[:,None]*E[None,:]
        gp=lin.gp.copy();gp[0,2]=0;rhs=lin.gc[1:].ravel()-fac.E@fac.point_solve(gp[...,None])[...,0].ravel()
        cases.append((family,H,E*rhs,center,1e-10,512,True))
    cases.extend([('zero-rhs',np.eye(33),np.zeros(33),.1,1e-10,100,True),('zero-H',np.zeros((33,33)),rng.normal(size=33),.1,1e-10,100,True),('negative',-np.eye(33),np.ones(33),.1,1e-10,100,False)])
    rows=[];e=P/'evidence/fixed';e.mkdir(parents=True,exist_ok=True)
    for name,H,rhs,center,eta,cap,want_ok in cases:
        n=len(rhs);inp=e/(name+'.bin');out=b/'check-output.bin'
        with inp.open('wb') as f:
            np.asarray([n,cap],dtype='<i4').tofile(f);np.asarray([center,eta],dtype='<f8').tofile(f);np.asarray(H,dtype='<f8').ravel(order='F').tofile(f);np.asarray(rhs,dtype='<f8').tofile(f)
        p=subprocess.run([str(b/'check-sweep'),str(inp),str(out)],text=True,capture_output=True,check=True);r=json.loads(p.stdout);r['case']=name
        assert r['ok']==want_ok,r
        if want_ok:
            got=np.fromfile(out,dtype='<f8');X=got[:5*n].reshape(5,n);actual=np.array([np.linalg.norm((H+center*10.**(j-2)*np.eye(n))@X[j]-rhs)/max(np.linalg.norm(rhs),1e-300) for j in range(5)])
            direct=np.array([np.linalg.solve(H+center*10.**(j-2)*np.eye(n),rhs) for j in range(5)])
            error=np.linalg.norm(X-direct)/max(np.linalg.norm(direct),1)
            assert r['qualified'] and max(actual)<1.1*eta and error<1e-6,(r,actual,error)
            norms=np.linalg.norm(X,axis=1);Y=X*np.minimum(1,.1/np.maximum(norms,1e-300))[:,None]
            diam=max(np.linalg.norm(Y[a]-Y[j]) for a in range(5) for j in range(a+1,5))/max(np.max(np.linalg.norm(Y,axis=1)),1e-300)
            assert abs(diam-r['clipped'])<1e-6,(r,diam)
            r.update(max_true_residual=float(max(actual)),relative_solution_error=float(error),clipped_numpy=float(diam))
        rows.append(r);print(r,flush=True)
    (P/'fixed_validation.json').write_text(json.dumps(rows,indent=2)+'\n')
if __name__=='__main__':main()
