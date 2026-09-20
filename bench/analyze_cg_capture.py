#!/usr/bin/env python3
"""Fixed captured operator: exact TR solve in spans of saved CG snapshots."""
import pathlib,json,numpy as np
ROOT=pathlib.Path('/workspace/prism-tr-cg-stop/capture')
def solve(H,b,R):
 d,U=np.linalg.eigh(H);a=U.T@b;floor=max(0.,-d[0]);tol=1e-13*max(1.,abs(d).max());z=np.divide(a,d+floor,out=np.zeros_like(a),where=d+floor>tol)
 if np.all(np.abs(a[d+floor<=tol])<=1e-13*max(1,np.linalg.norm(b))) and np.linalg.norm(z)<=R:
  if floor>0:z[0]+=np.sqrt(max(0,R*R-z@z))
  return U@z,floor
 lo=floor;hi=floor+max(1.,np.linalg.norm(b)/R)
 while np.linalg.norm(a/(d+hi))>R:hi=floor+2*(hi-floor)
 for _ in range(100):
  mid=(lo+hi)/2
  if np.linalg.norm(a/(d+mid))>R:lo=mid
  else:hi=mid
 return U@(a/(d+hi)),hi

def main():
 dims=(ROOT/'dimensions.txt').read_text().split();n=9*int(dims[1]);sigma,R=float(dims[4]),float(dims[5]);b=np.fromfile(ROOT/'b',dtype='float64');assert len(b)==n
 cols=[];ops=[];rows=[]
 for depth in [16,32,64,128]:
  x=np.fromfile(ROOT/f'depth-{depth}.cg_x',dtype='float64');r=np.fromfile(ROOT/f'depth-{depth}.cg_residual',dtype='float64');sx=b-r-sigma*x;cols.append(x);ops.append(sx)
  X=np.column_stack(cols);SX=np.column_stack(ops);Q,T=np.linalg.qr(X,mode='reduced');SQ=np.linalg.solve(T.T,SX.T).T;rawH=Q.T@SQ;H=.5*(rawH+rawH.T);rhs=Q.T@b;y,lam=solve(H,rhs,R);candidate=Q@y;sc=SQ@y;gradient=sc-b
  pred=b@candidate-.5*candidate@sc;fw=gradient@candidate+R*np.linalg.norm(gradient)
  candidate.tofile(ROOT/f'projected-{depth}.x');sc.tofile(ROOT/f'projected-{depth}.sx')
  rows.append(dict(depth=depth,dimension=len(cols),norm=float(np.linalg.norm(candidate)),prediction=float(pred),fw_gap=float(fw),gap_ratio=float(fw/pred),lambda_=float(lam),projected_min_eigenvalue=float(np.linalg.eigvalsh(H)[0]),projected_symmetry_error=float(np.linalg.norm(rawH-rawH.T)/max(1,np.linalg.norm(H))),projected_kkt_error=float(np.linalg.norm(H@y+lam*y-rhs)/max(1,np.linalg.norm(rhs)))))
 (ROOT/'projected-results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
