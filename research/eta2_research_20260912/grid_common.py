#!/usr/bin/env python3
"""Serial native runs with frozen inputs, independent endpoint audits and provenance."""
from pathlib import Path
import csv,fcntl,gzip,hashlib,json,os,re,shutil,socket,subprocess,sys,time
P=Path(__file__).resolve().parent
F=P.parent/'eta2_champion'
sys.path.insert(0,str(F/'bench'))
from audit_prism_state import observations,audit
CHAMP=json.loads((F/'champion.json').read_text())
ORIGINAL=Path('/tmp/prism-rl-actor/build/prism-tr')
OBS={}
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def run(folder,scene,arm,rep,binary,flags,protocol,target=0,cap=60,problem=None,cli=None,build_manifest=None):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    binary=Path(binary);problem=Path(problem or '/workspace/bal/'+scene+'.txt')
    if (folder/'result.json').exists():return json.loads((folder/'result.json').read_text())
    assert sha(ORIGINAL)==CHAMP['binary_sha256']
    env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','CERES_','COLMAP_MFREE','MF_DEBUG'))}
    config=dict(CHAMP['flags'],**flags,OCA_MAX_SECONDS=str(cap))
    if target>0:config['OCA_TARGET_COST']=str(target)
    env.update(config)
    cmd=[str(binary),'--problem',str(problem),*(cli or CHAMP['cli']),'--csv',str(folder/'curve.csv'),'--state_out',str(folder/'endpoint.state')]
    manifest=dict(command=cmd,flags=config,binary_sha256=sha(binary),input_sha256=sha(problem),
      champion_sha256=sha(F/'champion.json'),protocol_sha256=sha(protocol),host=socket.gethostname(),
      scene=scene,arm=arm,rep=rep,target=target,cap=cap,build_manifest=build_manifest)
    write(folder/'manifest.json',manifest)
    print('RUN',folder.parent.name,scene,arm,rep,flush=True)
    start=time.monotonic()
    with open('/tmp/prism_gpu.lock','w') as lock,(folder/'stdout.log').open('w') as out,(folder/'stderr.log').open('w') as err:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:rc=subprocess.run(cmd,env=env,stdout=out,stderr=err,timeout=max(120,cap*3)).returncode
        except subprocess.TimeoutExpired:rc=124
    text=(folder/'stdout.log').read_text()
    row=dict(scene=scene,arm=arm,rep=rep,target=target,cap=cap,returncode=rc,process_seconds=time.monotonic()-start,
      valid=False,source=str(folder.relative_to(P)))
    try:
        m=re.search(r'RESULT .*?iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)',text)
        assert rc==0 and m,(rc,bool(m))
        if str(problem) not in OBS:OBS[str(problem)]=observations(problem)
        cost=audit(folder/'endpoint.state',*OBS[str(problem)])
        relative=abs(cost-float(m[2]))/max(1,cost);assert relative<1e-6,relative
        count=re.search(r'MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+).*?negcurv=(\d+)',text);assert count
        curves=list(csv.DictReader(x for x in (folder/'curve.csv').read_text().splitlines() if not x.startswith('#')))
        target_rows=[r for r in curves if target>0 and float(r['cost'])<=target]
        crossing=float(target_rows[0]['wall_s']) if target_rows else None
        # Target-stopped final state is independently audited. Native CSV has four decimal time precision.
        hit=target>0 and cost<=target and crossing is not None and crossing<=cap
        row.update(valid=True,cost=cost,native_cost=float(m[2]),audit_relative_error=relative,native_seconds=float(m[3]),
          outers=int(m[1]),accepts=int(count[1]),rejects=int(count[2]),matvecs=int(count[3]),negcurv=int(count[4]),
          score_init=float(curves[0]['cost']),hit=hit,target_seconds=crossing if hit else None,
          cap_hit='MAX_SECONDS' in text or int(m[1])>=600,stop_ftol='converged (OCA_FTOL:' in text,
          mean_matvecs_per_outer=int(count[3])/max(1,int(m[1])))
        raw=folder/'endpoint.state';gz=folder/'endpoint.state.gz';rawhash=sha(raw)
        with raw.open('rb') as src,gzip.open(gz,'wb',compresslevel=1) as dst:shutil.copyfileobj(src,dst)
        with gzip.open(gz,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==rawhash
        row['state']=dict(sha256=rawhash,compressed_sha256=sha(gz),bytes=raw.stat().st_size)
        raw.unlink() # This run's export only, after verified lossless compression.
    except Exception as e:row['error']=str(e)
    write(folder/'result.json',row)
    print('DONE',scene,arm,rep,'valid',row['valid'],'cost',row.get('cost'),'s',row.get('native_seconds'),'hit',row.get('hit'),flush=True)
    assert row['valid'],row
    return row
