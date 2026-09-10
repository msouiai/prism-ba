#!/usr/bin/env python3
"""One separate terminal curvature transfer probe; no speed claim."""
import pathlib,json,os,subprocess,fcntl,time,re,hashlib,shutil
ROOT=pathlib.Path(__file__).resolve().parent
OUT=pathlib.Path(os.environ.get('PRISM_LARGEST_OUT','/workspace/prism-schur-physics-largest'))/'curvature'
OUT.mkdir(parents=True,exist_ok=True)
if (OUT/'probe.json').exists():raise SystemExit('Existing diagnostic; choose a fresh PRISM_LARGEST_OUT.')
binary=ROOT/'build/probe-eta2-extended/probe'
manifest=json.loads((binary.parent/'manifest.json').read_text())
assert hashlib.sha256(binary.read_bytes()).hexdigest()==manifest['binary_sha256']
shutil.copy2(binary.parent/'manifest.json',OUT/'build-manifest.json')
shutil.copy2(ROOT/'LARGEST_PROTOCOL.md',OUT/'PROTOCOL.md')
cfg=json.loads((ROOT.parent/'eta2_champion/champion.json').read_text());cli=cfg['cli'].copy();cli[cli.index('--max_iter')+1]='30'
flags=cfg['flags']|{'OCA_MAX_SECONDS':'12','OCA_GRAD_AUDIT':'1','OCA_RELAX_PROBE':'1'}
env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}|flags
cmd=[str(binary),'--problem','/workspace/bal/final-13682.txt',*cli]
with open('/tmp/prism_gpu.lock','w') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX);start=time.monotonic();print('RUN largest terminal curvature probe',flush=True)
    with (OUT/'probe.log').open('w') as f:
        try:rc=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=120).returncode
        except subprocess.TimeoutExpired:rc=124
text=(OUT/'probe.log').read_text()
row={'command':cmd,'flags':flags,'returncode':rc,'process_seconds':time.monotonic()-start,'speed_comparison':False}
m=re.search(r'RESULT algo=\S+ iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)',text)
if m:row.update(outers=int(m[1]),cost=float(m[2]),native_seconds=float(m[3]))
row['diagnostics']=[dict(kind=l.split()[0],**dict(x.split('=',1) for x in l.split()[1:])) for l in text.splitlines() if l.startswith(('RELAX_PROBE ','RELAX_TRIAL ','RELAX_CURVATURE ','GRAD_AUDIT phase=terminal'))]
row['stop_messages']=[l.strip() for l in text.splitlines() if 'converged (' in l or 'budget' in l.lower() or 'MAX_SECONDS' in l]
(OUT/'probe.json').write_text(json.dumps(row,indent=2)+'\n')
print(json.dumps(row,indent=2),flush=True)
