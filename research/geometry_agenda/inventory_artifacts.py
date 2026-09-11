import datetime
import hashlib
import json
import pathlib
import platform
import subprocess
import sys
ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'build/python'))
import numpy
import scipy
import matplotlib

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

rows = []
for path in sorted(ROOT.rglob('*')):
    rel = path.relative_to(ROOT)
    if not path.is_file() or any(p in ['build', '__pycache__'] for p in rel.parts) or path.name == 'artifact_manifest.json': continue
    rows.append({'path': str(rel), 'bytes': path.stat().st_size, 'sha256': digest(path)})
result = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'code_results_parent_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'branch': 'research/geometry-agenda',
          'python': sys.version, 'numpy': numpy.__version__, 'scipy': scipy.__version__, 'matplotlib': matplotlib.__version__,
          'platform': platform.platform(),
          'cpu_model': next(x.split(':', 1)[1].strip() for x in pathlib.Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name')),
          'gpu': subprocess.check_output(['nvidia-smi', '--query-gpu=name,driver_version,memory.total', '--format=csv,noheader'], text=True).strip(),
          'cpu_experiment_threads': {'OPENBLAS_NUM_THREADS': 1, 'OMP_NUM_THREADS': 1}, 'precision': 'FP64',
          'files': rows, 'total_bytes': sum(r['bytes'] for r in rows)}
(ROOT/'artifact_manifest.json').write_text(json.dumps(result, indent=2)+'\n')
print('Inventoried', len(rows), 'files;', result['total_bytes'], 'bytes')
