from pathlib import Path
import csv,fcntl,gzip,hashlib,json,os,shutil,subprocess,sys,time
P=Path(__file__).resolve().parent;C=P.parent/'eta2_research_20260912';F=P.parent/'eta2_champion'
sys.path.insert(0,str(C/'coarse'))
from diagnostic import verify_baseline,read_metadata,sha256

def run(scene,rep,toy=False):
    source=C/('evidence/toy/toy-capture-1' if toy else f'evidence/collect/{scene}-capture-{rep}')
    problem=C/'build/toy.txt' if toy else Path('/workspace/bal')/(scene+'.txt')
    out=P/'witness_proposals'/('toy' if toy else f'{scene}-{rep}')
    if (out/'result.json').exists():return
    out.mkdir(parents=True,exist_ok=True);meta=read_metadata(source/'metadata.txt')
    bm=json.loads((P/'witness_build_manifest.json').read_text());binary=P/'build/prism-wave-witness'
    assert sha256(binary)==bm['binary_sha256'];assert sha256(P/'WITNESS_PROTOCOL.md')==bm['protocol_sha256']
    assert all(sha256(Path(p))==h for p,h in bm['inputs'].items())
    c=json.loads((F/'champion.json').read_text());flags=dict(c['flags'],OCA_W2_WITNESS=str(source),OCA_W2_OUTPUT=str(out),OCA_W2_RADIUS=str(meta['radius']))
    if scene=='final-3068' or (scene=='venice-52' and rep==0) or toy:flags['OCA_W2_GEODESIC']='1'
    cli=list(c['cli']);cli[cli.index('--lam0')+1]=str(meta['lambda']);cli[cli.index('--max_iter')+1]='1'
    cmd=[str(binary),'--problem',str(problem),*cli]
    env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};env.update(flags)
    manifest=dict(build_manifest=bm,input_sha256=sha256(problem),metadata=meta,flags=flags,command=cmd,
      capture_hashes={p.name:sha256(p) for p in source.iterdir() if p.suffix in ('.f64','.step') or p.name=='metadata.txt'})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    start=time.perf_counter();print('RUN',scene,rep,'toy',toy,flush=True)
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        with (out/'stdout.log').open('w') as log,(out/'stderr.log').open('w') as err:
            result=subprocess.run(cmd,env=env,stdout=log,stderr=err,timeout=3600)
    text=(out/'stdout.log').read_text();assert result.returncode==0 and 'W2_WITNESS_COMPLETE' in text,(result.returncode,text[-500:])
    rows=list(csv.DictReader((out/'directions.csv').open()))
    assert len(rows)==(16 if 'OCA_W2_GEODESIC' in flags else 13)
    files={}
    for p in out.glob('*.step'):
        rawhash=sha256(p);gz=Path(str(p)+'.gz')
        with p.open('rb') as src,gzip.open(gz,'wb',compresslevel=1) as dst:shutil.copyfileobj(src,dst)
        with gzip.open(gz,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==rawhash
        files[p.name]=dict(raw_sha256=rawhash,gzip_sha256=sha256(gz));p.unlink()
    answer=dict(scene=scene,rep=rep,rows=rows,seconds=time.perf_counter()-start,files=files)
    (out/'result.json').write_text(json.dumps(answer,indent=2)+'\n')
    for r in rows:
        if r['rep']=='0':print(scene,rep,r['arm'],'gain',r['decrease'],'rho',r['rho'],'cert',r['certified'],'guard',r['guard_ratio'],flush=True)

def main():
    verify_baseline();run('toy',0,True)
    for scene,rep in [('venice-52',i) for i in (0,1,2)]+[('final-3068',i) for i in (0,5,6)]+[('ladybug-1197',0)]:run(scene,rep)
if __name__=='__main__':main()
