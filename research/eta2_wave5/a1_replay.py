#!/usr/bin/env python3
"""A1 fixed-state replay: targeted nonlinear two-view repair on E4 point 250233."""
from pathlib import Path
import hashlib, json, sys, tempfile

import numpy as np
from scipy.optimize import least_squares, minimize_scalar

P = Path(__file__).resolve().parent
W4 = P.parent / "eta2_wave4"
W3 = P.parent / "eta2_wave3"
sys.path.insert(0, str(W3))
import forensics as F


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def invert_simple_radial(pixel, focal, k1, predicted_radius):
    """Return the BAL normalized coordinate on the current monotone branch."""
    distorted = np.asarray(pixel, dtype=float) / focal
    rd = float(np.linalg.norm(distorted))
    if rd == 0:
        return distorted.copy(), {"roots": [0.0], "selected_radius": 0.0}
    roots = np.roots([k1, 0.0, 1.0, -rd]) if k1 != 0 else np.array([rd])
    candidates = []
    for root in roots:
        if abs(root.imag) <= 1e-9 * max(1.0, abs(root.real)) and root.real >= 0:
            radius = float(root.real)
            scale = 1.0 + k1 * radius * radius
            error = abs(radius * scale - rd)
            monotone = 1.0 + 3.0 * k1 * radius * radius > 0
            candidates.append((error, not monotone, abs(radius-predicted_radius), radius))
    if not candidates:
        raise RuntimeError("No nonnegative real SIMPLE_RADIAL inverse")
    candidates.sort()
    radius = candidates[0][-1]
    normalized = distorted * (radius / rd)
    return normalized, {"roots": sorted(float(x[-1]) for x in candidates),
                        "selected_radius": radius,
                        "forward_error": candidates[0][0],
                        "monotone_branch": not candidates[0][1]}


def skew(v):
    x, y, z = v
    return np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]], dtype=float)


def camera_matrix(camera, index):
    return np.column_stack((camera.R[index], camera.t[index]))


def fundamental_pixel(camera, c1, c2):
    r21 = camera.R[c2] @ camera.R[c1].T
    t21 = camera.t[c2] - r21 @ camera.t[c1]
    essential = skew(t21) @ r21
    k_1_inv = np.diag([1.0/camera.intrinsics[c1, 0],
                       1.0/camera.intrinsics[c1, 0], 1.0])
    k_2_inv = np.diag([1.0/camera.intrinsics[c2, 0],
                       1.0/camera.intrinsics[c2, 0], 1.0])
    return k_2_inv.T @ essential @ k_1_inv


def hs_correct(fundamental, point1, point2):
    """Hartley-Sturm/OpenCV polynomial, in ascending-coefficient convention."""
    x1, y1 = map(float, point1)
    x2, y2 = map(float, point2)
    t1 = np.array([[1, 0, x1], [0, 1, y1], [0, 0, 1.]], dtype=float)
    t2 = np.array([[1, 0, x2], [0, 1, y2], [0, 0, 1.]], dtype=float)
    translated = t2.T @ fundamental @ t1
    u, _, vh = np.linalg.svd(translated)
    e1 = vh[-1].copy()
    e1 /= np.linalg.norm(e1[:2])
    if e1[2] < 0: e1 *= -1
    e2 = u[:, -1].copy()
    e2 /= np.linalg.norm(e2[:2])
    if e2[2] < 0: e2 *= -1
    r1t = np.array([[e1[0], -e1[1], 0],
                    [e1[1],  e1[0], 0], [0, 0, 1.]])
    r2 = np.array([[ e2[0], e2[1], 0],
                   [-e2[1], e2[0], 0], [0, 0, 1.]])
    transformed = r2 @ translated @ r1t
    f1, f2 = e1[2], e2[2]
    a, b, c, d = transformed[1,1], transformed[1,2], transformed[2,1], transformed[2,2]
    coeff = np.array([
        -a*d*d*b+b*b*c*d,
        f2**4*d**4+b**4+2*b*b*f2*f2*d*d-a*a*d*d+b*b*c*c,
        4*a*b**3+4*b*b*f2*f2*c*d+4*f2**4*c*d**3-a*a*d*c+b*c*c*a+
        4*a*b*f2*f2*d*d-2*a*d*d*f1*f1*b+2*b*b*c*f1*f1*d,
        6*a*a*b*b+6*f2**4*c*c*d*d+2*b*b*f2*f2*c*c+2*a*a*f2*f2*d*d-
        2*a*a*d*d*f1*f1+2*b*b*c*c*f1*f1+8*a*b*f2*f2*c*d,
        4*a**3*b+2*b*c*c*f1*f1*a+4*f2**4*c**3*d+4*a*b*f2*f2*c*c+
        4*a*a*f2*f2*c*d-2*a*a*d*f1*f1*c-a*d*d*f1**4*b+b*b*c*f1**4*d,
        f2**4*c**4+2*a*a*f2*f2*c*c-a*a*d*d*f1**4+b*b*c*c*f1**4+a**4,
        b*c*c*f1**4*a-a*a*d*f1**4*c], dtype=float)
    scale = np.max(np.abs(coeff))
    if not np.isfinite(scale) or scale == 0:
        raise RuntimeError("Degenerate Hartley-Sturm polynomial")
    roots = np.roots((coeff/scale)[::-1])
    real_roots = [float(z.real) for z in roots
                  if abs(z.imag) <= 1e-7*max(1.0, abs(z.real))]
    def objective(t):
        q = c*t+d
        den = (a*t+b)**2 + f2*f2*q*q
        return t*t/(1+f1*f1*t*t) + q*q/den
    choices = [(objective(t), t) for t in real_roots if np.isfinite(objective(t))]
    if not choices:
        raise RuntimeError("No finite real Hartley-Sturm root")
    value, t = min(choices)
    den1 = t*t*f1*f1+1
    q1 = t1 @ (r1t @ np.array([t*t*f1/den1, t/den1, 1.]))
    q = c*t+d
    den2 = f2*f2*q*q+(a*t+b)**2
    q2 = t2 @ (r2.T @ np.array([f2*q*q/den2, -(a*t+b)*q/den2, 1.]))
    q1, q2 = q1[:2]/q1[2], q2[:2]/q2[2]
    epi = float(np.r_[q2,1.] @ fundamental @ np.r_[q1,1.])
    direct = float(np.sum((q1-point1)**2)+np.sum((q2-point2)**2))
    return q1, q2, {"real_roots": real_roots, "polynomial_cost": value,
                    "direct_correction_cost": direct, "epipolar_residual": epi}


def triangulate_dlt(camera, cameras, standard_pixels):
    rows = []
    for c, pixel in zip(cameras, standard_pixels):
        focal = camera.intrinsics[c,0]
        projection = np.diag([focal,focal,1.]) @ camera_matrix(camera,c)
        rows.extend([pixel[0]*projection[2]-projection[0],
                     pixel[1]*projection[2]-projection[1]])
    _, _, vh = np.linalg.svd(np.asarray(rows))
    if abs(vh[-1,3]) < 1e-14:
        raise RuntimeError("DLT returned point at infinity")
    return vh[-1,:3]/vh[-1,3]


def midpoint(camera, cameras, bal_normalized):
    matrix = np.zeros((3,3)); rhs = np.zeros(3)
    for c, point in zip(cameras, bal_normalized):
        center = -camera.R[c].T @ camera.t[c]
        direction = camera.R[c].T @ np.r_[-point, 1.]
        direction /= np.linalg.norm(direction)
        projector = np.eye(3)-np.outer(direction,direction)
        matrix += projector; rhs += projector @ center
    return np.linalg.solve(matrix,rhs)


def old_anchor_search(camera, proposed, old_x, cameras, pixels):
    # Choose the most projection-sensitive old observation, as wave 4 did.
    y = np.einsum('nij,j->ni',camera.R[cameras],old_x)+camera.t[cameras]
    _, jy, _ = F.S.chart.project_jacobian(y,camera.intrinsics[cameras])
    anchor = int(np.argmax(np.sum(jy*jy,axis=(1,2))))
    c = int(cameras[anchor])
    center = -camera.R[c].T @ camera.t[c]
    bal, _ = invert_simple_radial(pixels[anchor],camera.intrinsics[c,0],
                                  camera.intrinsics[c,1],
                                  np.linalg.norm(-y[anchor,:2]/y[anchor,2]))
    direction = camera.R[c].T @ np.r_[-bal,1.]
    direction /= np.linalg.norm(direction)
    z0 = float(direction @ (old_x-center))
    old_sign = np.sign(y[:,2]); old_sign[old_sign==0]=1
    def cost_at(z):
        x=center+z*direction
        residual, yy=F.S.residual(proposed,np.broadcast_to(x,(len(cameras),3)),cameras,pixels)
        if not np.all(np.isfinite(residual)) or np.any(yy[:,2]*old_sign<=0): return np.inf
        return float(.5*np.sum(residual*residual,dtype=np.longdouble))
    lo,hi=sorted([1e-4*z0,1e4*z0])
    grid=np.unique(np.r_[np.linspace(lo,hi,65),z0*np.logspace(-4,4,257)])
    a=np.einsum('nij,j->ni',proposed.R[cameras],center)+proposed.t[cameras]
    b=np.einsum('nij,j->ni',proposed.R[cameras],direction)
    poles=-a[:,2]/b[:,2]
    grid=np.sort(np.unique(np.r_[grid,poles[(poles>lo)&(poles<hi)]]))
    best=(np.inf,z0)
    for lower,upper in zip(grid[:-1],grid[1:]):
        width=upper-lower
        lower += width*1e-10; upper -= width*1e-10
        mid=.5*(lower+upper)
        if not np.isfinite(cost_at(mid)): continue
        result=minimize_scalar(cost_at,bounds=(lower,upper),method='bounded',
            options={'xatol':max(1e-14,abs(z0)*1e-13),'maxiter':200})
        for z in (lower,upper,float(result.x)):
            value=cost_at(z)
            if value<best[0]: best=(value,z)
    return center+best[1]*direction,{"anchor":c,"depth":best[1],"cost":best[0]}


def original_polish(proposed, cameras, pixels, starts, old_depth):
    sign=np.sign(old_depth);sign[sign==0]=1
    def residual(x):
        r,_=F.S.residual(proposed,np.broadcast_to(x,(len(cameras),3)),cameras,pixels)
        return r.ravel()
    def jacobian(x):
        y=np.einsum('nij,j->ni',proposed.R[cameras],x)+proposed.t[cameras]
        _,jy,_=F.S.chart.project_jacobian(y,proposed.intrinsics[cameras])
        return np.einsum('nij,njk->nik',jy,proposed.R[cameras]).reshape(-1,3)
    rows=[]
    for label,start in starts:
        try:
            result=least_squares(residual,np.asarray(start),jac=jacobian,method='lm',
                ftol=1e-14,xtol=1e-14,gtol=1e-14,max_nfev=1000)
            x=result.x; r=residual(x); y=np.einsum('nij,j->ni',proposed.R[cameras],x)+proposed.t[cameras]
            valid=bool(np.all(np.isfinite(r)) and np.all(y[:,2]*sign>0))
            rows.append(dict(label=label,point=x.tolist(),cost=float(.5*r@r) if valid else None,
                valid=valid,nfev=result.nfev,status=result.status,optimality=float(result.optimality),
                depth_ratios=(y[:,2]/old_depth).tolist()))
        except Exception as exc:
            rows.append(dict(label=label,valid=False,error=str(exc)))
    return rows


def calculate(root, label, ci, pi, uv):
    folder=root/label
    camera,x,meta=F.load_capture_state(folder); nc=len(camera.R); point=250233
    step=F.read_array(folder/'accepted.step',(9*nc+3*len(x),))
    dc=step[:9*nc].reshape(nc,9); dp=step[9*nc:].reshape(-1,3)
    obs=np.flatnonzero(pi==point); cameras=ci[obs]; pixels=uv[obs]
    assert len(obs)==2
    old=x[point]; proposed=camera.retract(dc)
    old_y=np.einsum('nij,j->ni',camera.R[cameras],old)+camera.t[cameras]
    old_pix,jy,ji=F.S.chart.project_jacobian(old_y,camera.intrinsics[cameras])
    residual=old_pix-pixels
    jp=np.einsum('nij,njk->nik',jy,camera.R[cameras])
    rx=np.einsum('nij,j->ni',camera.R[cameras],old)
    yc=np.einsum('nij,nj->ni',jy,np.cross(dc[cameras,:3],rx)+dc[cameras,3:6])
    yc+=np.einsum('nij,nj->ni',ji,dc[cameras,6:9])
    def track_cost(candidate):
        rr,yy=F.S.residual(proposed,np.broadcast_to(candidate,(len(obs),3)),cameras,pixels)
        return float(.5*np.sum(rr*rr,dtype=np.longdouble)),yy
    def point_pred(delta):
        jd=yc+np.einsum('nri,i->nr',jp,delta)
        return -float(np.sum(residual*jd+.5*jd*jd,dtype=np.longdouble))
    inverse=[]; normalized=[]
    proposed_old_y=np.einsum('nij,j->ni',proposed.R[cameras],old)+proposed.t[cameras]
    for q,c,y in zip(pixels,cameras,proposed_old_y):
        pred=np.linalg.norm(-y[:2]/y[2])
        p,record=invert_simple_radial(q,proposed.intrinsics[c,0],
                                      proposed.intrinsics[c,1],pred)
        normalized.append(p); inverse.append(record)
    normalized=np.asarray(normalized)
    midpoint_x=midpoint(proposed,cameras,normalized)
    # Hartley-Sturm works in standard undistorted pixel coordinates; BAL's
    # normalized coordinate has the opposite sign in x and y.
    standard=np.asarray([-camera.intrinsics[c,0]*p for c,p in zip(cameras,normalized)])
    fundamental=fundamental_pixel(proposed,int(cameras[0]),int(cameras[1]))
    q1,q2,hs=hs_correct(fundamental,standard[0],standard[1])
    hs_x=triangulate_dlt(proposed,cameras,[q1,q2])
    ray_x,ray=old_anchor_search(camera,proposed,old,cameras,pixels)
    recorded_cost,recorded_y=track_cost(old+dp[point])
    starts=[('old',old),('recorded',old+dp[point]),('midpoint',midpoint_x),
            ('hartley_sturm',hs_x),('old_anchor_global_1d',ray_x)]
    raw_candidates=[]
    old_sign=np.sign(old_y[:,2]);old_sign[old_sign==0]=1
    for start_label,start in starts:
        start_cost,start_y=track_cost(start)
        valid=bool(np.isfinite(start_cost) and np.all(start_y[:,2]*old_sign>0))
        margin=bool(np.all(np.abs(start_y[:,2])>=np.abs(recorded_y[:,2])))
        raw_candidates.append(dict(label=start_label,point=np.asarray(start).tolist(),
            cost=start_cost if valid else None,valid=valid,
            projection_margin_passed=margin,
            depth_ratios=(start_y[:,2]/old_y[:,2]).tolist(),
            point_prediction=point_pred(np.asarray(start)-old)))
    polishes=original_polish(proposed,cameras,pixels,starts,old_y[:,2])
    for candidate in polishes:
        if candidate['valid']:
            candidate['projection_margin_passed']=bool(np.all(
                np.abs(np.asarray(candidate['depth_ratios'])) >=
                np.abs(recorded_y[:,2]/old_y[:,2])))
        else:
            candidate['projection_margin_passed']=False
    eligible=[]
    for kind,rows in [('raw',raw_candidates),('polished',polishes)]:
        for candidate in rows:
            if candidate['valid'] and candidate['projection_margin_passed']:
                eligible.append((candidate['cost'],kind,candidate))
    if not eligible: raise RuntimeError('No candidate passed depth signs and projection margin')
    _,selected_kind,best=min(eligible,key=lambda item:item[0])
    repaired=np.asarray(best['point']);repaired_cost,new_y=track_cost(repaired)
    attribution=json.loads((W4/'attribution'/('final-e4-'+label.replace('/','-')+'.json')).read_text())
    full_prediction=attribution['prediction']-point_pred(dp[point])+point_pred(repaired-old)
    full_decrease=attribution['true_decrease']+recorded_cost-repaired_cost
    return dict(label=label,point=point,observations=obs.tolist(),cameras=cameras.tolist(),
        recorded_point_cost=recorded_cost,repaired_point_cost=repaired_cost,
        repaired_point=repaired.tolist(),recorded_point=(old+dp[point]).tolist(),
        full_prediction=full_prediction,full_true_decrease=full_decrease,
        full_rho=full_decrease/full_prediction if full_prediction>0 else None,
        depth_signs_preserved=bool(np.all(new_y[:,2]*old_y[:,2]>0)),
        repaired_depth_ratios=(new_y[:,2]/old_y[:,2]).tolist(),
        radial_inverse=inverse,hartley_sturm=hs,old_anchor_search=ray,
        raw_candidates=raw_candidates,selected_kind=selected_kind,
        selected_candidate=best,all_polishes=polishes,
        source_hashes={q.name:F.sha(q) for q in folder.iterdir() if q.is_file()},
        scope='Fixed recorded camera proposal; only point 250233 substituted and full quadratic prediction recomputed')


def main():
    F.verify_baseline()
    protocol=P/'A1_REPLAY_PROTOCOL.md'
    ci,pi,uv,_=F.CHART.load_observations(Path('/workspace/bal/final-3068.txt'))
    record=json.loads((W3/'miss-forensics/decision.json').read_text())
    archive=Path(record['archive']); assert F.sha(archive)==record['sha256']
    wanted={'hit/6','miss/6'}
    with tempfile.TemporaryDirectory(prefix='wave5-a1-',dir='/dev/shm') as temporary:
        root=Path(temporary)
        for name,raw in F.FA.decoded(archive):
            if str(Path(name).parent) in wanted:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        rows=[calculate(root,label,ci,pi,uv) for label in sorted(wanted)]
    old_gap=abs(rows[1]['recorded_point_cost']-rows[0]['recorded_point_cost'])
    new_gap=abs(rows[1]['repaired_point_cost']-rows[0]['repaired_point_cost'])
    passed=(new_gap<=.1*old_gap and all(r['depth_signs_preserved'] and
            r['full_prediction']>0 and r['full_rho'] is not None and r['full_rho']>.1
            for r in rows))
    result=dict(rows=rows,recorded_point_gap=old_gap,repaired_point_gap=new_gap,
        fraction_remaining=new_gap/old_gap,replay_gate_passed=passed,
        protocol_sha256=sha(protocol),code_sha256=sha(__file__),
        decision=('Proceed to detector-locality and native targeted repair' if passed else
                  'Kill the registered targeted repair before native rollout'))
    write(P/'a1-replay.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
