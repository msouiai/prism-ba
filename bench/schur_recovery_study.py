#!/usr/bin/env python3
"""Bounded recovery ablations and six-scene extension, with exported-state audits."""
import argparse
import datetime
import gzip
import hashlib
import json
import math
import os
import pathlib
import re
import shutil
import socket
import statistics
import subprocess
import time

from audit_prism_state import audit, observations

ROOT = pathlib.Path('/workspace/prism-schur-recovery')
BAL = pathlib.Path('/workspace/bal')
FROZEN = pathlib.Path('/workspace/prism-model-followup/candidate/prism-tr')
CONTROL = ROOT/'controls/prism-tr'
FLAGS = json.loads(pathlib.Path('/workspace/prism-model-followup/selected_candidate.json').read_text())
EXPANSION = ['ladybug-810','ladybug-1469','dubrovnik-356','venice-951','final-3068','final-13682']
CAPS = {'ladybug-810':8,'ladybug-1469':8,'dubrovnik-356':8,'venice-951':12,'final-3068':12,'final-13682':20,
        'ladybug-1723':8,'final-1936':8,'trafalgar-126':4}
BINS = dict(off=FROZEN, rayleigh=FROZEN, x4=CONTROL, x4_floor=CONTROL, rebuilt_off=CONTROL, rebuilt_rayleigh=CONTROL,
            caspar32=pathlib.Path('/workspace/prism-caspar-current/caspar32'),
            caspar64=pathlib.Path('/workspace/prism-caspar-current/caspar64'))
EXPECTED = dict(off=FLAGS['binary_sha256'],rayleigh=FLAGS['binary_sha256'],
                caspar32='de038488e929a8fad674d1096c5f61619f3039e6409a81670dab0df7dffe0919',
                caspar64='6ca81c85112005b024df4972b0ec16c3819838999a876513e148c58ed8f35eb2')

def sha(path):
    with open(path,'rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def write(path,value):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,indent=2)+'\n')
    tmp.replace(path)

def prepare():
    ROOT.mkdir(exist_ok=True)
    old=json.loads(pathlib.Path('/workspace/prism-caspar-expanded/measurement-plan.json').read_text())
    anchors={s:old['anchors'][s] for s in ['dubrovnik-356','venice-951','final-3068']}
    anchors.update({'final-13682':27318392.631312046,'ladybug-1723':448194.125,
                    'final-1936':5074937.9725361075,'trafalgar-126':104534.24152926281})
    plan=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),host=socket.gethostname(),
        scenes={s:dict(cap=CAPS[s],input_sha256=sha(BAL/(s+'.txt')),anchor=anchors.get(s)) for s in CAPS},
        quality_multipliers=[1.005,1.01,1.02],reps=3,
        historical_anchor_source='/workspace/prism-caspar-expanded/measurement-plan.json except existing model-followup scenes and Final13682 controller anchor',
        new_anchor_rule='Ladybug810/1469 minimum independently audited endpoint across N3 guard-off and N3 Caspar64 calibration, same cap and 600 limit; fixed before any target measurement; calibration excluded from timings',
        primary_arms=['off','rayleigh','caspar32','caspar64'],
        controls=['off','x4','x4_floor','rayleigh'],
        controls_scope='Ladybug1723 diagnostic and Final1936/Trafalgar126 unaffected controls; add controls on expansion scenes that activate the guard or exhibit negative curvature.',
        sensitivity_rule='N3 at 0.5% and 2% on Ladybug1723 and Trafalgar126; add expansion scene when a miss is within 2% of primary target or guard changes hit classification; include all four recovery arms for Ladybug1723.',
        audit_relative_tolerance=1e-6,
        audit_reason='Declared before this study. Prior tighter-target C++/independent-FP64 discrepancy 2.25e-7 exposed arithmetic-order sensitivity. 1e-6 is 0.0001%, far below all declared useful-quality tolerances. Failed audits retained and excluded from timing claims, never silently relaxed.',
        clocks='Native solver timer, parsing/export/audit excluded; Prism includes solver-local setup, Caspar excludes graph setup (recorded). All numerical rebuild work charged. GPU serialized; timeout after lock.',
        caps='Native time primary; 600 secondary: Prism accepted outer steps, Caspar attempted iterations. Process timeout 180s excludes lock wait.',
        selection='Current guard stays frozen throughout extension. Prefer simpler control if reliably equivalent; no tuning on extension.',
        dependency='Ladybug sizes are correlated subsets, not independent recordings.',
        research='No multishift or higher-order residual model is introduced. Existing production defaults untouched.')
    path=ROOT/'plan.json'
    if path.exists():
        previous=json.loads(path.read_text());plan['created_utc']=previous['created_utc'];assert plan==previous
    else:
        write(path,plan)
        with pathlib.Path('/workspace/collab/CLAIMS.md').open('a') as f:
            f.write('\n'+plan['created_utc']+' Codex — bounded Schur recovery study: x4 transient / x4 retained / measured-curvature retained / guard-off N3; six-scene frozen Prism vs Caspar32/64 extension, then declared target sensitivity. Plan /workspace/prism-schur-recovery/plan.json. Local GPU serialized.\n')
    return plan

def run_one(folder,scene,arm,rep,target,cap,dims,obs,proto,*,trace_csv=False):
    stem=folder/f'{scene}-{arm}-{rep}'
    rp=stem.with_suffix('.result.json')
    if rp.exists():
        return json.loads(rp.read_text())
    env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}
    if arm.startswith('caspar'):
        env.update(CASPAR_TARGET_COST=str(target*(.999 if arm=='caspar32' else 1)),CASPAR_MAX_SECONDS=str(cap),CASPAR_STATE_OUT=str(stem)+'.state')
        cmd=[str(BINS[arm]),str(BAL/(scene+'.txt')),'600','default']
    else:
        env.update(FLAGS['flags'],OCA_TARGET_COST=str(target),OCA_MAX_SECONDS=str(cap))
        env['OCA_SCHUR_NUMERIC_GUARD']='0' if arm in ('off','rebuilt_off') else '1'
        if arm in ('x4','x4_floor'):
            env['OCA_SCHUR_RECOVERY_MODE']='1' if arm=='x4' else '2'
        cmd=[str(BINS[arm]),'--problem',str(BAL/(scene+'.txt')),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--mf-no-alpha',
             '--lam0',str(FLAGS['initial_lambda']),'--max_iter','600','--state_out',str(stem)+'.state','--mf-json',str(stem)+'.jsonl']
        if trace_csv:
            cmd += ['--csv',str(stem)+'.csv']
    cmd=['flock','/tmp/prism_gpu.lock','timeout','180']+cmd
    manifest=dict(command=cmd,flags={k:v for k,v in env.items() if k.startswith(('OCA_','CASPAR_'))},
                  binary_sha256=proto['binaries'][arm],input_sha256=proto['scenes'][scene]['input_sha256'])
    write(stem.with_suffix('.manifest.json'),manifest)
    print('RUN',folder.name,stem.name,flush=True)
    start=time.monotonic()
    with stem.with_suffix('.log').open('w') as out,stem.with_suffix('.stderr').open('w') as err:
        proc=subprocess.run(cmd,env=env,stdout=out,stderr=err)
    row=dict(scene=scene,arm=arm,rep=rep,returncode=proc.returncode,process_wall=time.monotonic()-start,
             target=target,cap=cap,hit=False,valid=False,artifact=str(stem))
    state=stem.with_suffix('.state')
    try:
        if proc.returncode:
            raise RuntimeError('process return code '+str(proc.returncode))
        log=stem.with_suffix('.log').read_text()
        cost=audit(state,dims,obs)
        if arm.startswith('caspar'):
            reported=float(re.search(r'CHECK final_score=(\S+)',log)[1])
            seconds=float(re.search(r'RESULT .*?runtime=(\S+)',log)[1])
            trace=re.findall(r'TRACE iter=(\d+) cost=(\S+) seconds=(\S+) accepted=(\d+) pcg=(\d+)',log)
            crossing=seconds if cost<=target else None
            row.update(accepts=sum(int(t[3]) for t in trace),rejects=sum(1-int(t[3]) for t in trace),
                       inner_iters=sum(int(t[4]) for t in trace),outers=len(trace),numeric_rebuilds=0,
                       setup_seconds=float(re.search(r'setup_seconds=(\S+)',log)[1]))
        else:
            result=re.search(r'RESULT .*?final_cost=(\S+) solve_seconds=(\S+)',log)
            reported,seconds=map(float,result.groups())
            reached=re.search(r'TARGET reached outer=(\d+) seconds=(\S+)',log)
            crossing=float(reached[2]) if reached else None
            counts=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+) negcurv=(\d+)',log)
            repair=re.search(r'NUMERIC_REPAIR summary rebuilds=(\d+) floor=(\S+)',log)
            checks=0
            for line in log.splitlines():
                if line.startswith(('CLASSICAL_LM o=','ATTR_RADIUS o=')):
                    v={k:float(v) for k,v in re.findall(r'(\w+)=([^ ]+)',line)}
                    if line.startswith('CLASSICAL_LM'):
                        assert abs(v['lambda']-v['tau'])<=1e-10*max(1e-16,v['lambda']), 'uncoupled damping'
                    if v['accept']:
                        assert v['rho']>.1
                        if line.startswith('ATTR_RADIUS'):
                            assert v['norm']<=v['radius']*(1+1e-8)
                        else:
                            assert v['prediction']>0
                        checks+=1
            row.update(accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]),negcurv=int(counts[4]),
                numeric_rebuilds=int(repair[1]) if repair else 0,numeric_floor=float(repair[2]) if repair else None,
                accepted_checks=checks,outers=int(counts[1])+int(counts[2]))
        error=abs(cost-reported)/max(1,cost)
        row.update(cost=cost,reported=reported,seconds=seconds,crossing=crossing,audit_error=error,
                   state_sha256=sha(state),cap_hit=seconds>=cap or (row['outers'] if arm.startswith('caspar') else row['accepts'])>=600)
        assert math.isfinite(cost) and error<proto['audit_relative_tolerance'], ('audit disagreement',error)
        row.update(valid=True,hit=crossing is not None and crossing<=cap and cost<=target)
    except Exception as exc:
        row['error']=str(exc)
    if state.exists():
        with state.open('rb') as src,gzip.open(str(state)+'.gz','wb',compresslevel=1) as dest:
            shutil.copyfileobj(src,dest)
        row['compressed_state_sha256']=sha(pathlib.Path(str(state)+'.gz'))
        state.unlink()  # Only this study's completed export, now losslessly archived.
    write(rp,row)
    print('DONE',json.dumps({k:row.get(k) for k in ['scene','arm','rep','valid','hit','crossing','cost','rejects','numeric_rebuilds','error']}),flush=True)
    return row

def summarize(rows):
    cells=[]
    for scene,arm in dict.fromkeys((r['scene'],r['arm']) for r in rows):
        rr=[r for r in rows if r['scene']==scene and r['arm']==arm]
        times=[r['crossing'] for r in rr if r['hit']]
        cells.append(dict(scene=scene,arm=arm,runs=len(rr),valid=sum(r['valid'] for r in rr),hits=len(times),
            median=statistics.median(times) if len(times)==len(rr) else None,
            range=[min(times),max(times)] if times else None,
            costs=[r.get('cost') for r in rr],rebuilds=[r.get('numeric_rebuilds') for r in rr],
            rejects=[r.get('rejects') for r in rr]))
    return cells

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--phase',choices=['prepare','calibration','controls','extension','sensitivity','compatibility'],required=True)
    ap.add_argument('--scenes',nargs='+')
    ap.add_argument('--arms',nargs='+')
    ap.add_argument('--multiplier',type=float,choices=[1.005,1.01,1.02],default=1.01)
    ap.add_argument('--name')
    ap.add_argument('--reps',type=int,default=3)
    a=ap.parse_args()
    plan=prepare()
    if a.phase=='prepare':
        print(json.dumps(plan,indent=2));return
    if a.phase=='calibration':
        scenes=a.scenes or ['ladybug-810','ladybug-1469'];arms=a.arms or ['off','caspar64']
    elif a.phase=='controls':
        scenes=a.scenes or ['ladybug-1723','final-1936','trafalgar-126'];arms=a.arms or plan['controls']
    elif a.phase=='compatibility':
        scenes=a.scenes or ['final-1936'];arms=a.arms or ['off','rebuilt_off','rayleigh','rebuilt_rayleigh']
    else:
        scenes=a.scenes or EXPANSION;arms=a.arms or plan['primary_arms']
    specs={s:plan['scenes'][s].copy() for s in scenes}
    if a.phase!='calibration' and any(v['anchor'] is None for v in specs.values()):
        new=json.loads((ROOT/'new-anchors.json').read_text())
        for s,v in specs.items():
            if v['anchor'] is None:v['anchor']=new[s]
    for s,v in specs.items():
        v['target']=1e-100 if a.phase=='calibration' else v['anchor']*a.multiplier
    hashes={arm:sha(BINS[arm]) for arm in arms}
    for arm,value in hashes.items():
        if arm in EXPECTED:assert value==EXPECTED[arm],arm
    proto=dict(phase=a.phase,host=plan['host'],scenes=specs,arms=arms,reps=a.reps,multiplier=a.multiplier,
               binaries=hashes,flags=FLAGS,plan_sha256=sha(ROOT/'plan.json'),audit_relative_tolerance=plan['audit_relative_tolerance'])
    folder=ROOT/(a.name or a.phase)
    folder.mkdir(exist_ok=True)
    if (folder/'protocol.json').exists():assert json.loads((folder/'protocol.json').read_text())==proto
    else:write(folder/'protocol.json',proto)
    rows=[]
    # One observation array at a time. Scene-major avoids loading 1.5GB BAL repeatedly for CPU auditing.
    for si,scene in enumerate(scenes):
        pending=any(not (folder/f'{scene}-{arm}-{rep}.result.json').exists()
                    for rep in range(1,a.reps+1) for arm in arms)
        dims,obs=observations(BAL/(scene+'.txt')) if pending else (None,None)
        for rep in range(1,a.reps+1):
            offset=(si+rep-1)%len(arms)
            for arm in arms[offset:]+arms[:offset]:
                rows.append(run_one(folder,scene,arm,rep,specs[scene]['target'],specs[scene]['cap'],dims,obs,proto))
                write(folder/'results.json',rows)
                write(folder/'summary.json',summarize(rows))
        del obs
    if a.phase=='calibration':
        anchors={s:min(r['cost'] for r in rows if r['scene']==s and r['valid']) for s in scenes}
        # Failed consistency checks are retained and excluded, as declared in
        # plan.json. They cannot supply an anchor or a timing observation.
        assert all(sum(r['valid'] for r in rows if r['scene']==s and r['arm']==arm)>=1
                   for s in scenes for arm in arms)
        write(ROOT/'new-anchors.json',anchors)
    print('COMPLETE',len(rows),json.dumps(summarize(rows)),flush=True)

if __name__=='__main__':
    main()
