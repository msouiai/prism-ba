import pathlib,json,hashlib,math,subprocess,collections
P=pathlib.Path(__file__).resolve().parent;B=P.parent/'eta2_champion'
m=json.loads((B/'source_manifest.json').read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(B/'source/prism_eta2.cu')==m['source_sha256']
assert all(sha(B/'source/headers'/n)==h for n,h in m['headers_sha256'].items())
rows=[];problem_hashes={}
small_targets=json.loads((P/'small-targets.json').read_text())['targets']
large_targets=json.loads((P/'large-targets.json').read_text())['targets']
for f in (P/'evidence').glob('*/*/result.json'):
    r=json.loads(f.read_text());man=json.loads((f.parent/'manifest.json').read_text())
    assert man['flags'].items()>=json.loads((B/'champion.json').read_text())['flags'].items()
    assert sha(pathlib.Path(man['command'][0]))==man['binary_sha256']
    problem=pathlib.Path(man['command'][man['command'].index('--problem')+1])
    if problem not in problem_hashes:problem_hashes[problem]=sha(problem)
    assert problem_hashes[problem]==man['problem_sha256']
    assert r['target']==man['target']
    if r['stage'] in ['small','collapse-diagnostic']:assert r['target']==small_targets[r['scene']]
    if r['stage']=='large':assert r['target']==large_targets[r['scene']]
    c=[float(l.split(',')[1]) for l in (f.parent/'curve.csv').read_text().splitlines()[2:] if l]
    assert all(math.isfinite(v) for v in c) and all(b<=a+1e-8*max(1,abs(a)) for a,b in zip(c,c[1:])),f
    assert abs(c[-1]-r['final_cost'])<1e-8*max(1,abs(r['final_cost']))
    if r['hit']:assert r['final_cost']<=r['target']*(1-1e-8) and r['target_seconds']<=man['cap']+.01
    else:assert r['target_seconds'] is None
    assert r['accepted']<=r['outers']
    for s in r.get('sweeps',[]):assert float(s['center'])==float(s['tau']),f
    if r['handover_reason']=='collapse':
        assert any(s['valid']=='1' and s['qualified']=='1' and float(s['clipped'])<=.001 for s in r['sweeps'])
    rows.append(r)
fixed=json.loads((P/'fixed_validation.json').read_text());assert len(fixed)==9
for case in fixed:
    if case['case']=='negative':assert not case['ok']
    else:assert case['ok'] and case['qualified'] and case['max_true_residual']<1.01e-10 and case['relative_solution_error']<1e-8
assert 'ERROR SUMMARY: 0 errors' in (P/'memcheck.txt').read_text()
counts=dict(collections.Counter(r['stage'] for r in rows))
assert counts=={'original-parity':9,'new-parity':9,'small':64,'calibrate-large':6,'large':40,'collapse-diagnostic':18,'handover-smoke':3},counts
handover=json.loads((P/'handover-validation.json').read_text());assert handover['actual_collapse_then_pcg']==3
report=dict(runs=len(rows),by_stage=counts,original_source_and_headers_unchanged=True,all_flags_retained=True,all_five_input_hashes_verified=True,accepted_costs_monotone=True,point_damping_fixed_at_menu_center=True,fixed_system_checks=len(fixed),memcheck_errors=0,actual_collapse_then_pcg=3)
(P/'audit.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
