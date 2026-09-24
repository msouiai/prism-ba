#!/usr/bin/env python3
"""Extended-precision diagnostics for excluded endpoints; never requalifies runs."""
import gzip
import json
import pathlib
import struct

import numpy as np
from audit_prism_state import observations

ROOT=pathlib.Path('/workspace/prism-schur-recovery')

def main():
    output=[]
    for rp in sorted(ROOT.glob('*/*.result.json')):
        row=json.loads(rp.read_text())
        if row['valid'] or 'audit_error' not in row:continue
        dims,obs=observations(pathlib.Path('/workspace/bal')/(row['scene']+'.txt'))
        with gzip.open(row['artifact']+'.state.gz','rb') as f:raw=f.read()
        assert raw[:8]==b'PRISMS01' and struct.unpack('<QQQ',raw[8:32])==dims
        nc,np_,no=dims
        v=np.frombuffer(raw,dtype='<f8',offset=32).astype(np.longdouble)
        R=v[:9*nc].reshape(nc,3,3);t=v[9*nc:12*nc].reshape(nc,3)
        X=v[12*nc:12*nc+3*np_].reshape(np_,3);intr=v[12*nc+3*np_:].reshape(3,nc)
        total=np.longdouble(0);smallest=np.longdouble(np.inf)
        for start in range(0,no,100000):
            o=obs[start:start+100000];ci=o[:,0].astype(np.int64);pi=o[:,1].astype(np.int64)
            q=np.sum(R[ci]*X[pi,None,:],axis=2)+t[ci]
            smallest=min(smallest,np.min(np.abs(q[:,2])))
            uv=-q[:,:2]/q[:,2,None];r2=np.sum(uv*uv,axis=1)
            res=uv*(intr[0,ci]*(1+intr[1,ci]*r2))[:,None]-o[:,2:4].astype(np.longdouble)
            total+=np.sum(res*res,dtype=np.longdouble)*.5
        output.append(dict(artifact=row['artifact'],reported=row['reported'],cpu_fp64=row['cost'],
            cpu_extended=float(total),extended_decimal_precision=np.finfo(np.longdouble).precision,
            smallest_abs_depth=float(smallest),qualification='Remains excluded under the original consistency rule; diagnostic only.'))
    (ROOT/'audit-discrepancies.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output,indent=2))

if __name__=='__main__':main()
