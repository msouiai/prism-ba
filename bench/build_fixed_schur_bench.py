#!/usr/bin/env python3
import pathlib,subprocess,json,shutil,argparse
from build_tr_candidate import sha
ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path,default=pathlib.Path('/workspace/prism-tr-reference/fixed'));a=ap.parse_args();root=a.output;root.mkdir();base=pathlib.Path('/workspace/prism-tr-cg-stop/guarded/source.cu');s=base.read_text()
parts=[]
for start,end in [('__device__ __forceinline__ void MFVinv(', '// GAP-4090 F2'),('__global__ void MFVinvApply(', '// Map camera traversal'),('template <int CD, class HT>\n__global__ void MFPass2(', '__global__ void MFBackSub')]:
 a=s.index(start);b=s.index(end,a);parts.append(s[a:b])
(root/'reference_kernels.cuh').write_text('\n'.join(parts));repo=pathlib.Path(__file__).resolve().parents[1];shutil.copy2(repo/'gpu/point_owned_schur.cuh',root/'point_owned_schur.cuh');shutil.copy2(repo/'bench/fixed_schur_bench.cu',root/'bench.cu')
cmd=['/usr/local/cuda/bin/nvcc','-O3','-std=c++17','-arch=sm_89',str(root/'bench.cu'),'-o',str(root/'bench'),'-lcublas'];subprocess.run(cmd,check=True)
(root/'manifest.json').write_text(json.dumps(dict(command=cmd,base_source_sha256=sha(base),files={p.name:sha(p) for p in root.iterdir() if p.is_file()}),indent=2))
