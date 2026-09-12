#!/usr/bin/env python3
import fcntl,json,os,re,subprocess,sys,statistics
from pathlib import Path
from build import P,C,sha
from trace_report import report
sys.path.insert(0,str(C));import grid_common as common
OUT=P/'evidence/correctness';SAN='/usr/local/cuda/bin/compute-sanitizer'

def locked(name,cmd,env=None):
    folder=OUT/name;folder.mkdir(parents=True,exist_ok=True)
    with open('/tmp/prism_gpu.lock','w') as lock,(folder/'stdout.log').open('w') as log:
        fcntl.flock(lock,fcntl.LOCK_EX);result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=180)
    text=(folder/'stdout.log').read_text();passed=result.returncode==0 and 'ERROR SUMMARY: 0 errors' in text
    (folder/'result.json').write_text(json.dumps(dict(command=cmd,returncode=result.returncode,passed=passed),indent=2)+'\n')
    if not passed:raise RuntimeError(text[-4000:])
    print(name,'passed',flush=True)

def main():
    manifest=json.loads((P/'build_manifest.json').read_text());binary=P/'build/prism-passenger'
    assert sha(binary)==manifest['binary_sha256'] and all(sha(P/h)==s for h,s in manifest['local_headers'].items())
    subprocess.run(['python',str(P/'check_toy.py'),'--create'],check=True)
    locked('kernel-memcheck',[SAN,'--tool','memcheck','--leak-check','full','--error-exitcode','91',str(P/'build/passenger-toy'),str(P/'evidence/toy')])
    subprocess.run(['python',str(P/'check_toy.py')],check=True)
    for on in (0,1):
        folder=OUT/f'tiny-memcheck-{on}';folder.mkdir(parents=True,exist_ok=True)
        flags=dict(common.CHAMP['flags'],OCA_PASSENGER=str(on),OCA_STCG_ATTEMPTS=str(folder/'attempts.json'),OCA_MAX_SECONDS='60')
        env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','CERES_','COLMAP_MFREE','MF_DEBUG'))};env.update(flags)
        cmd=[SAN,'--tool','memcheck','--error-exitcode','91',str(binary),'--problem',str(C/'build/toy.txt'),*common.CHAMP['cli'],'--csv',str(folder/'curve.csv')]
        (folder/'manifest.json').write_text(json.dumps(dict(command=cmd,flags=flags,binary_sha256=sha(binary),input_sha256=sha(C/'build/toy.txt')),indent=2)+'\n')
        locked(f'tiny-memcheck-{on}',cmd,env);result=report(folder)
        if on:assert len(result['probe_events'])==1,'tiny native gate never exercised'
    rows=[]
    for rep in range(3):
        for arm in (['original','off'] if rep%2==0 else ['off','original']):
            folder=OUT/f'dubrovnik-88-{arm}-{rep}'
            flags=dict(OCA_PASSENGER='0')
            if arm=='off':flags['OCA_STCG_ATTEMPTS']=str(folder/'attempts.json')
            rows.append(common.run(folder,'dubrovnik-88',arm,rep,common.ORIGINAL if arm=='original' else binary,flags,C/'PROTOCOL_09_NATIVE.md',target=0,cap=5,build_manifest=manifest if arm=='off' else None))
            if arm=='off':report(folder)
    med={a:statistics.median(r['cost'] for r in rows if r['arm']==a) for a in ('original','off')};delta=med['off']/med['original']-1
    result=dict(median_cost=med,relative_cost_delta=delta,endpoint_compatibility=abs(delta)<=.0015,
        score_init_relative_spread=(max(r['score_init'] for r in rows)-min(r['score_init'] for r in rows))/max(r['score_init'] for r in rows),
        native_times={a:[r['native_seconds'] for r in rows if r['arm']==a] for a in ('original','off')},rows=rows)
    assert result['endpoint_compatibility'] and result['score_init_relative_spread']<1e-10
    (P/'compatibility.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
