"""Pre-registered native analytic geodesic campaign, serial paired cohorts."""
import argparse,json,re,statistics,subprocess
import run_native as N
P=N.P;G=N.G
N.ARMS={'off':{},'geodesic':{'OCA_GEODESIC':'1'}}
def register():
    subprocess.run(['python3',str(G.F/'build.py'),'--check-only'],check=True)
    bm=json.loads((P/'geodesic_native_manifest.json').read_text());audit=json.loads((P/'geodesic_native_validation/audit.json').read_text())
    assert audit['passed'] and audit['memcheck_passed']
    assert bm['binary_sha256']==G.sha(P/'build/prism-geodesic-native')
    assert all(G.sha(p)==h for p,h in bm['sources'].items())
    assert bm['source_sha256']==G.sha(P/'build/prism_geodesic_native.cu') and bm['protocol_sha256']==G.sha(P/'GEODESIC_NATIVE_PROTOCOL.md')
    prior=json.loads((P/'registration.json').read_text())
    obj=dict(build_manifest=bm,protocol=str(P/'GEODESIC_NATIVE_PROTOCOL.md'),binary=str(P/'build/prism-geodesic-native'),
      arms=N.ARMS,cells=prior['cells'],native_panel=prior['native_panel'],independent_validation=audit)
    path=P/'geodesic_registration.json'
    if path.exists():assert json.loads(path.read_text())==obj
    else:G.write(path,obj)
    return obj
def run(reg,stage,cell,arm,rep):
    row=N.run(reg,stage,cell,arm,rep);folder=P/row['source'];text=(folder/'stdout.log').read_text();events=[]
    for line in re.findall(r'^GEODESIC (.*)$',text,re.M):events.append({k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)})
    if arm=='geodesic':
        tr=json.loads((folder/'attempts.json').read_text())['rows']
        row['geodesic']=dict(calls=len(events),certified=sum(x['certified'] for x in events),cutoff=sum(x['cutoff'] for x in events),
           admitted=sum(x['admitted'] for x in events),candidate_wins=sum(x['won'] for x in events),
           won_and_outer_accepted=sum(x['won'] and tr[int(x['attempt'])]['accepted'] for x in events),
           seconds=sum(x['seconds'] for x in events),products=sum(x['products'] for x in events),pcg_iterations=sum(x['cg'] for x in events))
    else:assert not events
    G.write(folder/'result.json',row);return row
def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['compatibility','tail','practical']);a=ap.parse_args();reg=register();rows=[]
    if a.stage=='compatibility':
        for rep in range(3):
            for arm in (['original','off'] if rep%2==0 else ['off','original']):rows.append(run(reg,'geodesic-compatibility',reg['cells']['dubrovnik-88'],arm,rep))
        off=statistics.median(r['cost'] for r in rows if r['arm']=='off');orig=statistics.median(r['cost'] for r in rows if r['arm']=='original');assert abs(off/orig-1)<.0015
    else:
        assert len(json.loads((P/'geodesic-compatibility-results.json').read_text()))==6
        if a.stage=='practical':
            tail=json.loads((P/'geodesic-tail-results.json').read_text());assert len(tail)==20
            geo=[r['geodesic'] for r in tail if r['arm']=='geodesic']
            ratio=sum(x['admitted'] for x in geo)/sum(x['calls'] for x in geo)
            if ratio<.2:
                G.write(P/'geodesic_practical_kill.json',dict(killed=True,admission_fraction=ratio,reason='More than80% optional corrections discarded.'))
                print('KILLED PRACTICAL',ratio,flush=True);return
        cells=[reg['cells'][s] for s in ['venice-52','final-3068']] if a.stage=='tail' else reg['native_panel']['practical']
        for rep in range(5 if a.stage=='tail' else 3):
            for cell in (cells if rep%2==0 else list(reversed(cells))):
                for arm in (list(N.ARMS) if rep%2==0 else list(reversed(N.ARMS))):
                    rows.append(run(reg,'geodesic-'+a.stage,cell,arm,rep));G.write(P/('geodesic-'+a.stage+'-results.json'),rows)
    G.write(P/('geodesic-'+a.stage+'-results.json'),rows);print('COMPLETE GEODESIC',a.stage,len(rows),flush=True)
if __name__=='__main__':main()
