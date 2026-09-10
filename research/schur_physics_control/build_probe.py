#!/usr/bin/env python3
"""Build separate probe binaries; preserve the binaries measured in earlier gates."""
import pathlib,hashlib,json,shutil,subprocess,argparse
from probe_patch import patch_probe
ROOT=pathlib.Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--arm',choices=['eta2','v2'],required=True);ap.add_argument('--extended',action='store_true')
args=ap.parse_args();arm=args.arm
OUT=ROOT/'build'/('probe-'+arm+('-extended' if args.extended else ''));OUT.mkdir(exist_ok=True,parents=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
if arm=='eta2':
    pkg=ROOT.parent/'eta2_champion'
    manifest=json.loads((pkg/'source_manifest.json').read_text())
    source=pkg/'source/prism_eta2.cu';headers=pkg/'source/headers'
    assert sha(source)==manifest['source_sha256']
    assert all(sha(headers/name)==h for name,h in manifest['headers_sha256'].items())
else:
    from v2_source import locate
    headers,_=locate();source=headers/'oca_cuda_v2.cu'
unit=OUT/'probe.cu';unit.write_text(patch_probe(source.read_text(),args.extended))
for name in ['gradient_audit.cuh','relaxation.cuh']:shutil.copy2(ROOT/name,OUT/name)
cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(headers),str(unit),'-o',str(OUT/'probe'),'-lcublas','-lcusolver']
print('Building terminal probe',arm,flush=True)
with (OUT/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
(OUT/'manifest.json').write_text(json.dumps({'command':cmd,'original_source_sha256':sha(source),'source_sha256':sha(unit),'binary_sha256':sha(OUT/'probe'),'headers':{p.name:sha(p) for p in headers.iterdir() if p.suffix in ['.h','.cuh']},'probe_headers':{name:sha(OUT/name) for name in ['gradient_audit.cuh','relaxation.cuh']}},indent=2)+'\n')
print(OUT/'probe',flush=True)
