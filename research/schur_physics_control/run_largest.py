#!/usr/bin/env python3
"""Bounded Final13682 extension using the previously measured binary."""
import pathlib,os,json,subprocess,fcntl,time,re,hashlib,shutil
ROOT=pathlib.Path(__file__).resolve().parent
OUT=pathlib.Path(os.environ.get('PRISM_LARGEST_OUT','/workspace/prism-schur-physics-largest'))
OUT.mkdir(exist_ok=True,parents=True)
if (OUT/'runs.json').exists():raise SystemExit('Completed output exists; choose PRISM_LARGEST_OUT for a new cohort.')
binary=ROOT/'build/prism-coarse';scene=pathlib.Path('/workspace/bal/final-13682.txt')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected=json.loads((ROOT/'build/solver-manifest.json').read_text())['binary_sha256']
assert sha(binary)==expected
frozen=ROOT.parent/'eta2_champion'
manifest=json.loads((frozen/'source_manifest.json').read_text())
assert sha(frozen/'source/prism_eta2.cu')==manifest['source_sha256']
assert all(sha(frozen/'source/headers'/name)==h for name,h in manifest['headers_sha256'].items())
cfg=json.loads((frozen/'champion.json').read_text())
base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}
shutil.copy2(ROOT/'LARGEST_PROTOCOL.md',OUT/'PROTOCOL.md')
with scene.open('rb') as f:input_hash=hashlib.file_digest(f,'sha256').hexdigest()
spec={'binary':str(binary),'binary_sha256':expected,'input':str(scene),'input_sha256':input_hash,'source_commit':'2db2175','flags':cfg['flags'],'cli':cfg['cli'],'targets':{'primary':27591576.557625167,'tighter':27318392.631312046},'native_cap':12,'process_cap':120,'repeats':3,'native_budget':180}
(OUT/'manifest.json').write_text(json.dumps(spec,indent=2)+'\n')
rows=[]
def kv(text,prefix):return [dict(x.split('=',1) for x in l.split()[1:] if '=' in x) for l in text.splitlines() if l.startswith(prefix+' ')]
def run(panel,rank,rep,target=None):
    stem=f'{panel}-r{rank}-{rep}';path=OUT/(stem+'.log');cli=cfg['cli'].copy()
    if panel=='activation':cli[cli.index('--max_iter')+1]='30'
    flags=cfg['flags']|{'OCA_COARSE_RANK':str(rank),'OCA_MAX_SECONDS':'12'}
    if target is not None:flags['OCA_TARGET_COST']=str(target)
    cmd=[str(binary),'--problem',str(scene),*cli]
    print('RUN',stem,flush=True);start=time.monotonic();peak=0;polls=0;last_gpu_sample=0
    with path.open('w') as f:
        proc=subprocess.Popen(cmd,env=base|flags,stdout=f,stderr=subprocess.STDOUT)
        while proc.poll() is None:
            elapsed=time.monotonic()-start
            if elapsed>120:proc.kill();proc.wait();break
            if elapsed-last_gpu_sample>=.5:
                # Driver query only; no competing CUDA context or kernel launch.
                q=subprocess.run(['nvidia-smi','--query-compute-apps=pid,used_gpu_memory','--format=csv,noheader,nounits'],capture_output=True,text=True)
                for line in q.stdout.splitlines():
                    fields=line.split(',')
                    if len(fields)==2 and fields[0].strip()==str(proc.pid):
                        try:peak=max(peak,int(fields[1].strip()));polls+=1
                        except ValueError:pass
                last_gpu_sample=elapsed
            time.sleep(.05)
    duration=time.monotonic()-start;text=path.read_text()
    row={'panel':panel,'rank':rank,'rep':rep,'command':cmd,'flags':flags,'returncode':proc.returncode,'process_seconds':duration,'process_timeout':duration>120,'sampled_peak_gpu_MiB':peak,'gpu_samples':polls,'target':target,'target_hit':False}
    m=re.search(r'RESULT algo=\S+ iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)',text)
    if m:row.update(outers=int(m[1]),cost=float(m[2]),native_seconds=float(m[3]))
    m=re.search(r'TARGET reached outer=(\d+) seconds=(\S+) cost=(\S+) threshold=(\S+)',text)
    if m:row.update(target_outers=int(m[1]),target_seconds=float(m[2]),target_cost=float(m[3]),target_hit=proc.returncode==0 and float(m[2])<=12 and float(m[3])<=target)
    m=re.search(r'MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)',text)
    if m:row.update(accepts=int(m[1]),rejects=int(m[2]),matvecs=int(m[3]))
    row['coarse_preparations']=kv(text,'COARSE_PREP')
    row['coarse_active']=sum(int(x['active']) for x in row['coarse_preparations'])
    row['coarse_rejects']=max((int(x['rejected']) for x in row['coarse_preparations']),default=0)
    row['stop_messages']=[l.strip() for l in text.splitlines() if 'converged (' in l or 'budget' in l.lower() or 'MAX_SECONDS' in l]
    path.with_suffix('.json').write_text(json.dumps(row,indent=2)+'\n');rows.append(row)
    (OUT/'runs.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps({k:v for k,v in row.items() if k in ['panel','rank','rep','returncode','cost','outers','target_seconds','target_hit','coarse_active','native_seconds','sampled_peak_gpu_MiB']}),flush=True)
    return row
with open('/tmp/prism_gpu.lock','w') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    for panel,target in spec['targets'].items():
        for rep in range(3):
            for rank in ([0,16] if rep%2==0 else [16,0]):run(panel,rank,rep,target)
    initial=[]
    for rank in [0,16]:initial.append(run('activation',rank,0))
    if initial[1]['coarse_active']:
        for rep in [1,2]:
            for rank in ([16,0] if rep==1 else [0,16]):run('activation',rank,rep)
print('DONE largest extension',flush=True)
