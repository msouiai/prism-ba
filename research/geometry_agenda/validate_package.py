"""Check algebra, immutable candidates, frozen sources and evidence integrity."""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'; os.environ['OMP_NUM_THREADS'] = '1'
import datetime
import hashlib
import json
import pathlib
import py_compile
import subprocess
import sys
import tarfile

ROOT = pathlib.Path(__file__).resolve().parent; REPO = ROOT.parent.parent
checks = ['check_geometry.py', 'check_reference.py', 'check_curvature.py', 'check_points.py',
          'check_collective.py', 'check_robust.py', 'check_smoothing.py', 'check_spectral.py', 'check_allocation.py']
records = []
for script in checks:
    result = subprocess.run([sys.executable, str(ROOT/script)], text=True, capture_output=True)
    records.append({'script': script, 'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
    print(script, result.returncode, flush=True)
    assert result.returncode == 0, result.stderr
result = subprocess.run([sys.executable, str(ROOT.parent/'eta2_champion/build.py'), '--check-only'], text=True, capture_output=True)
assert result.returncode == 0, result.stderr
records.append({'script': 'eta2_champion/build.py --check-only', 'returncode': result.returncode, 'stdout': result.stdout})
for p in ROOT.glob('*.py'): py_compile.compile(str(p), doraise=True)
def reject_constant(v): raise ValueError('non-finite JSON constant: '+v)
files = list(ROOT.glob('*.json'))+list((ROOT/'evidence').glob('*.json'))
for p in files:
    try: json.loads(p.read_text(), parse_constant=reject_constant)
    except ValueError as error: raise ValueError(f'{p.name}: {error}') from error
archives = []
for record in json.loads((ROOT/'evidence/manifest.json').read_text()):
    path = ROOT/'evidence'/record['archive']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']
    members = {r['path']: r for r in record['files']}; count = 0
    with tarfile.open(path, 'r|xz') as archive:
        for m in archive:
            if not m.isfile(): continue
            data = archive.extractfile(m).read(); expected = members[m.name]
            assert len(data) == expected['bytes'] and hashlib.sha256(data).hexdigest() == expected['sha256']
            count += 1
    assert count == len(members)
    archives.append({'archive': path.name, 'verified_members': count, 'sha256': record['sha256']})
report = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'checks': records,
          'compiled_scripts': len(list(ROOT.glob('*.py'))), 'strict_json_files': len(files),
          'archives': archives, 'passed': True}
(ROOT/'validation.json').write_text(json.dumps(report, indent=2)+'\n')
print('All checks passed; frozen sources and archive members verified.')
