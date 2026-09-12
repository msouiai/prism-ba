#!/usr/bin/env python3
import json,subprocess
from grid_common import P,F,run,write,sha
from report_native import summary

subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
binary=P/'frontload/build/prism-frontload'
assert sha(binary)=='24e08d038c4232b6d6a9278e6fa34242b9e9ac5488786bdcc83ecbce2c18b9f9'
bm=json.loads((P/'frontload/build_manifest.json').read_text())
problem='/workspace/bal/venice-52.txt'
panel=json.loads((P/'native-panel.json').read_text())
assert sha(problem)==next(x['input_sha256'] for x in panel['tail'] if x['scene']=='venice-52')
rows=[]
for rep in range(5,10):
    for arm in (['off','on'] if rep%2==0 else ['on','off']):
        folder=P/'evidence/frontload/confirmation'/f'venice-52-{arm}-{rep}'
        row=run(folder,'venice-52',arm,rep,binary,{'OCA_FRONTLOAD':str(int(arm=='on')),'OCA_STCG_ATTEMPTS':str(folder/'attempts.json')},P/'PROTOCOL_05_CONFIRM.md',243740.27,60,problem,build_manifest=bm)
        t=json.loads((folder/'attempts.json').read_text())['totals']
        assert t['accepted']==row['accepts'] and t['matvecs']==row['matvecs']
        row.update(attempts=t,pcg_per_outer=t['pcg_iterations']/max(1,row['outers']),retry_fraction_native=t['retry_entry_seconds']/row['native_seconds'],failed_fraction_native=t['not_accepted_seconds']/row['native_seconds'])
        write(folder/'result.json',row);rows.append(row)
        write(P/'frontload-confirmation-results.json',rows)
        if len(rows)%2==0:
            old=[r for r in json.loads((P/'frontload-tail-results.json').read_text()) if r['scene']=='venice-52']
            ss=[r['score_init'] for r in old+rows];assert max(ss)-min(ss)<1e-9*max(ss)
            result={cohort:{arm:summary([r for r in rr if r['arm']==arm]) for arm in ('off','on')} for cohort,rr in [('confirmation',rows),('combined',old+rows)]}
            write(P/'frontload-confirmation-summary.json',result)
print('COMPLETE frontload confirmation',len(rows))
