#!/usr/bin/env python3
"""One separately registered native arm, identical-target comparisons."""
import argparse,json,subprocess
from grid_common import P,F,run,write,sha
CONFIGS={
 'stcg':dict(binary='steihaug/build/prism-stcg',manifest='steihaug/build_manifest.json',flag='OCA_STEIHAUG',trace='OCA_STCG_ATTEMPTS'),
 'pi':dict(binary='pi_radius/build/prism-pi',manifest='pi_radius/build/manifest.json',flag='OCA_PI_RADIUS',trace='OCA_STCG_ATTEMPTS')}
def panel():
    path=P/'native-panel.json'
    if path.exists():return json.loads(path.read_text())
    old=json.loads(open('/tmp/prism-speed-novelty/protocol.json').read());anchors=json.loads(open('/tmp/prism-speed-novelty/anchors.json').read())
    cells=[]
    for sc,anchor in anchors['anchors'].items():
        for mul in [1.005,1.01,1.02]:
            info=old['scenes'][sc];assert sha(info['path'])==info['input_sha256']
            cells.append(dict(scene=sc,multiplier=mul,target=anchor*mul,cap=old['selection']['native_caps'][sc],
              path=info['path'],input_sha256=info['input_sha256'],cell=sc+'-'+str(mul)))
    tails=[]
    for sc,target in [('venice-52',243740.27),('final-3068',1744796.9841897595)]:
        path0='/workspace/bal/'+sc+'.txt';tails.append(dict(scene=sc,target=target,cap=60,path=path0,input_sha256=sha(path0),cell=sc))
    obj=dict(practical=cells,tail=tails,protocol_sha256=sha(P/'PROTOCOL_NATIVE_PANEL.md'),
      source_protocol_sha256=sha('/tmp/prism-speed-novelty/protocol.json'),source_anchors_sha256=sha('/tmp/prism-speed-novelty/anchors.json'))
    write(path,obj);return obj
def main():
    ap=argparse.ArgumentParser();ap.add_argument('candidate',choices=CONFIGS);ap.add_argument('stage',choices=['register','practical','tail']);a=ap.parse_args()
    proto=panel()
    if a.stage=='register':print(json.dumps(proto,indent=2));return
    subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
    c=CONFIGS[a.candidate];binary=P/c['binary'];bm=json.loads((P/c['manifest']).read_text());assert sha(binary)==bm['binary_sha256']
    assert proto['protocol_sha256']==sha(P/'PROTOCOL_NATIVE_PANEL.md')
    rows=[]
    for rep in range(3 if a.stage=='practical' else 5):
        cells=proto[a.stage] if rep%2==0 else list(reversed(proto[a.stage]))
        for cell in cells:
            assert sha(cell['path'])==cell['input_sha256']
            for arm in (['off','on'] if rep%2==0 else ['on','off']):
                folder=P/'evidence'/a.candidate/a.stage/f"{cell['cell']}-{arm}-{rep}"
                flags={c['flag']:str(int(arm=='on')),c['trace']:str(folder/'attempts.json')}
                r=run(folder,cell['scene'],arm,rep,binary,flags,P/'PROTOCOL_NATIVE_PANEL.md',cell['target'],cell['cap'],cell['path'],build_manifest=bm)
                r['cell']=cell['cell'];r['candidate']=a.candidate;r['stage']=a.stage
                trace=json.loads((folder/'attempts.json').read_text())
                totals=trace['totals'];assert totals['accepted']==r['accepts'],(totals,r)
                assert totals['matvecs']==r['matvecs'],(totals,r)
                r['attempts']=totals;r['pcg_per_outer']=totals['pcg_iterations']/max(1,r['outers'])
                r['retry_fraction_native']=totals['retry_entry_seconds']/r['native_seconds']
                r['failed_fraction_native']=totals['not_accepted_seconds']/r['native_seconds']
                write(folder/'result.json',r);rows.append(r)
                write(P/(a.candidate+'-'+a.stage+'-results.json'),rows)
    for cell in proto[a.stage]:
        ss=[r['score_init'] for r in rows if r['cell']==cell['cell']]
        assert max(ss)-min(ss)<=1e-9*max(1,max(ss)),(cell,ss)
    print('COMPLETE',a.candidate,a.stage,len(rows),flush=True)
if __name__=='__main__':main()
