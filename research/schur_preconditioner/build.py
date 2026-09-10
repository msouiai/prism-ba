#!/usr/bin/env python3
"""Isolated fixed-state probe; frozen solver input source is checksum verified."""
import pathlib,hashlib,json,subprocess
ROOT=pathlib.Path(__file__).resolve().parent
pkg=ROOT.parent/'eta2_champion'
out=ROOT/'build';out.mkdir(exist_ok=True)
s=(pkg/'source/prism_eta2.cu').read_text()
assert hashlib.sha256(s.encode()).hexdigest()=='22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8'
manifest=json.loads((pkg/"source_manifest.json").read_text())
assert all(hashlib.sha256((pkg/"source/headers"/name).read_bytes()).hexdigest()==h for name,h in manifest["headers_sha256"].items()), "Frozen header changed"
parts=[]
for start,end in [('__device__ __forceinline__ void MFVinv(', '// GAP-4090 F2'),('__global__ void MFVinvApply(', '// Map camera traversal'),('template <int CD, class HT>\n__global__ void MFPass2(', '__global__ void MFBackSub'),('template <int CD, typename HT>\n__global__ void MFBlockSchur(', '#include "pcg_camera.cuh"')]:
    a=s.index(start);b=s.index(end,a);parts.append(s[a:b])
(out/'reference.cuh').write_text('\n'.join(parts))
old='if(camera_tr && getenv("OCA_CG_CAPTURE") && k=='
assert s.count(old)==1
s=s.replace(old,'if(getenv("OCA_CG_CAPTURE") && k==')
s=s.replace('std::string dir=getenv("OCA_CG_CAPTURE");','if(!classical_lm || CD!=9 || compact_mode!=2 || L!=1)throw std::runtime_error("fixed capture requires frozen classical eta2 layout");\n      std::string dir=getenv("OCA_CG_CAPTURE");')
s=s.replace('(double)shifts[0],tr->radius,(double)eta);fclose(f);','(double)shifts[0],0.0,(double)eta);fclose(f);\n      std::printf("FIXED_CAPTURE outer=%d cost=%.17g tau=%.17g lambda=%.17g eta=%.17g\\n",k,(double)cost,(double)tau_eff,(double)shifts[0],(double)eta);std::fflush(stdout);std::exit(0);')
assert 'FIXED_CAPTURE outer' in s
(out/'capture.cu').write_text(s)
commands=[['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(pkg/'source/headers'),str(out/'capture.cu'),'-o',str(out/'capture'),'-lcublas','-lcusolver'],['nvcc','-O3','-std=c++17','-arch=sm_89','-I'+str(out),str(ROOT/'fixed.cu'),'-o',str(out/'fixed'),'-lcublas']]
for i,cmd in enumerate(commands):
    print('Building',cmd[-3:],flush=True)
    with (out/f'build-{i}.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
(out/'manifest.json').write_text(json.dumps({'commands':commands,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}},indent=2))
