import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import datetime
import hashlib
import json
import pathlib
import platform
import py_compile
import subprocess
import sys
import numpy as np
from paths import ROOT, GEOMETRY
from geometry import State
from reference_ba import valid_cost
import scipy
import matplotlib

sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
def reject(v): raise ValueError('nonfinite JSON: '+v)
for file in ROOT.glob('*.json'): json.loads(file.read_text(),parse_constant=reject)
for file in ROOT.glob('*.py'): py_compile.compile(str(file),doraise=True)
cases=json.loads((ROOT/'frozen_cases.json').read_text())['cases']; indexed={(c['scene'],c['seed']):c for c in cases}
for c in cases:
    assert sha(ROOT/c['path'])==c['packed_sha256']
    a=np.load(ROOT/c['path']);s=State(*[a[k] for k in ['R','t','X','intr']]);obs=a['observations']
    assert len(s.R)==c['original_dimensions'][0]
    assert len(np.unique(obs[:,0]))==len(s.R)
    assert abs(valid_cost(s,obs)-c['initial_cost']) <= 1e-12*max(1.,c['initial_cost'])
results=json.loads((ROOT/'results.json').read_text())['rows'];assert len(results)==135
assert len(set((r['scene'],r['seed'],r['rep'],r['arm']) for r in results))==135
for r in results:
    assert r['target']==indexed[(r['scene'],r['seed'])]['target']
    assert r['hit'] and r['cost']<=r['target'] and r['invalid_final_depths']==0
    if r['arm']=='bridge8':
        assert not r['coarse']['verification_fallback'] and r['coarse']['full_cost_relative_disagreement']<1e-10
        other=next(x for x in results if x['scene']==r['scene'] and x['seed']==r['seed'] and x['rep']==r['rep'] and x['arm']=='nonlinear8')
        assert abs(r['cost']-other['cost'])/max(1.,other['cost']) < 1e-8
checks=json.loads((ROOT/'bridge_checks.json').read_text());assert checks['passed']
validation={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':True,'frozen_inputs':len(cases),
            'complete_unique_runs':len(results),'all_targets_hit':True,'all_final_depths_valid':True,
            'bridge_original_endpoint_equivalence':True,'equivalence_cases':len(checks['rows'])}
(ROOT/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
files=[]
for file in sorted(ROOT.rglob('*')):
    if file.is_file() and '__pycache__' not in file.parts and file.name!='artifact_manifest.json':
        files.append({'path':str(file.relative_to(ROOT)),'bytes':file.stat().st_size,'sha256':sha(file)})
dependencies=['geometry.py','reference_ba.py','experiment.py','collective.py','partition.py','curvature.py']
manifest={'utc':validation['utc'],'source_parent_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'package_files':files,'geometry_dependencies':{n:sha(GEOMETRY/n) for n in dependencies},
          'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,'matplotlib':matplotlib.__version__,
          'platform':platform.platform(),'cpu':next(x.split(':',1)[1].strip() for x in pathlib.Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name')),
          'threads':{'OPENBLAS_NUM_THREADS':1,'OMP_NUM_THREADS':1},'precision':'FP64','gpu_used':False}
(ROOT/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(validation,indent=2))
