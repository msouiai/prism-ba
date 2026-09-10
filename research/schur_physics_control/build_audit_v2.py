#!/usr/bin/env python3
"""Instrument the delivered v2 source in a separate copy; never edit its package."""
import pathlib,hashlib,json,subprocess,shutil
from audit_patch import patch_gradient
from v2_source import locate
ROOT=pathlib.Path(__file__).resolve().parent
VENDOR,vendor_manifest=locate()
OUT=ROOT/'build/v2';OUT.mkdir(exist_ok=True,parents=True)
src=VENDOR/'oca_cuda_v2.cu'
binary=VENDOR/'oca_cuda_v2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
s=patch_gradient(src.read_text())
unit=OUT/'audit_v2.cu';unit.write_text(s)
shutil.copy2(ROOT/'gradient_audit.cuh',OUT/'gradient_audit.cuh')
cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I'+str(VENDOR),str(unit),'-o',str(OUT/'audit-v2'),'-lcublas','-lcusolver']
print('Building v2 gradient audit',flush=True)
with (OUT/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
(OUT/'manifest.json').write_text(json.dumps({'command':cmd,'original_source_sha256':sha(src),'original_binary_sha256':vendor_manifest['delivered_binary_sha256'],'delivered_binary_present':binary.exists(),'source_sha256':sha(unit),'binary_sha256':sha(OUT/'audit-v2'),'header_sha256':sha(OUT/'gradient_audit.cuh'),'vendor_headers':{p.name:sha(p) for p in VENDOR.iterdir() if p.suffix in ['.h','.cuh']}},indent=2)+'\n')
print(OUT/'audit-v2',flush=True)
