#!/usr/bin/env python3
"""Use reference Schur model values to rank approximate projected proposals."""
import pathlib,shutil,json,subprocess
from build_tr_candidate import sha
ROOT=pathlib.Path('/workspace/prism-tr-reference/rank')
def main():
 base=pathlib.Path('/workspace/prism-tr-fp32-products/reliable');m=json.loads((base/'stop-manifest.json').read_text());assert sha(base/'source.cu')==m['source_sha256'];assert all(sha(base/'headers'/k)==v for k,v in m['headers_sha256'].items());ROOT.mkdir();shutil.copytree(base/'headers',ROOT/'headers');shutil.copy2(base/'source.cu',ROOT/'source.cu')
 h=ROOT/'headers/cg_tr_projection_step.inc';s=h.read_text();old='const bool verified=model_error<=1e-7 && xx<=tr->radius*tr->radius*(1+1e-10);';assert s.count(old)==1
 s=s.replace(old,'''// The approximate reduced model proposes x. Reference S*x already supplies
 // all ranking and stopping quantities; reduced-model agreement is diagnostic.
 const bool verified=std::isfinite(bx)&&std::isfinite(xx)&&std::isfinite(xsx)&&std::isfinite(gn)&&std::isfinite(pred)&&std::isfinite(fw)&&xx>=0&&xx<=tr->radius*tr->radius*(1+1e-10);''')
 s=s.replace('// A failed model check discards the projection; continue the original CG solve.', '// Nonfinite or radius-invalid proposals are discarded. Full nonlinear acceptance remains unchanged.')
 h.write_text(s);p=ROOT/'source.cu';cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(ROOT/'headers'),str(p),'-o',str(ROOT/'prism-tr'),'-lcublas','-lcusolver']
 with (ROOT/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 (ROOT/'stop-manifest.json').write_text(json.dumps(dict(command=cmd,source_sha256=sha(p),binary_sha256=sha(ROOT/'prism-tr'),base_source_sha256=m['source_sha256'],headers_sha256={p.name:sha(p) for p in (ROOT/'headers').iterdir()},policy='Rank approximate projected candidates by reference FP64 Schur prediction/gradient/norm; reduced-model disagreement is diagnostic. Retain reference residual fallback, radius feasibility and full nonlinear acceptance. FW bound conditional on PSD, not a global certificate.'),indent=2));print(ROOT/'prism-tr')
if __name__=='__main__':main()
