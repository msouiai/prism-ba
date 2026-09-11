#!/usr/bin/env python3
"""Check that the precision variants differ by casting, not linearization."""
import fcntl,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent
def main():
    rows=[]
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        for f in sorted((P/'evidence').glob('capture-*')):
            r={'capture':f.name}
            for kind in ['W','B']:
                a=np.fromfile(f/(kind+'32.f32'),'<f4');b=np.fromfile(f/(kind+'64.f64'),'<f8')
                assert len(a)==len(b)
                r[kind+'_entries']=len(a)
                r[kind+'_cast_mismatches']=int(np.count_nonzero(a!=b.astype('<f4')))
                assert r[kind+'_cast_mismatches']==0
            rows.append(r)
    (P/'rounding_identity.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps(rows))
if __name__=='__main__':main()
