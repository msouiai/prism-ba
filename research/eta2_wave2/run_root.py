from pathlib import Path
import argparse,json,re,statistics,subprocess
import run_native as N
P=N.P;G=N.G
N.ARMS={'off':{},'coupled':{'OCA_W2_ROOT':'1'},'frozen':{'OCA_W2_ROOT':'2'},'opening':{'OCA_W2_ROOT':'3'}}

def register():
    subprocess.run(['python3',str(G.F/'build.py'),'--check-only'],check=True)
    validation=json.loads((P/'root_validation_summary.json').read_text());assert validation['passed']
    bm=json.loads((P/'root_build_manifest.json').read_text());assert bm['binary_sha256']==G.sha(P/'build/prism-wave-root')
    assert all(G.sha(p)==h for p,h in bm['sources'].items())
    assert bm['source_sha256']==G.sha(P/'build/prism_wave_root.cu') and bm['protocol_sha256']==G.sha(P/'ROOT_NATIVE_PROTOCOL.md')
    prior=json.loads((P/'registration.json').read_text())
    obj=dict(build_manifest=bm,protocol=str(P/'ROOT_NATIVE_PROTOCOL.md'),protocol_sha256=G.sha(P/'ROOT_NATIVE_PROTOCOL.md'),binary=str(P/'build/prism-wave-root'),
        arms=N.ARMS,cells=prior['cells'],native_panel=prior['native_panel'],independent_validation=validation)
    f=P/'root_registration.json'
    if f.exists():assert json.loads(f.read_text())==obj
    else:G.write(f,obj)
    return obj

def run(reg,stage,cell,arm,rep):
    row=N.run(reg,stage,cell,arm,rep);folder=P/row['source'];text=(folder/'stdout.log').read_text()
    root=[]
    for line in re.findall(r'^W2_RESOLVE (.*)$',text,re.M):root.append({k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)})
    row['root_adjustments']=len(root);row['root_fallbacks']=len(re.findall(r'^W2_FALLBACK ',text,re.M))
    if arm!='original':
        tr=json.loads((folder/'attempts.json').read_text());waves=json.loads((folder/'wave.json').read_text());ids={int(x['attempt']) for x in root}
        assert len(ids)==len(root)
        assert all(not tr['rows'][i]['accepted'] for i in ids)
        row['root_solve_seconds']=sum(tr['rows'][i]['seconds'] for i in ids)
        row['root_products']=sum(tr['rows'][i]['matvecs'] for i in ids)
        row['root_scope_fraction_native']=row['root_solve_seconds']/row['native_seconds']
        # Scope leading up to a re-solve is root work, not a rejected nonlinear proposal.
        row['root_attempt_ids']=sorted(ids)
        if arm=='frozen':
            for outer in {r['outer'] for r in waves}:
                tau={r['tau'] for r in waves if r['outer']==outer};assert len(tau)==1,(outer,tau)
        if arm=='off':assert not root
    G.write(folder/'result.json',row);return row

def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['register','compatibility','tail','practical']);a=ap.parse_args();reg=register()
    if a.stage=='register':return
    rows=[]
    if a.stage=='compatibility':
        for rep in range(3):
            for arm in (['original','off'] if rep%2==0 else ['off','original']):rows.append(run(reg,'root-compatibility',reg['cells']['dubrovnik-88'],arm,rep))
        off=statistics.median(r['cost'] for r in rows if r['arm']=='off');orig=statistics.median(r['cost'] for r in rows if r['arm']=='original');assert abs(off/orig-1)<.0015
    else:
        assert len(json.loads((P/'root-compatibility-results.json').read_text()))==6
        cells=[reg['cells'][s] for s in ['venice-52','final-3068']] if a.stage=='tail' else reg['native_panel']['practical']
        for rep in range(5 if a.stage=='tail' else 3):
            for cell in (cells if rep%2==0 else list(reversed(cells))):
                for arm in (list(N.ARMS) if rep%2==0 else list(reversed(N.ARMS))):
                    rows.append(run(reg,'root-'+a.stage,cell,arm,rep));G.write(P/('root-'+a.stage+'-results.json'),rows)
    G.write(P/('root-'+a.stage+'-results.json'),rows);print('COMPLETE ROOT',a.stage,len(rows),flush=True)
if __name__=='__main__':main()
