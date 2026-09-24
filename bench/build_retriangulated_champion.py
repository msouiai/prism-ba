"""Build the current coupled-radius champion with the upstream OCA_RETRI pass."""
from pathlib import Path
import hashlib, json, shutil, subprocess

champ = Path('/tmp/prism-controller-attribution/build/source.cu')
upstream = Path('/tmp/prism-retriangulation/gpu/oca_cuda.cu')
root = Path('/tmp/prism-retriangulated-champion')
out = root / 'build'
if root.exists():
    raise SystemExit('refusing existing build; choose a fresh temporary root')
out.mkdir(parents=True)
s = champ.read_text()
u = upstream.read_text()
ks = u.index('__global__ void KernelRetriangulate')
ke = u.index('\n// H_gn must', ks)
kernel = u[ks:ke]
if 'KernelRetriangulate' in s:
    raise SystemExit('champion already contains retriangulation')
pos = s.index('__global__ void', s.index('struct DeviceState {'))
s = s[:pos] + kernel + '\n\n' + s[pos:]
ss = u.index('    // OCA_RETRI=<k>:')
se = u.index('    // OCA_RI_AT=<k>:', ss)
schedule = u[ss:se]
needle = '    ++k;   // AUDIT 2026-08-22: advanced here, not in the for-header, so an\n'
if s.count(needle) != 1:
    raise SystemExit(f'expected one iteration marker, found {s.count(needle)}')
s = s.replace(needle, needle + schedule, 1)
(out / 'source.cu').write_text(s)
shutil.copytree(Path('/tmp/prism-controller-attribution/build/headers'), out / 'headers')
cmd = ['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',
       '-I'+str(out/'headers'),str(out/'source.cu'),'-o',str(out/'prism-tr'),
       '-lcublas','-lcusolver']
with (out/'build.log').open('w') as f:
    subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, check=True)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
(out/'manifest.json').write_text(json.dumps({
    'command':cmd,'source_sha256':sha(out/'source.cu'),
    'binary_sha256':sha(out/'prism-tr'),
    'champion_source_sha256':sha(champ),'upstream_source_sha256':sha(upstream),
    'scope':'Current coupled-radius champion plus upstream OCA_RETRI kernel and accepted-outer scheduler. Production unchanged.'}, indent=2))
print(json.dumps(json.loads((out/'manifest.json').read_text()), indent=2))
