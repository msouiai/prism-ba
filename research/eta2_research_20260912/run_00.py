#!/usr/bin/env python3
"""Serial registered witness collection; all selection attempts stay visible."""
import argparse,csv,fcntl,gzip,hashlib,json,math,os,re,shutil,socket,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;F=P.parent/'eta2_champion'
sys.path.insert(0,str(F/'bench'))
from audit_prism_state import observations,audit
CHAMP=json.loads((F/'champion.json').read_text())
ORIGINAL=Path('/tmp/prism-rl-actor/build/prism-tr')
TARGETS={'venice-52':243740.27,'final-3068':1744796.9841897595}
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,obj):p.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def pack(p):
    gz=Path(str(p)+'.gz')
    with p.open('rb') as src,gzip.open(gz,'wb',compresslevel=1) as dst:shutil.copyfileobj(src,dst)
    with gzip.open(gz,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==sha(p)
    record=dict(bytes=p.stat().st_size,sha256=sha(p),compressed_sha256=sha(gz))
    p.unlink() # Only this run's new file, after verified lossless compression.
    return record
def run(scene,arm,rep,stage,problem=None,sanitizer=False):
    folder=P/'evidence'/stage/f'{scene}-{arm}-{rep}';folder.mkdir(parents=True,exist_ok=True)
    if (folder/'result.json').exists():return json.loads((folder/'result.json').read_text())
    problem=Path(problem) if problem else Path('/workspace/bal')/(scene+'.txt')
    binary=ORIGINAL if arm=='original' else P/'build/prism-brief0'
    bm=json.loads((P/'build/manifest.json').read_text())
    expected=CHAMP['binary_sha256'] if arm=='original' else bm['binary_sha256'];assert sha(binary)==expected
    flags=dict(CHAMP['flags'],OCA_MAX_SECONDS='60')
    if scene in TARGETS:flags['OCA_TARGET_COST']=str(TARGETS[scene])
    if arm=='capture':
        flags['OCA_BRIEF0_DIR']=str(folder)
        if scene=='ladybug-1197':flags['OCA_BRIEF0_OUTER']='1'
        elif stage=='toy':flags['OCA_BRIEF0_OUTER']='0'
    env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','CERES_','COLMAP_MFREE','MF_DEBUG'))}
    env.update(flags)
    cmd=[str(binary),'--problem',str(problem),*CHAMP['cli'],'--csv',str(folder/'curve.csv'),'--state_out',str(folder/'endpoint.state')]
    if sanitizer:cmd=['/usr/local/cuda/bin/compute-sanitizer','--tool','memcheck','--error-exitcode','91']+cmd
    write(folder/'manifest.json',dict(command=cmd,flags=flags,input_sha256=sha(problem),binary_sha256=expected,
      source_sha256=sha(F/'source/prism_eta2.cu') if arm=='original' else bm['source_sha256'],protocol_sha256=sha(P/'PROTOCOL_00.md'),host=socket.gethostname()))
    print('RUN',stage,scene,arm,rep,flush=True);begin=time.monotonic()
    with (folder/'stdout.log').open('w') as out,(folder/'stderr.log').open('w') as err:
        try:rc=subprocess.run(cmd,env=env,stdout=out,stderr=err,timeout=900).returncode
        except subprocess.TimeoutExpired:rc=124
    text=(folder/'stdout.log').read_text();m=re.search(r'RESULT .*?iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)',text)
    row=dict(scene=scene,arm=arm,rep=rep,stage=stage,returncode=rc,process_seconds=time.monotonic()-begin,
      source=str(folder.relative_to(P)),captured='BRIEF0_COMPLETE' in text,hit='TARGET reached' in text,valid=False)
    try:
        assert rc==0 and m,(rc,bool(m))
        dims,obs=observations(problem);cost=audit(folder/'endpoint.state',dims,obs)
        assert abs(cost-float(m[2]))/max(1,cost)<1e-6
        count=re.search(r'MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)',text);assert count
        initial=list(csv.DictReader(l for l in (folder/'curve.csv').read_text().splitlines() if not l.startswith('#')))[0]['cost']
        row.update(valid=True,cost=cost,native_seconds=float(m[3]),outers=int(m[1]),accepts=int(count[1]),
          rejects=int(count[2]),matvecs=int(count[3]),score_init=float(initial))
        if row['captured']:
            meta={k:float(v) for k,v in (l.split('=') for l in (folder/'metadata.txt').read_text().splitlines())}
            assert abs(meta['cost']-cost)/max(1,cost)<1e-9
            row['metadata']=meta
            row['directions']=list(csv.DictReader((folder/'native_directions.csv').open()))
            row['reference_certified']=all(r['certified']=='1' for r in row['directions'] if r['arm'].startswith('exact'))
            assert len(row['directions'])==7
        row['state']=pack(folder/'endpoint.state')
        # Keep witness state/directions uncompressed for the imminent CPU audit;
        # their later verified archive is charged separately from native solves.
    except Exception as exc:row['error']=str(exc)
    write(folder/'result.json',row)
    print('DONE',stage,scene,arm,rep,'valid',row['valid'],'captured',row['captured'],'hit',row['hit'],
      'cost',row.get('cost'),'seconds',row.get('native_seconds'),'certified',row.get('reference_certified'),'error',row.get('error'),flush=True)
    assert row['valid'],row
    return row
def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['compatibility','collect','toy']);ap.add_argument('--problem');ap.add_argument('--sanitizer',action='store_true');ap.add_argument('--scene');a=ap.parse_args()
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        assert sha(ORIGINAL)==CHAMP['binary_sha256']
        if a.stage=='toy':run('toy','capture',int(a.sanitizer),'toy',a.problem,a.sanitizer);return
        rows=[]
        if a.stage=='compatibility':
            for rep in range(3):
                for arm in (['original','off'] if rep%2==0 else ['off','original']):rows.append(run('dubrovnik-88',arm,rep,a.stage))
        else:
            assert (P/'compatibility-results.json').exists()
            for scene in ([a.scene] if a.scene else ['venice-52','final-3068','ladybug-1197']):
                captured=0
                for rep in range(3 if scene=='ladybug-1197' else 20):
                    r=run(scene,'capture',rep,a.stage);rows.append(r);captured+=r['captured']
                    write(P/(a.stage+'-'+scene+'-results.json'),[x for x in rows if x['scene']==scene])
                    if captured==3:break
                assert captured==3,(scene,captured)
        write(P/(a.stage+'-results.json'),rows)
if __name__=='__main__':main()
