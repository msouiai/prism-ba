import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,hashlib,subprocess,sys,platform
import numpy as np
from paths import ROOT,GEOMETRY,write_json,load_packed
from reference_ba import synthetic,valid_cost
from depth_smoothing import parallax_case
import scipy

def read(name):return json.loads((ROOT/name).read_text())
late=read('late_oracle.json');lr=late['rows']
assert len(lr)==270 and len(late['baselines'])==6
assert all(r['hit'] and r['fine_saved']==0 and r['failure'] is None and r['tail']['rejected']==0 for r in lr)
interventions=[r for r in lr if r['arm']!='continue'];assert len(interventions)==216
assert all(r['coarse']['cost']<r['parent_cost'] for r in interventions)
assert read('late_checks.json')['passed']
chart=read('chart_results.json')['rows'];assert len(chart)==270 and all(r['hit'] for r in chart)
assert read('chart_checks.json')['passed']
endpoint_errors=[]
for row in chart:
    if row['rep']!=0:continue
    family=row['family'];seed=row['seed'];arm=row['arm']
    truth,initial,obs=synthetic(seed,'rotation') if family=='rotation' else parallax_case(seed,.08 if family=='low_parallax' else 1.)
    z=np.load(ROOT/'evidence'/f'chart-{family}-{seed}-{arm}.npz')
    endpoint=initial.copy()
    for name in ['R','t','X','intr']:setattr(endpoint,name,z[name])
    assert np.array_equal(endpoint.R[0],initial.R[0]) and np.array_equal(endpoint.t[0],initial.t[0])
    assert endpoint.X[0,2]==initial.X[0,2] and np.array_equal(endpoint.intr,initial.intr)
    f=valid_cost(endpoint,obs);rel=abs(f-row['cost'])/max(f,1.)
    assert np.isfinite(f) and rel<1e-13
    endpoint_errors.append(rel)
schur=read('schur_results.json')['rows'];assert len(schur)==63
assert all(r['hit'] and r['true_relative']<=r['eta'] and not r['negative'] for r in schur)
assert read('schur_math_checks.json')['passed']
assert 'ERROR SUMMARY: 0 errors' in (ROOT/'evidence/schur-memcheck.log').read_text()
for r in schur:
    if r['scene']!='muell-gba146':assert r['refresh']==0 and r['used']==0
    elif r['arm'].startswith(('theta','energy')):assert r['refresh']==32 and r['used'] in [2,4]
# Production solver and old research sources remain byte-for-byte at the base.
base='78fc32e8f33f54eaf46b5298032ef7ce46d75620'
subprocess.run(['git','diff','--exit-code',base,'--','gpu','research/eta2_champion',
                'research/geometry_agenda','research/collective_bal','research/schur_physics_control'],
               cwd=ROOT.parent.parent,check=True,stdout=subprocess.PIPE)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(ROOT/'residual_fixed.cu')==read('schur_build_manifest.json')['source_sha256']
write_json(ROOT/'validation.json',{'passed':True,'late_rows':len(lr),'late_interventions':len(interventions),
    'late_continuation_controls':54,'chart_runs':len(chart),'saved_chart_endpoints_checked':len(endpoint_errors),
    'max_endpoint_cost_relative_error':max(endpoint_errors),'schur_runs':len(schur),'cuda_memcheck_errors':0,
    'old_solver_and_research_unchanged_from':base})
write_json(ROOT/'environment.json',{'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,
    'platform':platform.platform(),'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version','--format=csv,noheader'],text=True).strip(),
    'BLAS_threads':1,'OMP_threads':1,'timing':'serialized; CPU runs separate from native GPU replay',
    'adviser_model':'gpt-6-astra','adviser_reasoning_effort':'high'})
files={}
for p in sorted(ROOT.rglob('*')):
    if not p.is_file() or any(part in ['build','__pycache__'] for part in p.relative_to(ROOT).parts) or p.name=='artifact_manifest.json':continue
    files[str(p.relative_to(ROOT))]={'bytes':p.stat().st_size,'sha256':sha(p)}
write_json(ROOT/'artifact_manifest.json',{'base_commit':base,'files':files})
print('PASS: artifact checks, endpoint costs, gauges, result gates, unchanged incumbent;',len(files),'inventoried files')
