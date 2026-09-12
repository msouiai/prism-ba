"""Dense independent audit of native second-RHS plumbing on a tiny BAL case."""
from pathlib import Path
import json,os,subprocess,sys
import numpy as np
P=Path(__file__).resolve().parent;C=P.parent/'eta2_research_20260912'
sys.path.insert(0,str(C/'analysis'))
from audit_capture import CHART
from geodesic_math import second_residual

def main():
    q=P/'geodesic_native_validation';q.mkdir(exist_ok=True)
    champ=json.loads((P.parent/'eta2_champion/champion.json').read_text())
    flags={k:v for k,v in os.environ.items() if not k.startswith('OCA_')}
    flags.update(champ['flags'],OCA_GEODESIC='1',OCA_GEODESIC_AUDIT=str(q/'toy'))
    cli=list(champ['cli']);cli[cli.index('--max_iter')+1]='1'
    cmd=[str(P/'build/prism-geodesic-native'),'--problem',str(C/'build/toy.txt'),*cli]
    with (q/'stdout.log').open('w') as out,(q/'stderr.log').open('w') as err:subprocess.run(cmd,env=flags,stdout=out,stderr=err,check=True)
    nc,np_,no,lam,relative=np.loadtxt(q/'toy.meta');nc,np_,no=int(nc),int(np_),int(no);n=9*nc+3*np_
    def read(name,shape,dtype='<f8'):return np.fromfile(q/('toy.'+name),dtype=dtype).reshape(shape)
    R,t,X=read('R',(nc,3,3)),read('t',(nc,3)),read('X',(np_,3))
    intr=np.c_[read('f',nc),read('k1',nc),np.zeros(nc)]
    ci,pi=read('ci',no,'<i4'),read('pi',no,'<i4');Y=np.einsum('nij,nj->ni',R[ci],X[pi])+t[ci]
    pred,dY,dintr=CHART.project_jacobian(Y,intr[ci]);RX=Y-t[ci]
    jc=np.concatenate((dY@(-CHART.skew(RX)),dY,dintr),axis=2);jc[:,:,8]=0;jp=dY@R[ci]
    J=np.zeros((2*no,n))
    for o in range(no):J[2*o:2*o+2,9*ci[o]:9*ci[o]+9]=jc[o];J[2*o:2*o+2,9*nc+3*pi[o]:9*nc+3*pi[o]+3]=jp[o]
    first=read('first',n);dc=first[:9*nc].reshape(nc,9);dp=first[9*nc:].reshape(np_,3)
    r2=second_residual(R[ci],t[ci],X[pi],intr[ci],dc[ci],dp[pi]).ravel()
    gradient=J.T@r2;g=np.r_[read('gc',9*nc),read('gp',3*np_)]
    E=read('E',9*nc);U=np.zeros((9*nc,9*nc));V=np.zeros((3*np_,3*np_))
    h=read('Hcc',(nc,9,9));rf=read('Rf',(np_,6))
    for c in range(nc):U[9*c:9*c+9,9*c:9*c+9]=h[c]
    for j,r in enumerate(rf):
        L=np.array([[r[0],0,0],[r[1],r[3],0],[r[2],r[4],r[5]]]);V[3*j:3*j+3,3*j:3*j+3]=L@L.T
    W=np.zeros((9*nc,3*np_));fr=read('Gp',(9,3,no),'<f4');fci,fpi=read('fci',no,'<i4'),read('fpi',no,'<i4')
    for o in range(no):W[9*fci[o]:9*fci[o]+9,3*fpi[o]:3*fpi[o]+3]+=fr[:,:,o]
    rhs=E*(g[:9*nc]-W@np.linalg.solve(V,g[9*nc:]))
    A=E[:,None]*(U-W@np.linalg.solve(V,W.T))*E[None,:]+lam*np.eye(9*nc)
    x=read('x',9*nc);d2=read('d2',n)
    def rel(a,b):return float(np.linalg.norm(a-b)/max(np.linalg.norm(b),1e-300))
    answer=dict(analytic_second_relative=rel(read('second',2*no),r2),gradient_relative=rel(g,gradient),
      reduced_rhs_relative=rel(read('rhs',9*nc),rhs),product_relative=rel(read('Ap',9*nc),A@x),
      independent_relative_residual=rel(A@x,rhs),logged_relative_residual=float(relative),
      physical_camera_relative=rel(d2[:9*nc],-E*x),point_completion_relative=rel(V@d2[9*nc:]+W.T@d2[:9*nc],-g[9*nc:]),
      command=cmd,flags={k:v for k,v in flags.items() if k.startswith('OCA_')})
    assert max(answer[k] for k in ('analytic_second_relative','gradient_relative','reduced_rhs_relative','product_relative','physical_camera_relative','point_completion_relative'))<1e-8,answer
    assert answer['independent_relative_residual']<=.505 and abs(answer['independent_relative_residual']-relative)<1e-8,answer
    answer['passed']=True;(q/'audit.json').write_text(json.dumps(answer,indent=2)+'\n');print(json.dumps(answer,indent=2))
    # Known historical CLI allocations are not part of this intervention's memory audit.
    mem=['compute-sanitizer','--tool','memcheck','--leak-check','no','--error-exitcode','86',*cmd]
    with (q/'memcheck.log').open('w') as out:subprocess.run(mem,env=flags,stdout=out,stderr=subprocess.STDOUT,check=True)
    assert 'ERROR SUMMARY: 0 errors' in (q/'memcheck.log').read_text()
    answer['memcheck_passed']=True;(q/'audit.json').write_text(json.dumps(answer,indent=2)+'\n')
if __name__=='__main__':main()
