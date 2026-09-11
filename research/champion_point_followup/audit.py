import pathlib,json,re,hashlib,math
P=pathlib.Path(__file__).resolve().parent
rows=[]
for file in sorted((P/'evidence').glob('*/*/result.json')):
    row=json.loads(file.read_text());text=(file.parent/'stdout.log').read_text()
    clean=re.sub(r'\[R9\] wrote [^\n]+\n','',text)
    m=re.search(r'MFCG: accepts=(\d+)\s+rejects=(\d+)\s+total_matvecs=(\d+)',clean)
    assert m,file
    row.update(accepted=int(m[1]),rejects=int(m[2]),matvecs=int(m[3]))
    assert row['accepted']==row['outers'],file
    curve=[line.split(',') for line in (file.parent/'curve.csv').read_text().splitlines()[2:] if line]
    costs=[float(x[1]) for x in curve];times=[float(x[2]) for x in curve]
    assert all(math.isfinite(c) for c in costs) and all(b<=a+1e-8*max(1,abs(a)) for a,b in zip(costs,costs[1:]))
    assert all(b>=a for a,b in zip(times,times[1:]))
    assert abs(costs[-1]-row['final_cost'])<1e-7*max(1,abs(row['final_cost']))
    if row['hit']:assert row['final_cost']<=row['target']*(1-1e-8)
    else:assert row['target_seconds'] is None
    file.write_text(json.dumps(row,indent=2)+'\n');rows.append(row)
for stage in sorted({r['stage'] for r in rows}):
    (P/(stage+'-results.json')).write_text(json.dumps([r for r in rows if r['stage']==stage],indent=2)+'\n')
B=P.parent/'eta2_champion';m=json.loads((B/'source_manifest.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(B/'source/prism_eta2.cu')==m['source_sha256']
assert all(sha(B/'source/headers'/n)==h for n,h in m['headers_sha256'].items())
report=dict(native_runs=len(rows),monotonic_finite_traces=True,target_and_endpoint_checks=True,frozen_source_and_headers_unchanged=True,counts_by_stage={s:sum(r['stage']==s for r in rows) for s in sorted({r['stage'] for r in rows})},cpu_holdout_runs=len(json.loads((P/'holdout_results.json').read_text())))
(P/'audit.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
