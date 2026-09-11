import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import fcntl,hashlib,json,subprocess,time,shutil
import numpy as np
from paths import ROOT,write_json

OUT=ROOT/'evidence';CAPTURE=ROOT.parent/'schur_physics_control'
RAW=__import__('pathlib').Path('/workspace/prism-schur-physics')
CASES=[('muell-gba146',12,11),('ladybug-598',8,7),('final-1936',0,None)]
binary=ROOT/'build/residual-fixed';manifest=[];rows=[]
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
for scene,outer,prior in CASES:
    for k in [outer]+([] if prior is None else [prior]):
        d=RAW/f'{scene}-o{k}';m=json.loads((d/'capture_manifest.json').read_text());files={}
        for name in ['dimensions.txt','W','U','R','E','b','cams','points','offsets']:
            p=d/name;digest=sha(p)
            assert digest==m['files'][name]['sha256'],p
            files[name]={'sha256':digest,'bytes':p.stat().st_size}
        manifest.append({'path':str(d),'files':files})
write_json(ROOT/'schur_inputs.json',manifest)
with open('/tmp/prism_gpu.lock','w') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    for scene,outer,prior in CASES:
        cmd=[str(binary),str(RAW/f'{scene}-o{outer}')]
        if prior is not None:cmd.append(str(RAW/f'{scene}-o{prior}'))
        start=time.perf_counter()
        log=OUT/f'schur-{scene}.log'
        with log.open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
        for line in log.read_text().splitlines():
            if not line.startswith('ASTRA_FIXED '):continue
            fields=dict(x.split('=',1) for x in line.split()[1:])
            row={k:(v if k=='arm' else float(v)) for k,v in fields.items()}
            rows.append({'scene':scene,'outer':outer,'prior':prior,**row})
        write_json(ROOT/'schur_results.json',{'rows':rows})
        print('done',scene,'process_seconds',time.perf_counter()-start,flush=True)
summary=[]
for scene,_,_ in CASES:
    base=[r for r in rows if r['scene']==scene and r['arm']=='plain']
    for arm in ['plain','old2','old4','theta2','theta4','energy2','energy4']:
        a=[r for r in rows if r['scene']==scene and r['arm']==arm]
        assert len(a)==3
        summary.append({'scene':scene,'arm':arm,'runs':len(a),'hits':sum(r['hit'] for r in a),
            'speedup':np.median([r['wall_ms'] for r in base])/np.median([r['wall_ms'] for r in a]) if all(r['hit'] for r in a+base) else None,
            **{k:np.median([r[k] for r in a]) for k in ['wall_ms','setup_ms','solve_event_ms','iterations','products','refresh','true_relative','eta','used','prior_iterations']}})
write_json(ROOT/'schur_summary.json',summary)
print(summary,flush=True)
