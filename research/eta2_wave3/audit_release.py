"""Verify frozen sources, every completed native export and research audits."""
from pathlib import Path
import gzip,hashlib,json,sys
P=Path(__file__).resolve().parent
sys.path.insert(0,str(P.parent/'eta2_research_20260912/coarse'))
from diagnostic import verify_baseline
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 frozen=verify_baseline();bm=json.loads((P/'build_manifest.json').read_text());assert sha(P/'build/prism-wave3')==bm['binary_sha256']
 assert all(sha(p)==h for p,h in bm['sources'].items())
 rows=[];initial={}
 for path in sorted((P/'evidence').glob('*/*/result.json')):
  r=json.loads(path.read_text());m=json.loads((path.parent/'manifest.json').read_text())
  assert r['valid'] and 'state' in r,path
  assert sha(m['command'][0])==m['binary_sha256'],path
  assert sha(path.parent/'endpoint.state.gz')==r['state']['compressed_sha256'],path
  with gzip.open(path.parent/'endpoint.state.gz','rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['state']['sha256'],path
  if r['hit']:assert r['cost']<=r['target'] and r['target_seconds'] is not None
  initial.setdefault(r['scene'],[]).append(r['score_init']);rows.append(str(path.parent.relative_to(P)))
 for scene,v in initial.items():assert (max(v)-min(v))/max(1,max(v))<1e-8,(scene,min(v),max(v))
 assert json.loads((P/'local_validation.json').read_text())['passed']
 assert json.loads((P/'intrinsic_operator_audit.json').read_text())['passed']
 e4=json.loads((P/'miss-forensics/decision.json').read_text());assert e4['complete'] and sha(e4['archive'])==e4['sha256']
 for record in json.loads((P/'old_endpoint_archives.json').read_text()):assert record['verified_exact_gzip'] and sha(record['archive'])==record['archive_sha256']
 report=dict(passed=True,frozen=frozen,native_rows=len(rows),sources=rows,all_endpoints_compressed_and_raw_hash_verified=True,
  initial_cost_relative_spread={s:(max(v)-min(v))/max(1,max(v)) for s,v in initial.items()},local_primitives_and_projected_solve_passed=True,
  e4_archive_verified=True,old_gzip_containers_exactly_restorable=True,
  timing_note='Opening and combination hit-screen walls may overlap CPU compaction; practical/confirmation comparisons are isolated')
 (P/'release_audit.json').write_text(json.dumps(report,indent=2)+'\n');print('RELEASE AUDIT PASS',len(rows))
if __name__=='__main__':main()
