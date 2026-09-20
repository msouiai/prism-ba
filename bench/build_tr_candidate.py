#!/usr/bin/env python3
"""Self-contained opt-in TR candidate build from the repository solver + patch."""
import argparse,pathlib,hashlib,subprocess,shutil,json
REPO=pathlib.Path(__file__).resolve().parents[1]
BASE_SHA='0b7aac9b70523ce08d791e1a75c6c18a672cdfb29f28c6a3ab21c0bf5e786569'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path,default=pathlib.Path('/workspace/prism-tr-candidate'));ap.add_argument('--arch',default='sm_89');ap.add_argument('--source-only',action='store_true');args=ap.parse_args()
 base=REPO/'gpu/oca_cuda.cu';patch=REPO/'gpu/tr_candidate.patch';assert sha(base)==BASE_SHA,'Base solver changed: review patch before rebuilding'
 out=args.output;out.mkdir(parents=True,exist_ok=True);source=out/'source.cu';shutil.copy2(base,source)
 subprocess.run(['patch','--batch','--forward','--silent',str(source),str(patch)],check=True)
 headers=out/'headers';headers.mkdir(exist_ok=True)
 for pattern in ['*.h','*.cuh','*.inc']:
  for p in (REPO/'gpu').glob(pattern):shutil.copy2(p,headers/p.name)
 cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch='+args.arch,'-I'+str(headers),str(source),'-o',str(out/'prism-tr'),'-lcublas','-lcusolver']
 manifest=dict(base_sha256=sha(base),patch_sha256=sha(patch),source_sha256=sha(source),headers_sha256={p.name:sha(p) for p in headers.iterdir()},command=cmd)
 if not args.source_only:
  with (out/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
  manifest['binary_sha256']=sha(out/'prism-tr')
 (out/'build-manifest.json').write_text(json.dumps(manifest,indent=2));print(out/'prism-tr' if not args.source_only else source)
if __name__=='__main__':main()
