"""Registered serial W3 runs; fresh cohorts and independently audited endpoints."""
from pathlib import Path
import argparse, importlib.util, json, os, re, statistics, subprocess, sys, tempfile
P=Path(__file__).resolve().parent;C=P.parent/'eta2_research_20260912'
sys.path.insert(0,str(C))
import grid_common as G
G.P=P
ARMS={
 'off':{},'lambda1':{},'lambda10':{},'lambda100':{},
 'no_interior':{'OCA_W2_INTERIOR':'1'},
 'opening_no_interior':{'OCA_W2_INTERIOR':'2'},
 'jump16':{'OCA_W3_JUMP':'1'},
 'forcing':{'OCA_W3_FORCE':'1'},
 'forcing_reject':{'OCA_W3_FORCE':'1','OCA_W3_UNCLIP':'1'},
 'accurate_reference':{'OCA_FRONTLOAD':'1'}}

def verify():
    subprocess.run(['python3',str(G.F/'build.py'),'--check-only'],check=True)
    bm=json.loads((P/'build_manifest.json').read_text())
    assert bm['binary_sha256']==G.sha(P/'build/prism-wave2')
    assert bm['source_sha256']==G.sha(P/'build/prism_wave2.cu')
    assert bm['frozen_source_sha256']==G.sha(G.F/'source/prism_eta2.cu')
    assert bm['protocol_sha256']==G.sha(P/'PROTOCOL.md')
    assert all(G.sha(p)==h for p,h in bm['local_headers_and_builders'].items())
    return bm

def register():
    bm=verify();cells={}
    for scene,target in [('venice-52',243740.27),('final-3068',1744796.9841897595),('dubrovnik-88',0)]:
        p=Path('/workspace/bal')/(scene+'.txt');cells[scene]=dict(scene=scene,path=str(p),target=target,input_sha256=G.sha(p),cap=60)
    obj=dict(build_manifest=bm,protocol_sha256=G.sha(P/'PROTOCOL.md'),arms=ARMS,cells=cells,
             initial_lambdas={'lambda1':1,'lambda10':10,'lambda100':100},
             native_panel=json.loads((C/'native-panel.json').read_text()),n=5,
             instrumentation='All derived runs charge gauge telemetry; speed is for instrumented arms until separate timing confirmation.')
    f=P/'registration.json'
    if f.exists():assert json.loads(f.read_text())==obj
    else:G.write(f,obj)
    return obj

def run(reg,stage,cell,arm,rep):
    scene=cell['scene'];cid=cell.get('cell',scene)
    folder=P/'evidence'/stage/f'{cid}-{arm}-{rep}'
    if (folder/'result.json').exists():return json.loads((folder/'result.json').read_text())
    assert G.sha(cell['path'])==cell['input_sha256']
    folder.mkdir(parents=True,exist_ok=True)
    flags=dict(ARMS.get(arm,{}))
    binary=G.ORIGINAL if arm=='original' else P/'build/prism-wave2'
    if arm!='original':flags.update(OCA_STCG_ATTEMPTS=str(folder/'attempts.json'),OCA_WAVE_TRACE=str(folder/'wave.json'))
    cli=list(G.CHAMP['cli'])
    if arm.startswith('lambda'):cli[cli.index('--lam0')+1]=str(reg['initial_lambdas'][arm])
    fd,raw=tempfile.mkstemp(prefix='eta2-wave2-',suffix='.state',dir='/dev/shm');os.close(fd)
    temporary=Path(raw);(folder/'endpoint.state').symlink_to(temporary)
    G.write(folder/'staging.json',dict(raw_path=raw,policy='RAM duplicate removed only after verified durable gzip'))
    row=G.run(folder,scene,arm,rep,binary,flags,P/'PROTOCOL.md',cell['target'],cell['cap'],cell['path'],cli,reg['build_manifest'])
    assert G.sha(temporary)==row['state']['sha256'];temporary.unlink()
    text=(folder/'stdout.log').read_text()
    row['stop_reason']='target' if row['hit'] else ('time_cap' if 'BUDGET stop=' in text else ('outer_cap' if row['outers']>=600 else ('ftol' if row['stop_ftol'] else 'other')))
    row['cell']=cid;row['stage']=stage
    if arm!='original':
        tr=json.loads((folder/'attempts.json').read_text());w=json.loads((folder/'wave.json').read_text())
        t=tr['totals'];assert t['accepted']==row['accepts'] and t['matvecs']==row['matvecs']
        assert len(w)==len(tr['rows']) and sum(x['accepted'] for x in w)==row['accepts']
        assert sum(x['pcg_iterations'] for x in w)==t['pcg_iterations']
        row['attempts']=t;row['pcg_per_outer']=t['pcg_iterations']/max(1,row['outers'])
        row['retry_fraction_native']=t['retry_entry_seconds']/row['native_seconds']
        row['gauge_seconds']=sum(x['gauge_seconds'] for x in w)
        row['max_raw_radius_ratio']=max((x['raw_radius_ratio'] for x in w if x['raw_radius_ratio'] is not None),default=None)
        # Every finite, positive-radius solve must carry composition telemetry.
        assert all(x['gauge_fraction'] is not None and -.000001<=x['gauge_fraction']<=1.000001 for x in w if x['observed'])
        assert all(abs(x['eta']-.05)<1e-12 for x in w if x['accepts_before']<3 and arm in ('forcing','forcing_reject','accurate_reference'))
    G.write(folder/'result.json',row);return row

def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['register','compatibility','venice','followup']);a=ap.parse_args()
    reg=register()
    if a.stage=='register':return
    rows=[]
    if a.stage=='compatibility':
        for rep in range(3):
            for arm in (['original','off'] if rep%2==0 else ['off','original']):
                rows.append(run(reg,a.stage,reg['cells']['dubrovnik-88'],arm,rep))
        med={arm:statistics.median(r['cost'] for r in rows if r['arm']==arm) for arm in ['original','off']}
        assert abs(med['off']/med['original']-1)<.0015,med
    elif a.stage=='venice':
        comp=json.loads((P/'compatibility-results.json').read_text());assert len(comp)==6
        for rep in range(5):
            order=list(ARMS) if rep%2==0 else list(reversed(ARMS))
            for arm in order:
                rows.append(run(reg,a.stage,reg['cells']['venice-52'],arm,rep))
                G.write(P/(a.stage+'-results.json'),rows)
    else:
        prior=json.loads((P/'venice-results.json').read_text());assert len(prior)==50
        survivors=[arm for arm in ARMS if arm!='off' and sum(r['hit'] for r in prior if r['arm']==arm)>=4]
        for rep in range(5):
            for arm in (['off']+survivors if rep%2==0 else list(reversed(['off']+survivors))):
                rows.append(run(reg,'final',reg['cells']['final-3068'],arm,rep));G.write(P/'final-results.json',rows)
        rows=[]
        for rep in range(3):
            for cell in reg['native_panel']['practical']:
                for arm in (['off']+survivors if rep%2==0 else list(reversed(['off']+survivors))):
                    rows.append(run(reg,'practical',cell,arm,rep));G.write(P/'practical-results.json',rows)
        return
    G.write(P/(a.stage+'-results.json'),rows)
    print('COMPLETE',a.stage,len(rows),flush=True)
if __name__=='__main__':main()
