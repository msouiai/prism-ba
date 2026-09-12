#!/usr/bin/env python3
"""One separately registered native arm, identical-target comparisons."""
import argparse,json,re,subprocess
from grid_common import P,F,run,write,sha
CONFIGS={
 'stcg':dict(binary='steihaug/build/prism-stcg',manifest='steihaug/build_manifest.json',flag='OCA_STEIHAUG',trace='OCA_STCG_ATTEMPTS'),
 'pi':dict(binary='pi_radius/build/prism-pi',manifest='pi_radius/build/manifest.json',flag='OCA_PI_RADIUS',trace='OCA_STCG_ATTEMPTS'),
 'frontload':dict(binary='frontload/build/prism-frontload',manifest='frontload/build_manifest.json',flag='OCA_FRONTLOAD',trace='OCA_STCG_ATTEMPTS',protocol='PROTOCOL_05_NATIVE.md'),
 'opening_unclip':dict(binary='opening_unclip/build/prism-opening-unclip',manifest='opening_unclip/build_manifest.json',flag='OCA_OPEN_UNCLIP',trace='OCA_STCG_ATTEMPTS',protocol='PROTOCOL_05_UNCLIP.md'),
 'passenger':dict(binary='coarse/nonlinear_native/build/prism-passenger',manifest='coarse/nonlinear_native/build_manifest.json',flag='OCA_PASSENGER',trace='OCA_STCG_ATTEMPTS',protocol='PROTOCOL_09_NATIVE.md'),
 'soft_kick':dict(binary='soft_kick/build/prism-soft-kick',manifest='soft_kick/build_manifest.json',flag='OCA_SOFT_KICK',trace='OCA_STCG_ATTEMPTS',protocol='PROTOCOL_11.md'),
 'coarse':dict(binary='coarse/native/build/prism-coarse',manifest='coarse/native/build_manifest.json',flag='OCA_COARSE',trace='OCA_ATTEMPT_TRACE')}
def coarse_trace(folder,row):
    text=(folder/'stdout.log').read_text();rows=[];previous=None
    for line in re.findall(r'^ATTEMPT (.*)$',text,re.M):
        r={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)}
        r['retry_entry']=r['o']==previous;previous=r['o'];rows.append(r)
    total=sum(r['seconds'] for r in rows);retry=sum(r['seconds'] for r in rows if r['retry_entry']);failed=sum(r['seconds'] for r in rows if not r['accepted'])
    obj=dict(clock='host_steady_stdout_no_added_gpu_sync',rows=rows,totals=dict(attempts=len(rows),accepted=sum(int(r['accepted']) for r in rows),
      not_accepted=sum(not r['accepted'] for r in rows),curvature_cutoffs=row['negcurv'],cutoff_accepts=None,
      numeric_repairs=sum(int(r['numeric_retry']) for r in rows),pcg_iterations=sum(int(r['pcg_products']) for r in rows),
      matvecs=sum(int(r['products']) for r in rows),attempt_seconds=total,retry_entry_seconds=retry,not_accepted_seconds=failed,
      retry_entry_wall_fraction=retry/total if total else 0,not_accepted_wall_fraction=failed/total if total else 0,
      raw_retry_index_seconds=sum(r['seconds'] for r in rows if r['retry']>0)))
    write(folder/'attempts.json',obj);return obj
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
    registered_cells=list(proto[a.stage])
    if a.candidate in ('frontload','opening_unclip') and a.stage=='tail':
        extra_path='/workspace/bal/ladybug-1197.txt'
        extra=dict(scene='ladybug-1197',target=369997.000889023,cap=60,path=extra_path,input_sha256=sha(extra_path),cell='ladybug-1197')
        registration=P/(a.candidate+'-tail-extra.json')
        if registration.exists():assert json.loads(registration.read_text())==extra
        else:write(registration,extra)
        registered_cells.append(extra)
    protocol=P/c.get('protocol','PROTOCOL_NATIVE_PANEL.md')
    for rep in range(3 if a.stage=='practical' else 5):
        cells=registered_cells if rep%2==0 else list(reversed(registered_cells))
        for cell in cells:
            assert sha(cell['path'])==cell['input_sha256']
            for arm in (['off','on'] if rep%2==0 else ['on','off']):
                folder=P/'evidence'/a.candidate/a.stage/f"{cell['cell']}-{arm}-{rep}"
                flags={c['flag']:str(int(arm=='on')),c['trace']:'1' if a.candidate=='coarse' else str(folder/'attempts.json')}
                r=run(folder,cell['scene'],arm,rep,binary,flags,protocol,cell['target'],cell['cap'],cell['path'],build_manifest=bm)
                r['cell']=cell['cell'];r['candidate']=a.candidate;r['stage']=a.stage
                trace=coarse_trace(folder,r) if a.candidate=='coarse' else json.loads((folder/'attempts.json').read_text())
                totals=trace['totals'];assert totals['accepted']==r['accepts'],(totals,r)
                assert totals['matvecs']==r['matvecs'],(totals,r)
                r['attempts']=totals;r['pcg_per_outer']=totals['pcg_iterations']/max(1,r['outers'])
                r['retry_fraction_native']=totals['retry_entry_seconds']/r['native_seconds']
                r['failed_fraction_native']=totals['not_accepted_seconds']/r['native_seconds']
                write(folder/'result.json',r);rows.append(r)
                write(P/(a.candidate+'-'+a.stage+'-results.json'),rows)
    for cell in registered_cells:
        ss=[r['score_init'] for r in rows if r['cell']==cell['cell']]
        assert max(ss)-min(ss)<=1e-9*max(1,max(ss)),(cell,ss)
    print('COMPLETE',a.candidate,a.stage,len(rows),flush=True)
if __name__=='__main__':main()
