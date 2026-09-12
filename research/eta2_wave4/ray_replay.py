"""O4 affine frozen-ray scalar GN pre-test, with an explicit fixed-camera scope."""
from pathlib import Path
import json,tempfile
import numpy as np
from scipy.optimize import minimize_scalar
import attribution as A
F=A.F;P=A.P;W=A.W

def observed_ray(cam,X,c,uv):
    f,k1,k2=cam.intrinsics[c];assert k2==0
    predY=cam.R[c]@X+cam.t[c];pred=-predY[:2]/predY[2]
    qd=uv/f;rd=float(np.linalg.norm(qd))
    if rd==0:q=np.zeros(2)
    elif k1==0:q=qd
    else:
        roots=np.roots([k1,0,1,-rd]);roots=roots[(abs(roots.imag)<1e-9)&(roots.real>=0)].real
        if not len(roots):raise RuntimeError('No nonnegative radial inverse root')
        candidates=roots[:,None]*qd/rd
        q=candidates[np.argmin(np.linalg.norm(candidates-pred,axis=1))]
    center=-cam.R[c].T@cam.t[c];v=cam.R[c].T@np.r_[-q,1.]
    check=F.S.chart.project_jacobian((cam.R[c]@(center+predY[2]*v)+cam.t[c])[None],cam.intrinsics[c:c+1])[0][0]
    assert np.linalg.norm(check-uv)/max(1,np.linalg.norm(uv))<1e-7
    return center,v,float(predY[2])

def calculate(root,name,ci,pi,uv):
    folder=root/name;cam,X,meta=F.load_capture_state(folder);nc=len(cam.R);point=250233
    step=F.read_array(folder/'accepted.step',(9*nc+3*len(X),));dc=step[:9*nc].reshape(nc,9);dp=step[9*nc:].reshape(-1,3)
    obs=np.flatnonzero(pi==point);cs=ci[obs];pixels=uv[obs];oldX=X[point];new=cam.retract(dc)
    R=cam.R[cs];RX=np.einsum('nij,j->ni',R,oldX);Y=RX+cam.t[cs]
    pix,JY,JI=F.S.chart.project_jacobian(Y,cam.intrinsics[cs]);r=pix-pixels
    Jp=np.einsum('nij,njk->nik',JY,R)
    yc=np.einsum('nij,nj->ni',JY,np.cross(dc[cs,:3],RX)+dc[cs,3:6])+np.einsum('nij,nj->ni',JI,dc[cs,6:9])
    # Highest current sensitivity selects the anchor independently of its ID.
    anchor=int(np.argmax(np.sum(JY*JY,axis=(1,2))));c=int(cs[anchor]);center,v,z0=observed_ray(cam,oldX,c,pixels[anchor])
    cd=F.read_array(folder/'Cdiag.f64',(len(X),3))[point];D=np.maximum(cd,.001*max(float(cd.mean()),1e-32))*meta['tau']
    offset=center+z0*v-oldX;jv=np.einsum('nri,i->nr',Jp,v)
    rr=r+yc+np.einsum('nri,i->nr',Jp,offset)
    denom=float(np.sum(jv*jv)+np.sum(D*v*v));numer=float(np.sum(jv*rr)+np.sum(D*v*offset))
    dz=-numer/denom;restricted=center+(z0+dz)*v;repaired=restricted-oldX
    def cost(x,camera=new):
        residual,y=F.S.residual(camera,np.broadcast_to(x,(len(cs),3)),cs,pixels)
        return float(.5*np.sum(residual*residual)),residual,y
    def pred(d):
        jd=yc+np.einsum('nri,i->nr',Jp,d)
        return -float(np.sum(r*jd+.5*jd*jd))
    baseline_cost,_,baseline_y=cost(oldX+dp[point]);newcost,newres,newy=cost(restricted)
    oldraycost,oldrayres,_=cost(restricted,cam)
    # Diagnostic finite search on the same signed ray. Poles split all intervals.
    lo,hi=sorted([1e-4*z0,1e4*z0]);grid=np.sort(z0*np.logspace(-4,4,129))
    a=np.einsum('nij,j->ni',new.R[cs],center)+new.t[cs];b=np.einsum('nij,j->ni',new.R[cs],v)
    poles=-a[:,2]/b[:,2];grid=np.unique(np.r_[grid,poles[(poles>lo)&(poles<hi)]])
    best=(float('inf'),z0);evaluations=0
    def objective(z):
        nonlocal evaluations
        evaluations+=1
        with np.errstate(divide='ignore',over='ignore',invalid='ignore'):f,_,yy=cost(center+z*v)
        return f if np.isfinite(f) and np.all(yy[:,2]*Y[:,2]>0) else float('inf')
    for l,h in zip(grid[:-1],grid[1:]):
        width=h-l;l=l+width*1e-9;h=h-width*1e-9
        mid=(l+h)/2
        if not np.isfinite(objective(mid)):continue
        res=minimize_scalar(objective,bounds=(l,h),method='bounded',options={'xatol':max(1e-18,abs(z0)*1e-12),'maxiter':100})
        for z in [l,h,float(res.x)]:
            value=objective(z)
            if value<best[0]:best=value,z
    atr=json.loads((P/'attribution'/('final-e4-'+name.replace('/','-')+'.json')).read_text())
    fullpred=atr['prediction']-pred(dp[point])+pred(repaired);gain=atr['true_decrease']+baseline_cost-newcost
    return dict(label=name,anchor_camera=c,point=point,observations=obs.tolist(),
        recorded_cost=baseline_cost,restricted_gn_cost=newcost,full_restricted_prediction=fullpred,
        full_restricted_decrease=gain,full_restricted_rho=gain/fullpred,
        scalar_normal_residual=abs(denom*dz+numer)/max(1,abs(numer)),
        original_anchor_depth=z0,restricted_anchor_depth=z0+dz,
        old_anchor_ray_residual_norm=float(np.linalg.norm(oldrayres[anchor])),
        updated_anchor_residual_norm=float(np.linalg.norm(newres[anchor])),
        actual_depth_ratios=(newy[:,2]/Y[:,2]).tolist(),
        depth_signs_preserved=bool(np.all(newy[:,2]*Y[:,2]>0)),
        local_gn_point_step=repaired.tolist(),recorded_point_step=dp[point].tolist(),
        affine_chart_offset=offset.tolist(),chart_ray=v.tolist(),
        best_finite_search_cost=best[0],best_finite_search_depth=best[1],search_evaluations=evaluations,
        input_state_hashes={f.name:F.sha(f) for f in folder.iterdir() if f.is_file()},
        scope='Restricted back-substitution at prescribed native camera step, not a recomputed joint Schur solve or continued basin replay')

def main():
    F.verify_baseline();ci,pi,uv,_=F.CHART.load_observations(Path('/workspace/bal/final-3068.txt'))
    rec=json.loads((W/'miss-forensics/decision.json').read_text());assert F.sha(rec['archive'])==rec['sha256'];names=['hit/6','miss/6']
    with tempfile.TemporaryDirectory(prefix='o4-replay-',dir='/dev/shm') as t:
        root=Path(t)
        for name,raw in F.FA.decoded(rec['archive']):
            if str(Path(name).parent) in names:
                f=root/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(raw)
        rows=[calculate(root,name,ci,pi,uv) for name in names]
    gap=abs(rows[1]['recorded_cost']-rows[0]['recorded_cost']);newgap=abs(rows[1]['restricted_gn_cost']-rows[0]['restricted_gn_cost'])
    passed=newgap<.1*gap and all(r['depth_signs_preserved'] and r['full_restricted_rho']>.1 and r['full_restricted_prediction']>0 for r in rows)
    result=dict(rows=rows,recorded_point_gap=gap,restricted_point_gap=newgap,fraction_remaining=newgap/gap,native_gate_passed=passed,
                protocol_sha256=F.sha(P/'O4_REPLAY_PROTOCOL.md'),code_sha256=F.sha(__file__),
                decision='Proceed to separately registered native chart test' if passed else 'Kill native frozen-ray approximation under fixed replay gate')
    F.write(P/'o4-ray-replay.json',result);print(result)
if __name__=='__main__':main()
