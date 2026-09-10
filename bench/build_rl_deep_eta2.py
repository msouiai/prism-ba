"""Allow fixed eta in replay, fingerprint it; preserve all numerical code."""
import json,pathlib,shutil,subprocess
from rl_damping_pilot import sha
ROOT=pathlib.Path('/tmp/prism-rl-deep-eta2/build')
BASE=pathlib.Path('/tmp/prism-rl-actor/build')
m=json.loads((BASE/'manifest.json').read_text())
assert sha(BASE/'source.cu')==m['source_sha256']
assert all(sha(BASE/'headers'/k)==v for k,v in m['headers_sha256'].items())
ROOT.mkdir(parents=True,exist_ok=False);shutil.copytree(BASE/'headers',ROOT/'headers')
s=(BASE/'source.cu').read_text()
old='"OCA_TR_RECURRENCE","OCA_BACKTRACK_REARM"};'
assert s.count(old)==1
s=s.replace(old,'"OCA_TR_RECURRENCE","OCA_BACKTRACK_REARM","OCA_RLA_FIXED_ETA"};')
(ROOT/'source.cu').write_text(s)
cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',
     '-I'+str(ROOT/'headers'),str(ROOT/'source.cu'),'-o',str(ROOT/'prism-tr'),'-lcublas','-lcusolver']
with (ROOT/'build.log').open('x') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
(ROOT/'manifest.json').write_text(json.dumps(dict(command=cmd,parent=m,
 source_sha256=sha(ROOT/'source.cu'),binary_sha256=sha(ROOT/'prism-tr'),
 headers_sha256={p.name:sha(p) for p in (ROOT/'headers').iterdir() if p.is_file()}),indent=2)+'\n')
print(ROOT/'prism-tr',flush=True)
