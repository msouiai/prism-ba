"""Release integrity checks justified by the storage-quota failures."""
from pathlib import Path
import csv,hashlib,json,subprocess
P=Path(__file__).resolve().parent
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    subprocess.run(['python3',str(P.parent/'eta2_champion/build.py'),'--check-only'],check=True)
    with (P/'metrics.csv').open() as f:rows=list(csv.DictReader(f))
    assert len(rows)==425 and len({r['source'] for r in rows})==425
    binaries={};points=0;originals=0
    for r in rows:
        folder=P/r['source'];result=json.loads((folder/'result.json').read_text());m=json.loads((folder/'manifest.json').read_text())
        assert result['valid'] and result['audit_relative_error']<1e-6
        assert m['flags']['OCA_NSHIFTS']=='1' and '--dof9' in m['command'] and '--zero_k2' in m['command'] and '--mf-fp32' not in m['command']
        b=m['command'][0]
        if b not in binaries:binaries[b]=sha(b)
        assert binaries[b]==m['binary_sha256']
        assert sha(folder/'endpoint.state.gz')==result['state']['compressed_sha256'];points+=1
        assert m['target']==result['target']
        originals+=r['arm']=='original'
    for path in (P/'composition').glob('*/archive.json'):
        m=json.loads(path.read_text());assert sha(m['path'])==m['sha256']
    geo=json.loads((P/'geodesic_native_validation/audit.json').read_text());assert geo['passed'] and geo['memcheck_passed']
    for path in (P/'geodesic_analytic').glob('*/independent_geodesic.json'):
        a=json.loads(path.read_text());assert a['analytic_second_derivative'];assert all(r['second_full_normal_relative']<1e-8 for r in a['rows'])
    assert json.loads((P/'plateau-witness-decision.json').read_text())['killed']
    report=dict(passed=True,native_rows=len(rows),verified_endpoint_exports=points,original_binary_runs=originals,binary_sha256=binaries,
      full_point_retention='SNAPSHOT_RETENTION_ADDENDUM.md',
      note='Original-arm manifests retain the campaign build context; actual binary hash and frozen champion source/config identify the original executable.')
    (P/'release_audit.json').write_text(json.dumps(report,indent=2)+'\n');print('RELEASE AUDIT PASSED',len(rows),flush=True)
if __name__=='__main__':main()
