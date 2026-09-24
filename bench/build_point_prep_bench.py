import pathlib,shutil,subprocess,json,argparse
from build_tr_candidate import sha
ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path,default=pathlib.Path('/workspace/prism-tr-point-prep/fixed-v2'));a=ap.parse_args();root=a.output;root.mkdir();repo=pathlib.Path(__file__).resolve().parents[1];s=pathlib.Path('/workspace/prism-tr-safeguard/factored/source.cu').read_text();parts=[]
for start,end in [('__device__ __forceinline__ void MFGivens(', '// PER-POINT DAMPING'),('__global__ void MFPointFactorTau(', 'template <int CD, class HT>\n__global__ void MFPass1('),('template <int CD, class HT>\n__global__ void MFRhsPrime(', 'template <int CD>\n__global__ void MFDiagHcc')]:
 a=s.index(start);b=s.index(end,a);parts.append(s[a:b])
(root/'reference.cuh').write_text('\n'.join(parts))
for file in ['gpu/point_prep_candidate.cuh','bench/point_prep_bench.cu']:shutil.copy2(repo/file,root/pathlib.Path(file).name)
cmd=['nvcc','-O3','-std=c++17','-arch=sm_89',str(root/'point_prep_bench.cu'),'-o',str(root/'bench')];subprocess.run(cmd,check=True);(root/'manifest.json').write_text(json.dumps(dict(command=cmd,files={p.name:sha(p) for p in root.iterdir() if p.is_file()}),indent=2))
