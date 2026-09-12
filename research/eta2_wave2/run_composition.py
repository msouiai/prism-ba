"""Full W1 snapshots with lossless archives; no scored speed comparisons."""
from pathlib import Path
import argparse,fcntl,gzip,hashlib,json,os,re,shutil,subprocess,tarfile,tempfile,time
import numpy as np
import witness_composition as W
import lossless_float_archive as FA
P=W.P;C=W.C;D=W.D;CHART=W.CHART
F=P.parent/'eta2_champion';T=P.parent/'eta2_track_damping'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def analyse(path,ci,pi,uv):
    cam,X,meta=W.load_capture_state(path);nc,np_=len(cam.R),len(X)
    E=D.read_array(path/'E.f64',(nc,9));cd=D.read_array(path/'Cdiag.f64',(np_,3));raw=-D.read_array(path/'eta2_raw_scaled.f64',(nc,9))
    G,Q,bases=W.subspaces(cam.R,cam.t,E);parts,norms=W.decompose(raw,G,Q)
    chart=CHART.make_chart(X,cam,'euclidean');res,Jc,Jp,Y=CHART.observation_jacobians(cam,chart.H,chart.T,ci,pi,uv)
    diag=np.maximum(cd,.001*np.maximum(cd.mean(axis=1),1e-32)[:,None])
    counts=np.bincount(pi,minlength=np_);multipliers=np.where(counts>=6,.3,1) if meta['static_replay'] else np.ones(np_)
    _,Ri,_=W.point_qr(Jp,pi,meta['tau']*multipliers[:,None]*diag)
    gp=W.sum_tracks(np.einsum('nri,nr->ni',Jp,res),pi,np_);offset=-W.point_inverse(Ri,gp)
    jd=[]
    for part in parts:
        dc=(E.ravel()*part).reshape(nc,9);yc=np.einsum('nri,ni->nr',Jc,dc[ci])
        cross=W.sum_tracks(np.einsum('nri,nr->ni',Jp,yc),pi,np_);dp=-W.point_inverse(Ri,cross)
        jd.append(yc+np.einsum('nri,ni->nr',Jp,dp[pi]))
    jd.append(np.einsum('nri,ni->nr',Jp,offset[pi]));total=sum(jd)
    pred=-float(np.sum(res*total+.5*total*total,dtype=np.longdouble))
    allocation=[-float(np.sum(res*v+.5*v*total,dtype=np.longdouble)) for v in jd]
    assert abs(sum(allocation)-pred)<1e-8*max(1,abs(pred))
    score=float(.5*np.sum(res*res,dtype=np.longdouble));assert abs(score-meta['cost'])/max(1,score)<1e-8
    return dict(metadata=meta,score_init=score,bases=bases,**norms,
        raw_radius_ratio=norms['norm']/meta['radius'] if meta['radius']>0 else None,
        prediction=pred,model_decrease_allocation=dict(zip(['gauge','local_cluster','remainder','point_offset'],allocation)))

def one(stage,arm,rep,old=None):
    folder=P/'composition'/f'{stage}-{arm}-{rep}';folder.mkdir(parents=True,exist_ok=True)
    if (folder/'result.json').exists():return json.loads((folder/'result.json').read_text())
    champ=json.loads((F/'champion.json').read_text());bm=json.loads((P/'composition_manifest.json').read_text())
    assert sha(P/'build/prism-composition')==bm['binary_sha256'];assert all(sha(p)==h for p,h in bm['sources'].items())
    recovery=None
    if (folder/'manifest.json').exists() and (folder/'decomposition.json').exists():
        recovery=json.loads((folder/'manifest.json').read_text());scratch=Path(recovery['scratch']);assert scratch.is_dir()
    else:scratch=Path(tempfile.mkdtemp(prefix='eta2-w1-',dir='/dev/shm'))
    capture=scratch/'captures';capture.mkdir(exist_ok=True)
    flags=dict(champ['flags'],OCA_WAVE_TRACE=str(folder/'wave.json'),OCA_STCG_ATTEMPTS=str(folder/'attempts.json'),OCA_W1_DIR=str(capture),OCA_MAX_SECONDS='300')
    cli=list(champ['cli']);provenance={}
    if old:
        original=T/old['source'];raw=scratch/'initial.state'
        with gzip.open(original/'endpoint.state.gz','rb') as src,raw.open('wb') as out:shutil.copyfileobj(src,out)
        assert sha(raw)==old['state']['sha256']
        diag=json.loads((T/'tail_diagnostics.json').read_text())['venice-52']['runs'];last=next(r for r in diag if r['rep']==rep and r['arm']=='on')
        flags.update(OCA_W1_STATE=str(raw),OCA_W1_RADIUS=str(last['last_radius']),OCA_W1_STATIC_REPLAY='1',OCA_W1_STOP='1')
        cli[cli.index('--lam0')+1]=str(last['last_lambda']);provenance=dict(endpoint=old,controller=last,fresh_forcing_history=True)
    else:
        flags['OCA_TARGET_COST']='243740.27'
        if arm=='accurate':flags['OCA_FRONTLOAD']='1'
    env={k:v for k,v in os.environ.items() if not k.startswith('OCA_')};env.update(flags)
    command=[str(P/'build/prism-composition'),'--problem','/workspace/bal/venice-52.txt',*cli,'--csv',str(folder/'curve.csv')]
    if not recovery:write(folder/'manifest.json',dict(command=command,flags=flags,build_manifest=bm,input_sha256=sha('/workspace/bal/venice-52.txt'),provenance=provenance,
       protocol_sha256=sha(P/'COMPOSITION_COMPLETION_PROTOCOL.md'),scratch=str(scratch)))
    print('W1 RUN',stage,arm,rep,flush=True);start=time.perf_counter()
    if not recovery:
        with open('/tmp/prism_gpu.lock','w') as lock,(folder/'stdout.log').open('w') as out,(folder/'stderr.log').open('w') as err:
            fcntl.flock(lock,fcntl.LOCK_EX);subprocess.run(command,env=env,stdout=out,stderr=err,check=True,timeout=900)
    # Copy the input state into the same verified archive, so no unique raw input is lost.
    if old:shutil.copy2(scratch/'initial.state',capture/'initial.state')
    ci,pi,uv,_=CHART.load_observations('/workspace/bal/venice-52.txt');rows=[]
    if recovery:rows=json.loads((folder/'decomposition.json').read_text())
    else:
        for case in sorted((p for p in capture.iterdir() if p.is_dir()),key=lambda p:int(p.name)):
            row=analyse(case,ci,pi,uv);row['attempt']=int(case.name);rows.append(row)
    waves=json.loads((folder/'wave.json').read_text());assert len(rows)==len(waves)
    for row,wave in zip(rows,waves):
        assert abs(row['gauge_fraction']-wave['gauge_fraction'])<1e-5
        row.update(accepted=wave['accepted'],rho=wave['rho'],numeric_repair=wave['numeric_repair'])
    write(folder/'decomposition.json',rows)
    files={str(p.relative_to(capture)):p for p in capture.rglob('*') if p.is_file()}
    keep={rows[0]['attempt'],rows[-1]['attempt'],max(rows,key=lambda r:r['raw_radius_ratio'] or 0)['attempt']}
    allhashes={name:sha(path) for name,path in files.items()}
    files={name:p for name,p in files.items() if p.name not in ('X_state.f64','Cdiag.f64') or int(p.parent.name) in keep}
    write(folder/'retention.json',dict(policy='SNAPSHOT_RETENTION_ADDENDUM.md',full_point_attempts=sorted(keep),source_member_sha256=allhashes))
    archive=folder/'snapshots.xor.tar.xz'
    hashes=FA.pack(archive,files);FA.verify(archive,hashes)
    write(folder/'archive.json',dict(path=str(archive),sha256=sha(archive),member_sha256=hashes,verified=True,decoder='lossless_float_archive.py'))
    # Only the just-created RAM copy; every byte is now in the verified archive.
    shutil.rmtree(scratch)
    result=dict(stage=stage,arm=arm,rep=rep,attempts=len(rows),diagnostic_seconds=time.perf_counter()-start,
      maximum_raw_radius_ratio=max((r['raw_radius_ratio'] for r in rows if r['raw_radius_ratio'] is not None),default=None),
      maximum_gauge_fraction=max(r['gauge_fraction'] for r in rows),archive_sha256=sha(archive),
      score_init=rows[0]['score_init'],next_solve_reconstruction=bool(old))
    write(folder/'result.json',result);print('W1 DONE',result,flush=True);return result
def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['trajectory','terminal']);a=ap.parse_args();D.verify_baseline();rows=[]
    if a.stage=='trajectory':
        for rep in range(3):
            for arm in (['off','accurate'] if rep%2==0 else ['accurate','off']):rows.append(one(a.stage,arm,rep))
    else:
        old=[r for r in json.loads((T/'tail-results.json').read_text()) if r['scene']=='venice-52' and r['arm']=='on'];assert len(old)==5
        for repeat in range(3):
            for r in sorted(old,key=lambda r:r['rep']):rows.append(one(a.stage,'static-'+str(repeat),r['rep'],r))
    write(P/('composition-'+a.stage+'-results.json'),rows)
if __name__=='__main__':main()
