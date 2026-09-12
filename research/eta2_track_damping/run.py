#!/usr/bin/env python3
"""Bounded paired transfer screen; shared frozen evidence/audit implementation."""
from pathlib import Path
import argparse,fcntl,json,statistics,subprocess,sys
import numpy as np
P=Path(__file__).resolve().parent
C=P.parent/'eta2_research_20260912'
sys.path.insert(0,str(C))
import grid_common as G
G.P=P
def toy():
    path=P/'build/toy_mixed.txt'
    if path.exists():return path
    rng=np.random.default_rng(7341);nc=8;np_=60
    trans=np.column_stack((np.linspace(-1.5,1.5,nc),.2*np.sin(np.arange(nc)),np.zeros(nc)))
    X=rng.uniform([-1,-1,-8],[1,1,-4],(np_,3));rows=[]
    for j in range(np_):
        for i in range([2,4,8][j//20]):
            Y=X[j]+trans[i];uv=-800*Y[:2]/Y[2]+rng.normal(0,.2,2)
            rows.append([i,j,*uv])
    cams=np.column_stack((np.zeros((nc,3)),trans+rng.normal(0,.03,(nc,3)),np.full(nc,800.),np.zeros((nc,2))))
    init=X+rng.normal(0,.04,X.shape)
    with path.open('w') as f:
        f.write(f'{nc} {np_} {len(rows)}\n')
        for i,j,u,v in rows:f.write(f'{i} {j} {u:.17g} {v:.17g}\n')
        for v in np.r_[cams.ravel(),init.ravel()]:f.write(f'{v:.17g}\n')
    return path
def execute(scene,arm,rep,stage,target=0,problem=None):
    m=json.loads((P/'build_manifest.json').read_text())
    binary=G.ORIGINAL if arm=='original' else P/'build/prism-track-tau'
    assert G.sha(binary)==(G.CHAMP['binary_sha256'] if arm=='original' else m['binary_sha256'])
    folder=P/'evidence'/stage/f'{scene}-{arm}-{rep}'
    flags={} if arm=='original' else dict(OCA_TRACK_TAU=str(int(arm=='on')),OCA_STCG_ATTEMPTS=str(folder/'attempts.json'))
    cli=G.CHAMP['cli'].copy()
    if stage=='toy':cli[cli.index('--max_iter')+1]='8'
    r=G.run(folder,scene,arm,rep,binary,flags,P/'PROTOCOL.md',target,60,problem,cli,m if arm!='original' else None)
    r.update(stage=stage,cell=scene)
    if arm!='original':
        tr=json.loads((folder/'attempts.json').read_text())['totals']
        assert tr['accepted']==r['accepts'] and tr['matvecs']==r['matvecs']
        r.update(attempts=tr,pcg_per_outer=tr['pcg_iterations']/max(1,r['outers']),
                 retry_fraction_native=tr['retry_entry_seconds']/r['native_seconds'],
                 failed_fraction_native=tr['not_accepted_seconds']/r['native_seconds'])
        assert ('TRACK_TAU rule=' in (folder/'stdout.log').read_text()) == (arm=='on')
    G.write(folder/'result.json',r);return r
def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['toy','compatibility','tail']);a=ap.parse_args()
    subprocess.run(['python3',str(G.F/'build.py'),'--check-only'],check=True)
    rows=[]
    if a.stage=='toy':
        for scene,path in [('toy_thin',C/'build/toy.txt'),('toy_mixed',toy())]:
            for arm in ['off','on']:rows.append(execute(scene,arm,0,a.stage,problem=path))
        pair=[r for r in rows if r['scene']=='toy_thin']
        assert abs(pair[0]['cost']/pair[1]['cost']-1)<1e-10
    elif a.stage=='compatibility':
        for rep in range(3):
            for arm in (['original','off'] if rep%2==0 else ['off','original']):rows.append(execute('dubrovnik-88',arm,rep,a.stage))
        med={a:statistics.median(r['cost'] for r in rows if r['arm']==a) for a in ['original','off']}
        assert abs(med['off']/med['original']-1)<.0015
    else:
        assert json.loads((P/'factor_verification.json').read_text())['passed']
        assert len(json.loads((P/'compatibility-results.json').read_text()))==6
        for rep in range(5):
            scenes=[('venice-52',243740.27),('final-3068',1744796.9841897595)]
            for scene,target in (scenes if rep%2==0 else list(reversed(scenes))):
                for arm in (['off','on'] if rep%2==0 else ['on','off']):
                    rows.append(execute(scene,arm,rep,a.stage,target))
                    G.write(P/'tail-results.json',rows)
    for sc in {r['scene'] for r in rows}:
        v=[r['score_init'] for r in rows if r['scene']==sc]
        assert max(v)-min(v)<=1e-9*max(1,max(v))
    G.write(P/(a.stage+'-results.json'),rows)
    print('COMPLETE',a.stage,len(rows),flush=True)
if __name__=='__main__':main()
