"""Verify and preserve the bounded point-rescue study without duplicating states."""
import hashlib
import json
import pathlib
import re
import shutil
import statistics

ROOT=pathlib.Path('/tmp/prism-lm-point-rescue')
DEST=pathlib.Path('/workspace/prism-lm-point-rescue')
GROUPS=('safe-screen','refine-screen','confirmation','caspar-pairs')


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while b:=f.read(8*1024*1024):h.update(b)
    return h.hexdigest()


def main():
    rows=[];locations={}
    for group in GROUPS:
        rr=json.loads((ROOT/group/'results.json').read_text())
        for r in rr:
            assert r['returncode']==0 and r['audit_error']<1e-7
            stem=ROOT/group/f'{r["scene"]}-{r["arm"]}-{r["rep"]}'
            state=stem.with_suffix('.state')
            assert sha(state)==r['state_sha256']
            locations[str(state.relative_to(ROOT))]=str(state)
            log=stem.with_suffix('.log').read_text()
            info={}
            m=re.search(r'LM_RESCUE summary calls=(\d+) wins=(\d+) seconds=(\S+)',log)
            if m:info=dict(rescue_calls=int(m[1]),provisional_rescues=int(m[2]),rescue_seconds=float(m[3]))
            accepted_rescues=0;pending=False;accepted_checks=0
            for line in log.splitlines():
                if line.startswith('LM_RESCUE o='):pending='won=1' in line
                if line.startswith('CLASSICAL_LM o='):
                    accepted_rescues+=int(pending and 'accept=1' in line);pending=False
                if line.startswith(('CLASSICAL_LM o=','CAMERA_TR o=')):
                    v={k:float(x) for k,x in re.findall(r'(\w+)=([^ ]+)',line)}
                    if v['accept']:
                        assert v['prediction']>0 and v['rho']>0
                        if line.startswith('CAMERA_TR'):
                            assert v['rho']>=.1-1e-14 and v['norm']<=v['radius']*(1+1e-8)
                        accepted_checks+=1
            if 'accepted_checks' in r:assert r['accepted_checks']==accepted_checks
            else:info['accepted_checks']=accepted_checks
            if m:info['accepted_rescues']=accepted_rescues
            rows.append(dict(group=group,**r,**info))
    assert len(rows)==78,len(rows)
    manifest=json.loads((ROOT/'build/manifest.json').read_text())
    for name,key in [('source.cu','source_sha256'),('prism-tr','binary_sha256')]:assert sha(ROOT/'build'/name)==manifest[key]
    for name,digest in manifest['headers_sha256'].items():assert sha(ROOT/'build/headers'/name)==digest
    assert sha(pathlib.Path('gpu/oca_cuda.cu'))=='0b7aac9b70523ce08d791e1a75c6c18a672cdfb29f28c6a3ab21c0bf5e786569'
    paused=json.loads(pathlib.Path('/workspace/prism-block-error/paused-verified.json').read_text())
    for job in paused:
        stat=pathlib.Path(f'/proc/{job["pid"]}/stat').read_text().split()
        assert stat[2]=='T' and stat[21]==str(job['start_ticks'])
    summary=[]
    for group in GROUPS:
        keys=dict.fromkeys((r['scene'],r['arm']) for r in rows if r['group']==group)
        for scene,arm in keys:
            rr=[r for r in rows if r['group']==group and r['scene']==scene and r['arm']==arm]
            times=[r['crossing'] for r in rr if r['hit']]
            summary.append(dict(group=group,scene=scene,arm=arm,runs=len(rr),hits=len(times),median=statistics.median(times) if len(times)==len(rr) else None,minimum=min(times) if times else None,maximum=max(times) if times else None))
    report=dict(runs=len(rows),hits=sum(r['hit'] for r in rows),native_seconds=sum(r['seconds'] for r in rows),maximum_audit_error=max(r['audit_error'] for r in rows),accepted_checks=sum(r.get('accepted_checks',0) for r in rows),paused_jobs_verified=len(paused),binary_sha256=manifest['binary_sha256'],rows=rows,summary=summary)
    (ROOT/'verification.json').write_text(json.dumps(report,indent=2))
    DEST.mkdir(exist_ok=True)
    for group in GROUPS:
        d=DEST/group;d.mkdir(exist_ok=True)
        for p in (ROOT/group).iterdir():
            if p.is_file() and p.suffix!='.state':shutil.copy2(p,d/p.name)
    shutil.copytree(ROOT/'build',DEST/'build',dirs_exist_ok=True)
    for name in ['verification.json','check-result-v3.json','check-result-v3.stderr','check-build.log','check-build-v2.log','check-build-v3.log','check-result.stderr']:
        shutil.copy2(ROOT/name,DEST/name)
    shutil.copy2(ROOT/'selected_config.json',DEST/'selected_config.json')
    (DEST/'endpoint_locations.json').write_text(json.dumps(locations,indent=2))
    d=DEST/'tools';d.mkdir(exist_ok=True)
    for name in ['build_lm_point_rescue.py','solver_novelty_ablation.py','point_rescue_caspar.py','check_point_refinement.cu','report_lm_point_rescue.py']:
        shutil.copy2(pathlib.Path('bench')/name,d/name)
    print(json.dumps({k:v for k,v in report.items() if k not in ('rows','summary')},indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
