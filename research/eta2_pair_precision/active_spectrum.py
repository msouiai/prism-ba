#!/usr/bin/env python3
"""Supplement: exclude the 52 frozen k2 coordinates from spectral summaries.

The registered full 468x468 eigenvalues remain unchanged. Their minimum may
be the trivial lambda eigenvalue of a zero-Jacobian k2 coordinate. This
post-processing exposes the active 416-dimensional spectrum, using only
the already validated dense matrices. It makes no optimizer measurements.
"""
import fcntl,json,os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent
def main():
    rows=[]
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        for f in sorted((P/'evidence/external').glob('*/dense_operators.npz')):
            a=np.load(f);active=np.arange(468)%9!=8
            spectra={};vectors={};matrices={}
            for name in ['stored','W64_Rstored','W64_R64qr']:
                A=a[name][np.ix_(active,active)];vals,vec=np.linalg.eigh(A)
                matrices[name]=A;vectors[name]=vec[:,0]
                spectra[name]=dict(min_eigenvalue=float(vals[0]),negative=int((vals<0).sum()),
                  below_cutoff=int((vals<=1e-14).sum()))
            v=vectors['stored']
            cross={name:float(v@A@v) for name,A in matrices.items()}
            row=dict(state=f.parent.name,active_dimensions=416,operators=spectra,mixed_min_direction_rayleigh=cross)
            rows.append(row)
            np.savez_compressed(f.parent/'active_min_vectors.npz',active_indices=np.flatnonzero(active),**vectors)
            print(row['state'],{k:v['min_eigenvalue'] for k,v in spectra.items()},flush=True)
    (P/'active-spectrum.json').write_text(json.dumps(rows,indent=2)+'\n')
if __name__=='__main__':main()
