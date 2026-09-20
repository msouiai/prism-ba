#!/usr/bin/env python3
"""Content-addressed, bit-preserving CPU audit input cache (outside solve timers)."""
import json,pathlib
import numpy as np
from audit_prism_state import observations
from profile_iterations import sha,score_initial

def load_input(data,cache_dir=None):
 data=pathlib.Path(data);digest=sha(data)
 if cache_dir is None:return digest,observations(data),score_initial(data)
 root=pathlib.Path(cache_dir)/digest;root.mkdir(parents=True,exist_ok=True);meta=root/'meta.json';array=root/'observations.npy'
 if not meta.exists():
  dims,obs=observations(data);initial=score_initial(data)
  tmp=root/'observations.tmp.npy';np.save(tmp,obs,allow_pickle=False);tmp.replace(array)
  loaded=np.load(array,mmap_mode='r',allow_pickle=False)
  assert loaded.shape==obs.shape and loaded.dtype==obs.dtype and np.array_equal(loaded,obs)
  m=dict(data_sha256=digest,dims=dims,initial=initial,array_sha256=sha(array),observations_source_sha256=sha(pathlib.Path(__file__).with_name('audit_prism_state.py')),initial_source_sha256=sha(pathlib.Path(__file__).with_name('profile_iterations.py')))
  temp=root/'meta.tmp.json';temp.write_text(json.dumps(m,indent=2)+'\n');temp.replace(meta)
 else:m=json.loads(meta.read_text())
 assert m['data_sha256']==digest
 assert m['observations_source_sha256']==sha(pathlib.Path(__file__).with_name('audit_prism_state.py'))
 assert m['initial_source_sha256']==sha(pathlib.Path(__file__).with_name('profile_iterations.py'))
 assert m['array_sha256']==sha(array)
 obs=np.load(array,mmap_mode='r',allow_pickle=False);dims=tuple(m['dims'])
 assert obs.dtype==np.float64 and obs.shape==(dims[2],4)
 return digest,(dims,obs),m['initial']
