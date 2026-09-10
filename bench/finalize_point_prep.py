import pathlib,json,sys,re,hashlib,shutil,subprocess
sys.path.insert(0,'/workspace/prism-ba/bench')
from audit_prism_state import audit
from cached_benchmark_input import load_input
from build_tr_candidate import sha
R=pathlib.Path('/workspace/prism-tr-point-prep');repo=pathlib.Path('/workspace/prism-ba');P=R/'package'
dh,(dims,obs),initial=load_input(pathlib.Path('/workspace/bal/trafalgar-126.txt'),'/workspace/prism-caspar-expanded/cpu-cache');cost=audit(R/'package-rebuilt.state',dims,obs);log=(R/'package-smoke.log').read_text();reported=float(re.search(r'RESULT .*final_cost=(\S+)',log)[1]);assert abs(cost-reported)/cost<1e-7 and cost<104534.24152926281*(1-1e-8);assert 'TARGET reached' in log
result=dict(cost=cost,reported=reported,audit_error=abs(cost-reported)/cost,input_sha256=dh,state_sha256=sha(R/'package-rebuilt.state'),tested_binary_sha256=sha(P/'prism-tr'),rebuilt_binary_sha256=sha(P/'prism-tr-rebuilt'),crossing=float(re.search(r'TARGET reached .*seconds=(\S+)',log)[1]));(R/'package-smoke.json').write_text(json.dumps(result,indent=2));print(result)
paused=json.loads((R/'paused-verified.json').read_text())
for v in paused:
 f=(pathlib.Path('/proc')/str(v['pid'])/'stat').read_text().split();assert f[2]=='T' and f[21]==v['start_ticks']
files=[*repo.glob('bench/*point_prep*.py'),repo/'bench/point_prep_bench.cu',repo/'bench/test_point_prep.cu',repo/'gpu/point_prep_candidate.cuh',repo/'docs/point_preparation_results.md'];out=R/'final-tooling';out.mkdir(exist_ok=True)
for p in files:shutil.copy2(p,out/p.name)
(R/'final-tooling.json').write_text(json.dumps(dict(files={str(p):sha(p) for p in files},paused_jobs_verified=len(paused),production_sha256=sha(repo/'gpu/oca_cuda.cu'),diagnostic_capture_cost=json.loads((R/'capture-v2/result.json').read_text())['cost'],profile=json.loads((R/'combined-profile/result.json').read_text())),indent=2))
for p in [R/'package-smoke.json',R/'final-tooling.json']:shutil.copy2(p,P/'results'/p.name)
(P/'files.json').write_text(json.dumps({str(p.relative_to(P)):sha(p) for p in P.rglob('*') if p.is_file() and p!=P/'files.json'},indent=2));subprocess.run(['tar','-czf',str(P)+'.tar.gz','-C',str(R),'package'],check=True);(R/'package-sha256.json').write_text(json.dumps(dict(archive_sha256=sha(str(P)+'.tar.gz'),bytes=pathlib.Path(str(P)+'.tar.gz').stat().st_size),indent=2));print('PACKAGED',str(P)+'.tar.gz')
