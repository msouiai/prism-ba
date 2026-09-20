#!/usr/bin/env python3
"""Verify the matched-state study and summarize all outcomes, including inactive probes."""
import json,pathlib,re,statistics
from expanded_caspar_screen import sha,write
from repair_rollout_study import ROOT

def main():
    protocol=json.loads((ROOT/'protocol.json').read_text())
    old=json.loads((ROOT/'protocol-before-parser-fix.json').read_text())
    assert {k:v for k,v in old.items() if k!='tooling_sha256'}=={k:v for k,v in protocol.items() if k!='tooling_sha256'}
    for f,h in protocol['tooling_sha256'].items():
        assert sha(ROOT/'tooling'/f)==h and sha(pathlib.Path(__file__).parent/f)==h
    assert sha(ROOT/'prism-rollout')==protocol['binary_sha256']
    assert sha(ROOT/'source-rollout.cu')==protocol['source_sha256']
    assert sha(pathlib.Path(__file__).parents[1]/'gpu/oca_cuda.cu')==protocol['source_before_sha256']
    headers=json.loads((ROOT/'headers.json').read_text())
    for f,h in headers.items():assert sha(ROOT/'tooling'/f)==h and sha(pathlib.Path(__file__).parents[1]/'gpu'/f)==h
    rows=json.loads((ROOT/'results.json').read_text());captures=json.loads((ROOT/'captures.json').read_text())
    assert len(rows)==24 and len(captures)==4
    assert [r['name'] for r in rows]==[j['name'] for j in protocol['jobs']]
    for r in rows+captures:
        m=json.loads((ROOT/(r['name']+'.manifest.json')).read_text())
        assert m['binary_sha256']==protocol['binary_sha256'] and m['data_sha256']==protocol['data_sha256']
        assert r['audit_error']<1e-7 and r['rejects']==0 and r['accepts']==3
        assert r['checkpoint_sha256']==sha(ROOT/f"o{r['outer']}.checkpoint")
        assert r['checkpoint_state_sha256']==sha(ROOT/f"o{r['outer']}.initial.state")
        flags=m['flags'];assert 'OCA_PROFILE' not in flags and 'OCA_LEARN_LOG' not in flags
        expected=dict(protocol['flags'],OCA_NSHIFTS='1' if r['arm']=='single' else '5',OCA_REPLAY_STEPS='3')
        if r['capture']:expected.update(OCA_REPLAY_SAVE=str(ROOT/f"o{r['outer']}.checkpoint"),OCA_REPLAY_AT=str(r['outer']))
        else:expected['OCA_REPLAY_LOAD']=str(ROOT/f"o{r['outer']}.checkpoint")
        if r['arm']=='five-probe':expected['OCA_REPLAY_REPAIR_PROBE']='1'
        assert expected==flags
        log=(ROOT/(r['name']+'.log')).read_text()
        r['lambda_trace']=[float(v) for v in re.findall(r'MFCG it\s+\d+ cost=\S+ lam=(\S+)',log)][-3:]
        r['state_sha256']=sha(ROOT/(r['name']+'.state'))
        r['rollout_csv_seconds']=float(r['trace'][-1]['wall_s'])
        if r['capture']:
            # Capture CSV clock includes the opening; no rollout-only timing claim.
            r['rollout_csv_seconds']=None
    cells=[]
    for o in protocol['capture_outers']:
        selected=[r for r in rows if r['outer']==o]
        assert len({r['checkpoint_sha256'] for r in selected})==1
        assert len({r['initial_cost'] for r in selected})==1
        for arm in ['single','five','five-probe']:
            rr=[r for r in selected if r['arm']==arm];assert len(rr)==2
            cells.append(dict(outer=o,arm=arm,initial_cost=rr[0]['initial_cost'],
                median_first_cost=statistics.median(r['first_cost'] for r in rr),
                median_cost=statistics.median(r['cost'] for r in rr),cost_range=[min(r['cost'] for r in rr),max(r['cost'] for r in rr)],
                median_seconds=statistics.median(r['seconds'] for r in rr),
                median_gain_per_second=statistics.median(r['gain_per_native_second'] for r in rr),
                median_matvecs=statistics.median(r['matvecs'] for r in rr),
                probe_eligible=sum(r['probe'] is not None for r in rr),probe_wins=sum(bool(r['probe'] and r['probe']['won']) for r in rr),
                existing_first_repairs=sum(r['first_existing_repair_won'] for r in rr)))
    summary=dict(cells=cells,branch_native_seconds=sum(r['seconds'] for r in rows),capture_native_seconds=sum(r['seconds'] for r in captures),
        max_audit_error=max(r['audit_error'] for r in rows+captures),
        probe_seconds=[r['probe']['seconds'] for r in rows if r['probe']],
        capture_replay_endpoint_relerr={str(c['outer']):max(abs(r['cost']-c['cost'])/c['cost'] for r in rows if r['outer']==c['outer'] and r['arm']=='single') for c in captures},
        missing_process_wall=[r['name'] for r in rows if r['process_wall'] is None])
    write(ROOT/'annotated-results.json',rows);write(ROOT/'summary.json',summary)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
