#!/usr/bin/env python3
"""Two short display traces; preserve the existing N=3 benchmark unchanged."""
import pathlib,os,json,subprocess,fcntl,time,re,hashlib,csv,shutil
ROOT=pathlib.Path(__file__).resolve().parent
OUT=pathlib.Path(os.environ.get('PRISM_CURVES_OUT','/workspace/prism-schur-physics-largest-curves'))
OUT.mkdir(parents=True,exist_ok=True)
cfg=json.loads((ROOT.parent/'eta2_champion/champion.json').read_text())
binary=ROOT/'build/prism-coarse'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
previous=json.loads(pathlib.Path('/workspace/prism-schur-physics-largest/manifest.json').read_text())
assert sha(binary)==previous['binary_sha256']
history=pathlib.Path('/workspace/prism-final13682-convergence')
historical=json.loads((history/'protocol.json').read_text())
assert previous['input_sha256']==historical['scenes']['final-13682']['input_sha256']
protocol={'purpose':'Visualization only: one timestamped trace per current Prism arm. Existing N=3 target statistics remain authoritative.','scene':'final-13682','binary_sha256':sha(binary),'input_sha256':previous['input_sha256'],'display_stop_cost':25000000,'native_cap':20,'outer_cap':30,'repeats':1,'display_target_note':'25M is chosen to display the later trajectory already explored by the capped run; it is not a newly registered performance gate.','clock':'Existing CSV timestamps receive the same-run terminal TARGET offset. CSV resolution is 0.1ms, and the final flush-to-TARGET delay is conservatively retained. No timings inferred from iteration counts.','historical_caspar':'Use the median-target-time representative from the previously recorded N=3 same-input/host batch, clearly labeled historical. Do not extrapolate past its target stop.','no_endpoint_export':True}
(OUT/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
for name in ['curves.csv','protocol.json','summary.json','README.md']:
    dest=OUT/'historical';dest.mkdir(exist_ok=True);shutil.copy2(history/name,dest/name)
env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}
with open('/tmp/prism_gpu.lock','w') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    for rank in [0,16]:
        stem=OUT/f'rank{rank}'
        if stem.with_suffix('.json').exists():continue
        cli=cfg['cli'].copy();cli[cli.index('--max_iter')+1]='30'
        cmd=[str(binary),'--problem','/workspace/bal/final-13682.txt',*cli,'--csv',str(stem.with_suffix('.csv'))]
        flags=cfg['flags']|{'OCA_COARSE_RANK':str(rank),'OCA_MAX_SECONDS':'20','OCA_TARGET_COST':'25000000'}
        start=time.monotonic();print('TRACE',rank,flush=True)
        with stem.with_suffix('.log').open('w') as f:
            try:rc=subprocess.run(cmd,env=env|flags,stdout=f,stderr=subprocess.STDOUT,timeout=120).returncode
            except subprocess.TimeoutExpired:rc=124
        text=stem.with_suffix('.log').read_text();m=re.search(r'TARGET reached outer=(\d+) seconds=(\S+) cost=(\S+) threshold=(\S+)',text)
        row={'command':cmd,'flags':flags,'returncode':rc,'process_seconds':time.monotonic()-start,'rank':rank,'target_hit':bool(m)}
        if m:row.update(target_outers=int(m[1]),target_seconds=float(m[2]),target_cost=float(m[3]))
        row['coarse_active']=sum(int(x) for x in re.findall(r'COARSE_PREP .*?active=(\d+)',text))
        stem.with_suffix('.json').write_text(json.dumps(row,indent=2)+'\n')
        print(json.dumps(row),flush=True)
        if rc or not m:raise SystemExit('Trace lacks its native TARGET anchor; retain raw output and do not invent an offset.')
print('DONE curve traces',flush=True)
