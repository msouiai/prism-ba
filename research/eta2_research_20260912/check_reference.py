#!/usr/bin/env python3
"""Tiny dense reference verifies the native Jacobian products and full step."""
import argparse,csv,json,sys
from pathlib import Path
import numpy as np
from scipy.linalg import block_diag
from scipy.spatial.transform import Rotation
P=Path(__file__).resolve().parent
sys.path.insert(0,str(P.parent/'geometry_agenda'))
from geometry import State,project,retract,dot
from reference_ba import synthetic
def generate():
    _,state,obs=synthetic(20260912,'depth',nc=4,np_=24)
    state.intr[:,1]=[.001,-.002,.003,-.001]
    p=P/'build/toy.txt'
    with p.open('w') as f:
        f.write(f'{len(state.R)} {len(state.X)} {len(obs)}\n')
        for c,j,u,v in obs:f.write(f'{int(c)} {int(j)} {u:.17g} {v:.17g}\n')
        for c in range(len(state.R)):
            values=np.r_[Rotation.from_matrix(state.R[c]).as_rotvec(),state.t[c],state.intr[c]]
            for v in values:f.write(f'{v:.17g}\n')
        for v in state.X.ravel():f.write(f'{v:.17g}\n')
    print(p)
def check(folder):
    folder=Path(folder);meta={k:float(v) for k,v in (l.split('=') for l in (folder/'metadata.txt').read_text().splitlines())}
    nc,np_,no=(int(meta[k]) for k in ['ncam','npt','nobs']);n=9*nc+3*np_
    def arr(name,shape):return np.fromfile(folder/name,'<f8').reshape(shape)
    state=State(arr('R_state.f64',(nc,3,3)),arr('t_state.f64',(nc,3)),arr('X_state.f64',(np_,3)),arr('intr_state.f64',(3,nc)).T)
    with (P/'build/toy.txt').open() as f:f.readline();obs=np.loadtxt(f,max_rows=no)
    r,q,jc,jp,*_=project(state,obs,9,True);ci=obs[:,0].astype(int);pi=obs[:,1].astype(int)
    J=np.zeros((2*no,n))
    for o in range(no):J[2*o:2*o+2,9*ci[o]:9*ci[o]+9]=jc[o];J[2*o:2*o+2,9*nc+3*pi[o]:9*nc+3*pi[o]+3]=jp[o]
    normal=J.T@J;grad=J.T@r.ravel();H=arr('Hcc.f64',(nc,9,9));E=arr('E.f64',(nc*9,));C=arr('Cdiag.f64',(np_,3));lam=meta['lambda']
    U=block_diag(*H);V=normal[9*nc:,9*nc:].copy();W=normal[:9*nc,9*nc:]
    pointd=lam*np.maximum(C,1e-3*C.mean(axis=1)[:,None]);V.flat[::len(V)+1]+=pointd.ravel()
    Winv=np.linalg.solve(V,W.T);vinvg=np.linalg.solve(V,grad[9*nc:])
    A=E[:,None]*(U-W@Winv)*E[None,:]+lam*np.eye(9*nc)
    b=-E*(grad[:9*nc]-W@vinvg);z=np.linalg.solve(A,b);dc=(E*z).reshape(nc,9)
    dp=-np.linalg.solve(V,grad[9*nc:]+W.T@dc.ravel()).reshape(np_,3)
    dref=np.r_[dc.ravel(),dp.ravel()];rows=[]
    for native in csv.DictReader((folder/'native_directions.csv').open()):
        d=arr(native['arm']+'-'+native['rep']+'.step',(n,));dca=d[:9*nc].reshape(nc,9);dpa=d[9*nc:].reshape(np_,3)
        rt=project(retract(state,dca,dpa),obs,9)[0];cost=.5*dot(rt,rt);pred=-dot(grad,d)-.5*dot(J@d,J@d)
        row=dict(arm=native['arm'],rep=int(native['rep']),cost=cost,prediction=pred,
          native_cost_relative=abs(cost-float(native['cost']))/max(1,cost),
          native_pred_relative=abs(pred-float(native['prediction']))/max(1,abs(pred)))
        assert row['native_cost_relative']<1e-9 and row['native_pred_relative']<1e-9,row
        if native['arm']=='exact':
            zz=dca.ravel()/E;row['cpu_true_residual']=np.linalg.norm(A@zz-b)/np.linalg.norm(b)
            row['relative_direction_error']=np.linalg.norm(d-dref)/np.linalg.norm(dref)
            assert row['cpu_true_residual']<2e-9 and row['relative_direction_error']<1e-7,row
            assert native['certified']=='1'
        rows.append(row)
    out=dict(rows=rows,min_eigenvalue=float(np.linalg.eigvalsh(A)[0]),symmetry_error=float(np.linalg.norm(A-A.T)/np.linalg.norm(A)),passed=True)
    (folder/'dense_check.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--generate',action='store_true');ap.add_argument('--folder');a=ap.parse_args()
    generate() if a.generate else check(a.folder)
