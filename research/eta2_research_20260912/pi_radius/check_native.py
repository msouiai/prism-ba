#!/usr/bin/env python3
import json,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from grid_common import P,ORIGINAL,CHAMP,run,write,sha
def main():
    root=P/'pi_radius';binary=root/'build/prism-pi';bm=json.loads((root/'build/manifest.json').read_text())
    assert sha(binary)==bm['binary_sha256']
    rows=[]
    for arm in ['off','on']:
        folder=root/'results'/('toy-'+arm)
        r=run(folder,'toy',arm,0,binary,{'OCA_PI_RADIUS':str(int(arm=='on')),'OCA_STCG_ATTEMPTS':str(folder/'attempts.json')},root/'PROTOCOL.md',
          problem=P/'build/toy.txt',cli=CHAMP['cli'][:-1]+['10'],build_manifest=bm)
        if arm=='on':assert 'PI_RADIUS o=' in (folder/'stdout.log').read_text()
        trace=json.loads((folder/'attempts.json').read_text())['totals'];assert trace['accepted']==r['accepts'] and trace['matvecs']==r['matvecs']
    for rep in range(3):
        for arm in (['original','off'] if rep%2==0 else ['off','original']):
            folder=root/'results'/f'dubrovnik-88-{arm}-{rep}'
            flags={} if arm=='original' else {'OCA_PI_RADIUS':'0','OCA_STCG_ATTEMPTS':str(folder/'attempts.json')}
            r=run(folder,'dubrovnik-88',arm,rep,ORIGINAL if arm=='original' else binary,flags,root/'PROTOCOL.md',build_manifest=None if arm=='original' else bm)
            if arm=='off':
                trace=json.loads((folder/'attempts.json').read_text())['totals'];assert trace['accepted']==r['accepts'] and trace['matvecs']==r['matvecs']
            rows.append(r)
    old=[r for r in rows if r['arm']=='original'];off=[r for r in rows if r['arm']=='off']
    delta=100*(statistics.median(r['cost'] for r in off)/statistics.median(r['cost'] for r in old)-1)
    init=[r['score_init'] for r in rows]
    assert abs(delta)<.15 and max(init)-min(init)<1e-9*max(init)
    result=dict(rows=rows,median_cost_delta_percent=delta,score_init_range=[min(init),max(init)],passed=True,
      binary_sha256=bm['binary_sha256'],scope='Compatibility, not timing superiority or identical trajectory proof')
    write(root/'compatibility.json',result);print('COMPATIBILITY',delta,flush=True)
if __name__=='__main__':main()
