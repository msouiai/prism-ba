"""W8 matched cohorts plus the registered five-stop-witness diagnostic."""
import argparse,json,re,statistics,subprocess
import run_native as N
P=N.P;G=N.G
N.ARMS={'off':{},'plateau':{'OCA_PLATEAU':'1'}}
def register():
    subprocess.run(['python3',str(G.F/'build.py'),'--check-only'],check=True)
    bm=json.loads((P/'plateau_manifest.json').read_text());assert bm['binary_sha256']==G.sha(P/'build/prism-plateau')
    assert all(G.sha(p)==h for p,h in bm['sources'].items())
    assert bm['source_sha256']==G.sha(P/'build/prism_plateau.cu') and bm['protocol_sha256']==G.sha(P/'PLATEAU_PROTOCOL.md')
    prior=json.loads((P/'registration.json').read_text())
    obj=dict(build_manifest=bm,protocol=str(P/'PLATEAU_PROTOCOL.md'),binary=str(P/'build/prism-plateau'),arms=N.ARMS,cells=prior['cells'],native_panel=prior['native_panel'])
    f=P/'plateau_registration.json'
    if f.exists():assert json.loads(f.read_text())==obj
    else:G.write(f,obj)
    return obj
def run(reg,stage,cell,arm,rep):
    row=N.run(reg,stage,cell,arm,rep);folder=P/row['source'];text=(folder/'stdout.log').read_text()
    def parse(tag):return [{k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',s)} for s in re.findall('^'+tag+r' (.*)$',text,re.M)]
    boundary=parse('W8_BOUNDARY');roots=parse('W8_ROOT');progress=parse('W8_PROGRESS');assert len(boundary)<=1
    if arm!='plateau':assert not boundary and not roots and not progress
    if boundary:
        assert boundary[0]['cost']>row['target']
        tr=json.loads((folder/'attempts.json').read_text())['rows'];ids={int(x['attempt']) for x in roots};assert all(not tr[i]['accepted'] for i in ids)
        # Exactly one root outer and at most two geodesic outers, unless target ends earlier.
        assert sum(x['phase']==1 for x in progress)<=1 and sum(x['phase']==2 for x in progress)<=2
        row['plateau']=dict(boundary=boundary[0],root_adjustments=len(roots),root_scope_seconds=sum(tr[i]['seconds'] for i in ids),
          extra_seconds=row['native_seconds']-boundary[0]['seconds'],progress=progress,resumed=bool(parse('W8_RESUME')),exhausted=bool(parse('W8_EXHAUSTED')),
          rescued=bool(row['hit']),endpoint_relative_progress=(boundary[0]['cost']-row['cost'])/boundary[0]['cost'])
    else:row['plateau']=None
    G.write(folder/'result.json',row);return row
def main():
    a=argparse.ArgumentParser();a.add_argument('stage',choices=['compatibility','tail','witnesses','practical']);stage=a.parse_args().stage;reg=register();rows=[]
    if stage=='compatibility':
        for rep in range(3):
            for arm in (['original','off'] if rep%2==0 else ['off','original']):rows.append(run(reg,'plateau-compatibility',reg['cells']['dubrovnik-88'],arm,rep))
        assert abs(statistics.median(r['cost'] for r in rows if r['arm']=='off')/statistics.median(r['cost'] for r in rows if r['arm']=='original')-1)<.0015
    else:
        assert len(json.loads((P/'plateau-compatibility-results.json').read_text()))==6
        if stage=='witnesses':
            tail=json.loads((P/'plateau-tail-results.json').read_text());rows=[r for r in tail if r['scene']=='final-3068' and r['arm']=='plateau'];assert len(rows)==5
            rep=5
            while sum(r['plateau'] is not None for r in rows)<5 and rep<30:
                rows.append(run(reg,'plateau-extra',reg['cells']['final-3068'],'plateau',rep));G.write(P/'plateau-witnesses-results.json',rows);rep+=1
            selected=[r for r in rows if r['plateau']][:5]
            decision=dict(total_runs=len(rows),all_hits=sum(r['hit'] for r in rows),witnesses=len(selected),rescued=sum(r['hit'] for r in selected),killed=len(selected)==5 and not any(r['hit'] for r in selected),
               note='Selected stop witnesses are conditional diagnostics; the complete denominator above retains all fast hits.')
            G.write(P/'plateau-witness-decision.json',decision);print('W8 DECISION',decision,flush=True)
        else:
            if stage=='practical':
                d=json.loads((P/'plateau-witness-decision.json').read_text())
                if d['killed']:print('W8 PRACTICAL KILLED',flush=True);return
            cells=[reg['cells'][s] for s in ['venice-52','final-3068']] if stage=='tail' else reg['native_panel']['practical']
            for rep in range(5 if stage=='tail' else 3):
                for cell in (cells if rep%2==0 else list(reversed(cells))):
                    for arm in (list(N.ARMS) if rep%2==0 else list(reversed(N.ARMS))):
                        rows.append(run(reg,'plateau-'+stage,cell,arm,rep));G.write(P/('plateau-'+stage+'-results.json'),rows)
    G.write(P/('plateau-'+stage+'-results.json'),rows);print('COMPLETE PLATEAU',stage,len(rows),flush=True)
if __name__=='__main__':main()
