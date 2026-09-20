"""Verify completed attribution artifacts and save a compact persistent archive.

Run the harness stages first. Verification JSON is the collected, audited result
of those stages; this script checks it against their original per-run records.
"""
import pathlib,json,hashlib,tarfile,shutil
ROOT=pathlib.Path('/tmp/prism-controller-attribution')
DEST=pathlib.Path('/workspace/prism-controller-attribution')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(8*1024*1024):h.update(b)
 return h.hexdigest()
def main():
 v=json.loads((ROOT/'verification.json').read_text());assert v['runs']==len(v['rows'])==58
 locations={}
 for r in v['rows']:
  stem=ROOT/r['group']/f'{r["scene"]}-{r["arm"]}-{r["rep"]}'
  raw=json.loads(stem.with_suffix('.result.json').read_text())
  assert all(r[k]==value for k,value in raw.items())
  assert r['returncode']==0 and r['audit_error']<1e-7
  state=stem.with_suffix('.state');assert sha(state)==r['state_sha256']
  locations[str(state.relative_to(ROOT))]=str(state)
 assert v['hits']==sum(r['hit'] for r in v['rows'])
 m=json.loads((ROOT/'build/manifest.json').read_text())
 assert sha(ROOT/'build/source.cu')==m['source_sha256'] and sha(ROOT/'build/prism-tr')==m['binary_sha256']
 assert all(sha(ROOT/'build/headers'/name)==digest for name,digest in m['headers_sha256'].items())
 assert sha(pathlib.Path('/workspace/prism-ba/gpu/oca_cuda.cu'))=='0b7aac9b70523ce08d791e1a75c6c18a672cdfb29f28c6a3ab21c0bf5e786569'
 for job in json.loads(pathlib.Path('/workspace/prism-block-error/paused-verified.json').read_text()):
  stat=pathlib.Path(f'/proc/{job["pid"]}/stat').read_text().split();assert stat[2]=='T' and stat[21]==str(job['start_ticks'])
 for group in ['dense-check','dense-anisotropic']:
  p=ROOT/group/'endpoint.state';locations[str(p.relative_to(ROOT))]=str(p)
 (ROOT/'endpoint_locations.json').write_text(json.dumps(locations,indent=2))
 tools=ROOT/'tools';tools.mkdir(exist_ok=True)
 for name in ['build_controller_attribution.py','controller_attribution.py','report_controller_attribution.py']:
  shutil.copy2(pathlib.Path('/workspace/prism-ba/bench')/name,tools/name)
 archive=ROOT/'artifacts.tar.gz'
 with tarfile.open(archive,'w:gz') as t:
  for p in ROOT.rglob('*'):
   if p.is_file() and p.suffix!='.state' and p!=archive and p.name!='prism-tr.gz':t.add(p,arcname=str(p.relative_to(ROOT)))
 DEST.mkdir(exist_ok=True)
 for name in ['artifacts.tar.gz','verification.json','endpoint_locations.json','selected_candidate.json','REPORT.md']:
  shutil.copy2(ROOT/name,DEST/name)
 assert sha(archive)==sha(DEST/'artifacts.tar.gz')
 print(json.dumps({k:value for k,value in v.items() if k not in ('summary','rows')},indent=2))
 print('Archive SHA256:',sha(archive))
if __name__=='__main__':main()
