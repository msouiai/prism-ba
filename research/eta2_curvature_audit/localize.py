#!/usr/bin/env python3
"""Post-hoc geometric description of the largest measured rounding terms."""
import fcntl,json,os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent
def main():
    rows=[]
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        for folder in sorted((P/'evidence').glob('capture-*')):
            a=json.loads((folder/'audit.json').read_text());m=a['metadata'];nc=int(m['ncam']);np_=int(m['npt']);no=int(m['nobs'])
            op=np.fromfile(folder/'obs_points.i32','<i4');oc=np.fromfile(folder/'obs_cams.i32','<i4')
            B=np.fromfile(folder/'B64.f64','<f8').reshape(no,2,3)
            R=np.fromfile(folder/'R_state.f64','<f8').reshape(nc,3,3)
            t=np.fromfile(folder/'t_state.f64','<f8').reshape(nc,3)
            X=np.fromfile(folder/'X_state.f64','<f8').reshape(np_,3)
            rf=np.fromfile(folder/'R_stored.f64','<f8').reshape(np_,6)
            info=[]
            for item in a['cross_rounding_perturbation']['worst_points'][:2]:
                point=item['point'];ix=np.flatnonzero(op==point);cams=oc[ix]
                centers=-np.einsum('oji,oj->oi',R[cams],t[cams])
                rays=X[point]-centers;norms=np.linalg.norm(rays,axis=1);unit=rays/norms[:,None]
                angle=np.degrees(np.arctan2(np.linalg.norm(np.cross(unit[0],unit[1])),np.dot(unit[0],unit[1])))
                q=rf[point];factor=np.array([[q[0],q[1],q[2]],[0,q[3],q[4]],[0,0,q[5]]])
                sv=np.linalg.svd(B[ix].reshape(-1,3),compute_uv=False)
                sr=np.linalg.svd(factor,compute_uv=False)
                info.append(dict(item,cameras=cams.tolist(),same_camera=bool(cams[0]==cams[1]),
                    baseline=float(np.linalg.norm(centers[1]-centers[0])),ray_angle_degrees=float(angle),
                    distances=norms.tolist(),point_jacobian_singular_values=sv.tolist(),
                    damped_point_normal_condition=float((sr[0]/sr[-1])**2)))
            delta=a['cross_rounding_perturbation']['total'];top=sum(x['error'] for x in info)
            rows.append(dict(capture=folder.name,posthoc=True,points=info,
                             fraction_of_signed_error=top/delta,
                             predicted_same_vector_quotient_if_only_these_cross_blocks_were_fp64=a['cpu_schur_quotients']['stored']-top))
    (P/'localization.json').write_text(json.dumps(rows,indent=2)+'\n')
    for r in rows:print(json.dumps(r),flush=True)
if __name__=='__main__':main()
