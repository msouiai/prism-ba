#!/usr/bin/env python3
"""Fresh user-requested N=10 comparison, with endpoint controls and frozen targets."""
import argparse,csv,json,os,re,statistics,subprocess,tempfile
from pathlib import Path
from run import P,G

Q=P/'confirmation'
PROTOCOL=P/'PROTOCOL_CONFIRMATION.md'
def verify_build():
    subprocess.run(['python3',str(G.F/'build.py'),'--check-only'],check=True)
    b=json.loads((P/'build_manifest.json').read_text())
    assert G.sha(P/'build/prism-track-tau')==b['binary_sha256']
    assert G.sha(G.ORIGINAL)==G.CHAMP['binary_sha256']
    assert G.sha(G.F/'champion.json')==b['champion_sha256']
    assert G.sha(G.F/'source/prism_eta2.cu')==b['frozen_source_sha256']
    assert G.sha(P/'build/prism_track_tau.cu')==b['derived_source_sha256']
    assert all(G.sha(P/k)==v for k,v in b['headers'].items())
    assert json.loads((P/'factor_verification.json').read_text())['passed']
    assert json.loads((P/'evidence/correctness/mixed-toy-memcheck/result.json').read_text())['passed']
    old=json.loads((P/'compatibility-results.json').read_text());assert len(old)==6
    costs={a:statistics.median(r['cost'] for r in old if r['arm']==a) for a in ('original','off')}
    assert abs(costs['off']/costs['original']-1)<.0015
    return b

def register():
    b=verify_build();Q.mkdir(exist_ok=True)
    historical_path=P.parent/'eta2_external_coverage/storm-results.json'
    historical=[r for r in json.loads(historical_path.read_text()) if r['scene']=='final-3068' and r['arm']=='champion']
    hits=[r['target_seconds'] for r in historical if r['hit']]
    assert len(historical)==10 and len(hits)==8
    cells=[]
    specs=[('tail','final-3068',10,1744796.9841897595,True),
           ('tail','venice-52',10,243740.27,True),
           ('controls','final-4585',3,7767397.3902649265,False),
           ('controls','dubrovnik-88',3,362571.82,False),
           ('controls','ladybug-539',3,165617.73918321263,False)]
    for stage,scene,n,target,stopping in specs:
        path=Path('/workspace/bal')/(scene+'.txt')
        if scene=='ladybug-539':path=Path('/tmp/prism-speed-novelty/inputs/ladybug-539.txt')
        cells.append(dict(stage=stage,scene=scene,n=n,target=target,target_stopping=stopping,
                          path=str(path),input_sha256=G.sha(path),cap=60,max_outers=600))
    reg=dict(protocol_sha256=G.sha(PROTOCOL),binary_sha256=b['binary_sha256'],
             champion_sha256=G.sha(G.F/'champion.json'),build_manifest=b,cells=cells,
             historical=dict(source=str(historical_path),sha256=G.sha(historical_path),n=10,hits=8,
                 target=historical[0]['target'],median=statistics.median(hits),range=[min(hits),max(hits)],
                 maximum_on_median_20percent=1.2*statistics.median(hits)),
             prior_screen_in_primary=False,expected_scored_runs=58)
    dest=Q/'registration.json'
    if dest.exists():assert json.loads(dest.read_text())==reg
    else:G.write(dest,reg)
    print('REGISTERED',[(x['scene'],x['n'],x['target']) for x in cells],flush=True)
    return reg

def run_cell(reg,cell,arm,rep):
    scene=cell['scene'];folder=P/'evidence/confirmation'/cell['stage']/f'{scene}-{arm}-{rep}'
    assert G.sha(cell['path'])==cell['input_sha256']
    operating_target=cell['target'] if cell['target_stopping'] else 0
    flags=dict(OCA_TRACK_TAU=str(int(arm=='on')),OCA_STCG_ATTEMPTS=str(folder/'attempts.json'))
    # State export occurs after native timing. Stage its raw bytes in RAM so the
    # durable gzip does not require a second full endpoint allocation on disk.
    temporary=None
    if not (folder/'result.json').exists():
        folder.mkdir(parents=True,exist_ok=True)
        fd,path=tempfile.mkstemp(prefix='eta2-confirm-'+scene+'-',suffix='.state',dir='/dev/shm')
        os.close(fd);temporary=Path(path)
        assert not (folder/'endpoint.state').exists()
        (folder/'endpoint.state').symlink_to(temporary)
        G.write(folder/'export-staging.json',dict(raw_path=str(temporary),
           policy='Raw export in RAM; exact hashed gzip retained on disk before raw cleanup.'))
    r=G.run(folder,scene,arm,rep,P/'build/prism-track-tau',flags,PROTOCOL,
            operating_target,cell['cap'],cell['path'],build_manifest=reg['build_manifest'])
    if temporary is not None:
        assert r['valid'] and G.sha(temporary)==r['state']['sha256']
        assert G.sha(folder/'endpoint.state.gz')==r['state']['compressed_sha256']
        temporary.unlink()  # Only the verified duplicate raw export of this run.
    tr=json.loads((folder/'attempts.json').read_text())['totals']
    assert tr['accepted']==r['accepts'] and tr['matvecs']==r['matvecs']
    text=(folder/'stdout.log').read_text()
    assert ('TRACK_TAU rule=' in text)==(arm=='on')
    curve=list(csv.DictReader(x for x in (folder/'curve.csv').read_text().splitlines() if not x.startswith('#')))
    crossing=next((float(x['wall_s']) for x in curve if float(x['cost'])<=cell['target']),None)
    hit=r['cost']<=cell['target'] and crossing is not None and crossing<=cell['cap']
    stop='unclassified'
    if 'TARGET reached' in text:stop='target'
    elif re.search(r'BUDGET stop=|MAX_SECONDS.*(?:stop|exceed)',text):stop='time_cap'
    elif r['outers']>=cell['max_outers']:stop='outer_cap'
    elif 'converged (OCA_FTOL:' in text:stop='ftol'
    elif 'converged (relative cost decrease' in text:stop='relative_decrease'
    r.update(stage=cell['stage'],cell=scene,cohort='fresh_confirmation',target=cell['target'],
        solver_target=operating_target,target_stopping=cell['target_stopping'],hit=hit,
        target_seconds=crossing if hit else None,stop_reason=stop,
        attempts=tr,pcg_per_outer=tr['pcg_iterations']/max(1,r['outers']),
        retry_fraction_native=tr['retry_entry_seconds']/r['native_seconds'],
        failed_fraction_native=tr['not_accepted_seconds']/r['native_seconds'])
    G.write(folder/'result.json',r)
    return r

def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['register','tail','controls']);a=ap.parse_args()
    if a.stage=='register':register();return
    reg=json.loads((Q/'registration.json').read_text());b=verify_build()
    assert reg['protocol_sha256']==G.sha(PROTOCOL) and reg['binary_sha256']==b['binary_sha256']
    cells=[c for c in reg['cells'] if c['stage']==a.stage];rows=[]
    for rep in range(max(c['n'] for c in cells)):
        for cell in (cells if rep%2==0 else list(reversed(cells))):
            for arm in (['off','on'] if rep%2==0 else ['on','off']):
                rows.append(run_cell(reg,cell,arm,rep));G.write(Q/(a.stage+'-results.json'),rows)
    for cell in cells:
        rr=[r for r in rows if r['scene']==cell['scene']]
        assert len(rr)==2*cell['n']
        initial=[r['score_init'] for r in rr]
        assert max(initial)-min(initial)<=1e-9*max(initial)
    print('COMPLETE',a.stage,len(rows),flush=True)
if __name__=='__main__':main()
