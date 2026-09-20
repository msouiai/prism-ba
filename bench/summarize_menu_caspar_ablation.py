#!/usr/bin/env python3
"""Audit frozen artifacts and report ablation without mixing profiling timings."""
import csv,json,pathlib,re,statistics
from expanded_caspar_screen import sha,write
from menu_caspar_ablation import ROOT,SCENES

def enrich(row,protocol):
    assert row['status']=='ok'
    dest=pathlib.Path(row['artifact_dir'])
    manifests=list(dest.rglob('*.manifest.json'));assert len(manifests)==1
    m=json.loads(manifests[0].read_text());flags=m['flags']
    assert m['data_sha256']==protocol['data_sha256'][row['scene']]
    assert m['binary_sha256']==protocol['caspar_sha256' if row['arm']=='caspar64' else 'prism_sha256']
    assert row['audit_error']<1e-7
    if row['arm']=='caspar64':
        log=next((dest/'caspar-runs').glob('*.log')).read_text()
        decisions=re.findall(r'TRACE iter=\d+ cost=\S+ seconds=\S+ accepted=(\d+) pcg=(\d+)',log)
        row.update(accepts=sum(int(a) for a,_ in decisions),rejects=sum(a=='0' for a,_ in decisions),
                   pcg_iterations=sum(int(n) for _,n in decisions))
        assert float(flags['CASPAR_TARGET_COST'])==row['target']
        initial=row['initial_reference']
    else:
        stage=row['stages'][0];assert len(row['stages'])==1 and not row['restarted']
        stem=pathlib.Path(stage['stem']);log=stem.with_suffix('.log').read_text()
        assert flags['OCA_NSHIFTS']==('1' if row['arm']=='single' else '5')
        assert flags['OCA_DEMAND_MENU']=='0' and flags['OCA_SWITCH_RESTART']=='0'
        assert ('OCA_PROFILE' in flags)==row['profile']
        assert ('OCA_LEARN_LOG' in flags)==row['learn_log']
        assert float(flags['OCA_TARGET_COST'])*(1-1e-8)==row['target']
        with stem.with_suffix('.csv').open() as f: trace=list(csv.DictReader(l for l in f if not l.startswith('#')))
        initial=float(trace[0]['cost'])
        row.update(accepts=stage['accepts'],rejects=stage['rejects'],matvecs=stage['matvecs'])
        counts=re.search(r'\[scoring\] menu_evals=(\d+) alpha_evals=(\d+) backtrack_evals=(\d+) total_scored=(\d+)',log)
        assert counts
        row.update(dict(zip(['menu_evals','alpha_evals','backtrack_evals','total_scored'],map(int,counts.groups()))))
        pt=re.search(r'POINT_SAFE summary calls=(\d+) evals=(\d+) wins=(\d+) frozen=(\d+) seconds=(\S+)',log)
        assert pt
        row.update(point_calls=int(pt[1]),point_evals=int(pt[2]),point_wins=int(pt[3]),point_seconds=float(pt[5]))
        if row['profile']:
            p=re.search(r'\[PROFILE\] assembly=(\S+)s pointfactor\+rhs=(\S+)s krylov=(\S+)s candidates=(\S+)s',log);assert p
            phases=dict(zip(['assembly','pointfactor_rhs','krylov','candidates'],map(float,p.groups())))
            for key in ['alpha','backtrack']:
                match=re.search(r'\[PROFILE\] '+key+r'=(\S+)s',log);assert match
                phases[key]=float(match[1])
            phases['point_safeguard']=row['point_seconds']
            row['phases']=phases
    row['initial_cost']=initial
    row['cost_reduction_per_native_second']=(initial-row['cost'])/row['seconds']
    row['relative_cost_reduction_per_native_second']=(1-row['cost']/initial)/row['seconds']
    assert row['hit']==(row['crossing'] is not None and row['crossing']<=row['cap'] and row['cost']<=row['target'])
    return row,flags

def main():
    protocol=json.loads((ROOT/'protocol.json').read_text())
    for f,h in protocol['tooling_sha256'].items():
        assert sha(ROOT/'tooling'/f)==h
        assert sha(pathlib.Path(__file__).parent/f)==h
    measured=json.loads((ROOT/'measurements-results.json').read_text())
    profiles=json.loads((ROOT/'profiles-results.json').read_text())
    assert len(measured)==27 and len(profiles)==6
    for rows,plan in [(measured,protocol['jobs']),(profiles,protocol['profiles'])]:
        assert [r['name'] for r in rows]==[j['name'] for j in plan]
        common=[]
        for row,job in zip(rows,plan):
            assert all(row[k]==v for k,v in job.items())
            _,flags=enrich(row,protocol)
            if row['arm']!='caspar64':
                common.append({k:v for k,v in flags.items() if k not in ['OCA_NSHIFTS','OCA_TARGET_COST','OCA_MAX_SECONDS','OCA_LEARN_LOG']})
        assert all(f==common[0] for f in common)
    cells=[]
    for scene,_,_ in SCENES:
        for arm in ['single','five','caspar64']:
            rr=[r for r in measured if r['scene']==scene and r['arm']==arm];assert len(rr)==3
            cross=[r['crossing'] for r in rr if r['hit']]
            cell=dict(scene=scene,arm=arm,hits=len(cross),median_crossing=statistics.median(cross) if len(cross)==3 else None,
                crossing_range=[min(cross),max(cross)] if cross else None,
                median_endpoint=statistics.median(r['cost'] for r in rr),
                median_process_wall=statistics.median(r['process_wall'] for r in rr),
                median_cost_reduction_per_second=statistics.median(r['cost_reduction_per_native_second'] for r in rr),
                rejects=sum(r['rejects'] for r in rr),
                median_accepts=statistics.median(r['accepts'] for r in rr))
            for key in ['matvecs','menu_evals','point_evals','total_scored']:
                if key in rr[0]:cell['median_'+key]=statistics.median(r[key] for r in rr)
            cells.append(cell)
    summary=dict(cells=cells,measurements_native_seconds=sum(r['seconds'] for r in measured),
        profiles_native_seconds=sum(r['seconds'] for r in profiles),
        max_audit_error=max(r['audit_error'] for r in measured+profiles),
        profiles=[{k:r[k] for k in ['scene','arm','hit','seconds','accepts','rejects','matvecs','menu_evals','point_evals','point_wins','phases']} for r in profiles])
    write(ROOT/'annotated-measurements.json',measured);write(ROOT/'annotated-profiles.json',profiles)
    write(ROOT/'summary.json',summary)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
