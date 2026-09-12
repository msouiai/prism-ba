"""Export-only derivative of the completed, frozen witness executable source."""
from pathlib import Path
import hashlib,json,os,subprocess
P=Path(__file__).resolve().parent;F=P.parent/'eta2_champion';b=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
prior=json.loads((P/'witness_build_manifest.json').read_text())
source=b/'prism_wave_witness.cu';assert sha(source)==prior['source_sha256'];s=source.read_text()
anchor='          bool fallback=triggered&&(norm>radius||norm<.5*radius||!result.certified);'
assert s.count(anchor)==1
s=s.replace(anchor,anchor+'''
          if(repeat==0){
            WaveSave(dest+(mode==0?"/coupled_raw.step":"/frozen_raw.step"),ref.Compose(blas,-1),n);
            WaveSave(dest+(mode==0?"/coupled.step":"/frozen.step"),ref.Compose(blas,radius),n);
          }
''')
src=b/'prism_root_validation.cu';src.write_text(s)
cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(P),'-I'+str(F/'source/headers'),str(src),'-o',str(b/'prism-root-validation'),'-lcublas','-lcusolver']
env=os.environ.copy();env['TMPDIR']='/dev/shm'
with (b/'root-validation-build.log').open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
ans=dict(command=cmd,source_sha256=sha(src),binary_sha256=sha(b/'prism-root-validation'),
         parent_witness_manifest=prior,change='export-only; no candidate or root logic change')
(P/'root_validation_manifest.json').write_text(json.dumps(ans,indent=2)+'\n');print('BUILT VALIDATION',flush=True)
