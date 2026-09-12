from pathlib import Path
import csv,fcntl,gzip,hashlib,json,os,shutil,subprocess
from audit_geodesic import run as audit
P=Path(__file__).resolve().parent
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(scene,rep):
    out=P/'geodesic_analytic'/f'{scene}-{rep}';out.mkdir(parents=True,exist_ok=True)
    bm=json.loads((P/'geodesic_analytic_manifest.json').read_text());binary=P/'build/prism-geodesic-analytic';assert sha(binary)==bm['binary_sha256']
    if not (out/'result.json').exists():
        parent=json.loads((P/'witness_proposals'/f'{scene}-{rep}'/'manifest.json').read_text());flags=dict(parent['flags'],OCA_W2_OUTPUT=str(out));cmd=[str(binary),*parent['command'][1:]]
        env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','MF_DEBUG'))};env.update(flags)
        (out/'manifest.json').write_text(json.dumps(dict(command=cmd,flags=flags,build_manifest=bm,parent=parent),indent=2)+'\n')
        print('RUN ANALYTIC',scene,rep,flush=True)
        with open('/tmp/prism_gpu.lock','w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            with (out/'stdout.log').open('w') as log,(out/'stderr.log').open('w') as err:subprocess.run(cmd,env=env,stdout=log,stderr=err,timeout=3600,check=True)
        assert 'W2_WITNESS_COMPLETE' in (out/'stdout.log').read_text()
        files={}
        for p in out.glob('*.step'):
            rawhash=sha(p);gz=Path(str(p)+'.gz')
            with p.open('rb') as src,gzip.open(gz,'wb',compresslevel=1) as dst:shutil.copyfileobj(src,dst)
            with gzip.open(gz,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==rawhash
            files[p.name]=dict(raw_sha256=rawhash,gzip_sha256=sha(gz));p.unlink()
        rows=list(csv.DictReader((out/'directions.csv').open()))
        (out/'result.json').write_text(json.dumps(dict(scene=scene,rep=rep,rows=rows,files=files),indent=2)+'\n')
    audit(scene,rep,out,True)
if __name__=='__main__':
    for scene,rep in [('venice-52',0)]+[('final-3068',r) for r in (0,5,6)]:run(scene,rep)
