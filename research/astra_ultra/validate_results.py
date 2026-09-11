import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,hashlib,platform,subprocess,sys
import numpy as np
from paths import ROOT,load_packed,write_json
from reference_ba import valid_cost
from geometry import State
from experiment import alignment_error
import scipy

read=lambda p:json.loads((ROOT/p).read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cases={r['id']:r for r in read('cases.json')};assert len(cases)==15
inputs={}
for name,c in cases.items():
    p=(ROOT.parent if c.get('input_from_research_root') else ROOT)/c['input']
    assert sha(p)==c['sha256']
    s,obs=load_packed(p);f0=valid_cost(s,obs)
    assert abs(f0-c['initial_cost'])<1e-11*max(f0,1.)
    inputs[name]=(s,obs)
    if c['family']!='bal':
        assert c['target']==1.01*c['reference_cost'] and c['deep_target']==1.001*c['reference_cost']
        z=np.load(p);ref=State(z['ref_R'],z['ref_t'],z['ref_X'],s.intr)
        assert abs(valid_cost(ref,obs)-c['reference_cost'])<1e-11*max(c['reference_cost'],1.)
assert read('ray_checks.json')['passed']
rows=read('path_results.json')['rows'];assert len(rows)==180
endpoint_errors=[]
for r in rows:
    assert r['hit'] and r['cost']<=r['target'] and r['target']==cases[r['id']]['target']
    assert len(r['trace'])==r['accepted']+1
    assert all(b['cost']<a['cost'] for a,b in zip(r['trace'],r['trace'][1:]))
    assert r['trace'][-1]['seconds']<=r['seconds']
    if r['rep']!=0:continue
    s,obs=inputs[r['id']];z=np.load(ROOT/'evidence'/f"path-{r['id']}-{r['arm']}.npz")
    final=State(*[z[k] for k in ['R','t','X','intr']]);f=valid_cost(final,obs)
    rel=abs(f-r['cost'])/max(f,1.);endpoint_errors.append(rel);assert rel<1e-12
    assert np.array_equal(final.R[0],s.R[0]) and np.array_equal(final.t[0],s.t[0])
    assert final.X[0,2]==s.X[0,2] and np.array_equal(final.intr,s.intr)
assert len(endpoint_errors)==60
ray=read('ray_diagnostics.json')['rows'];assert len(ray)==432
assert all(r['valid'] for r in ray)
stiff=read('stiffness_diagnostic.json');assert stiff['algebra_passed'] and len(stiff['rows'])==36
assert len(stiff['finite_difference_checks'])==12 and not stiff['gate']['passed']
for r in stiff['rows']:
    assert r['decomposition_relative_error']<1e-10 and r['rank1_factor_relative_error']<1e-12
    for a in r['augmented']:assert a['augmented_prediction']<=a['original_gn_prediction']+1e-8*max(abs(a['original_gn_prediction']),1.)
energy=read('energy_results.json')['rows'];assert len(energy)==45
for r in energy:
    assert r['quadratic_identity_max_relative_error']<1e-9
    for name,a in r['rules'].items():
        assert a['selected'] and a['valid'] and a['rho']>.1
        assert a['products']==a['iteration']+a['iteration']//10+a['true_exit_checks']
        assert a['iteration']<10 and a['true_exit_checks']==1
        if name in ['oracle_full','bound_full']:assert a['fraction_optimal_full_decrement']>=1/1.1-1e-10
decisions=read('decisions.json')
assert not any(g['general_promotion'] for g in decisions['paths'])
assert not decisions['stiffness']['passed'] and not decisions['energy_bound']['gate']
base='d988b59a3b63a488ffd95c6ab3cc1cd672e2aa6e'
subprocess.run(['git','diff','--exit-code',base,'--','gpu','research/eta2_champion',
    'research/geometry_agenda','research/collective_bal','research/schur_physics_control','research/astra_followup'],
    cwd=ROOT.parent.parent,check=True,stdout=subprocess.PIPE)
write_json(ROOT/'validation.json',{'passed':True,'unchanged_original_source_base':base,'input_hashes_checked':len(cases),
    'full_path_runs':len(rows),'saved_endpoints_checked':len(endpoint_errors),'max_endpoint_cost_relative_error':max(endpoint_errors),
    'frozen_ray_evaluations':len(ray),'stiffness_parent_checks':len(stiff['rows']),'stiffness_fd_initial_states':12,
    'energy_parents':len(energy),'energy_selected_proposals':315,'fresh_checks_per_exit':1,
    'periodic_residual_reset_exercised':False,'failed_exit_check_exercised':False,'promotion':False})
write_json(ROOT/'environment.json',{'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,
    'platform':platform.platform(),'cpu':subprocess.check_output(['lscpu'],text=True).split('Model name:')[1].splitlines()[0].strip(),
    'BLAS_threads':1,'OMP_threads':1,'timing':'serialized CPU runs; no native/GPU experiment',
    'adviser_model':'gpt-6-astra','adviser_reasoning_effort':'ultra'})
files={}
for p in sorted(ROOT.rglob('*')):
    if not p.is_file() or any(a in ['build','__pycache__'] for a in p.relative_to(ROOT).parts) or p.name=='artifact_manifest.json':continue
    files[str(p.relative_to(ROOT))]={'bytes':p.stat().st_size,'sha256':sha(p)}
write_json(ROOT/'artifact_manifest.json',{'base_commit':base,'files':files})
print('PASS:',len(files),'inventoried artifacts;',len(rows),'path runs,36stiffness parents,45energy systems; old solver unchanged')
