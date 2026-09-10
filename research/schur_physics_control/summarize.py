#!/usr/bin/env python3
"""Recompute the compact ledger from retained raw logs, without running a solver."""
import pathlib,argparse,json,re,statistics,collections
ROOT=pathlib.Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--data',type=pathlib.Path,default=pathlib.Path('/workspace/prism-schur-physics'));ap.add_argument('--output',type=pathlib.Path,default=ROOT/'summary.json');args=ap.parse_args()
def scalar(x):
    try:return int(x)
    except ValueError:
        try:return float(x)
        except ValueError:return x
def kv(text,prefix):return [dict((k,scalar(v)) for k,v in (t.split('=',1) for t in l.split()[1:] if '=' in t)) for l in text.splitlines() if l.startswith(prefix+' ')]
def stats(xs):
    xs=list(xs)
    return {'n':len(xs),'median':statistics.median(xs),'min':min(xs),'max':max(xs)} if xs else None
def read_run(path):
    t=path.read_text();d={'file':str(path.relative_to(args.data))}
    m=re.search(r'RESULT algo=\S+ iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)',t)
    if m:d.update(outers=int(m[1]),cost=float(m[2]),native_seconds=float(m[3]))
    m=re.search(r'MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)',t)
    if m:d.update(accepts=int(m[1]),rejects=int(m[2]),matvecs=int(m[3]))
    m=re.search(r'TARGET reached outer=(\d+) seconds=(\S+) cost=(\S+) threshold=(\S+)',t)
    d['target_hit']=bool(m)
    if m:d.update(target_outers=int(m[1]),target_seconds=float(m[2]),target_cost=float(m[3]),threshold=float(m[4]))
    d['stop_messages']=list(dict.fromkeys(l.strip() for l in t.splitlines() if 'converged (' in l or 'stop:' in l))
    d['cap60']=d.get('outers',0)>=60
    grads=kv(t,'GRAD_AUDIT');d['terminal_gradient']=next((g for g in grads if g['phase']=='terminal'),None)
    d['coarse_preparations']=kv(t,'COARSE_PREP')
    d['relaxation']=kv(t,'RELAX_PROBE');d['relaxation_trials']=kv(t,'RELAX_TRIAL');d['curvature']=kv(t,'RELAX_CURVATURE')
    meta=path.with_suffix('.json')
    if meta.exists():d['returncode']=json.loads(meta.read_text()).get('returncode')
    return d
out={'winner':'frozen eta2; no candidate promoted','timing':'target_seconds is the native TARGET event; native_seconds includes later reporting/diagnostics. Fixed/menu event timings are computational subtotals, not end-to-end process time.'}
fixed=[]
for p in sorted(args.data.glob('*-fixed.log')):
    for r in kv(p.read_text(),'COARSE_FIXED'):fixed.append(dict(scene=p.stem.removesuffix('-fixed'),**r))
out['fixed_rows']=fixed
out['fixed_summary']=[{'scene':scene,'rank':rank,'hits':sum(r['hit'] for r in rows),'current_ms':stats(r['current_ms'] for r in rows),'pair_ms':stats(r['pair_ms'] for r in rows),'iterations':stats(r['iterations'] for r in rows),'products':stats(r['products'] for r in rows),'prior_hits':sum(r['prior_hit'] for r in rows)} for (scene,rank),rows in ((key,[r for r in fixed if (r['scene'],r['rank'])==key]) for key in sorted({(r['scene'],r['rank']) for r in fixed}))]
targets=[]
for p in sorted((args.data/'targets').glob('*-r*-*.log')):
    m=re.match(r'(.+)-r(\d+)-(\d+)',p.stem);targets.append(dict(scene=m[1],rank=int(m[2]),rep=int(m[3]),**read_run(p)))
for p in sorted((args.data/'transfer').glob('r*-*.log')):
    m=re.match(r'r(\d+)-(\d+)',p.stem);targets.append(dict(scene='ladybug-598',rank=int(m[1]),rep=int(m[2]),**read_run(p)))
out['target_rows']=targets
out['target_summary']=[]
for scene in sorted({r['scene'] for r in targets}):
    base=statistics.median(r['target_seconds'] for r in targets if r['scene']==scene and r['rank']==0)
    for rank in [0,8,16]:
        rows=[r for r in targets if r['scene']==scene and r['rank']==rank]
        times=stats(r['target_seconds'] for r in rows if r['target_hit'])
        out['target_summary'].append({'scene':scene,'rank':rank,'n':len(rows),'hits':sum(r['target_hit'] for r in rows),'target_seconds':times,'native_seconds':stats(r['native_seconds'] for r in rows),'ratio_to_eta2':times['median']/base if times else None,'outers':stats(r['outers'] for r in rows),'rejects':stats(r['rejects'] for r in rows),'matvecs':stats(r['matvecs'] for r in rows),'coarse_active':stats(sum(a['active'] for a in r['coarse_preparations']) for r in rows)})
out['audit_rows']=[];out['audit_summary']=[]
for directory,arms in [('stall',['v2','window8','eta2']),('audit-controls',['delivered-v2','rebuilt-off'])]:
    for arm in arms:
        rows=[dict(cohort=directory,arm=arm,**read_run(p)) for p in sorted((args.data/directory).glob(arm+'-[0-9][0-9].log'))]
        out['audit_rows']+=rows
        high=[r for r in rows if r['cost']>2e6];low=[r for r in rows if r['cost']<2e6]
        out['audit_summary'].append({'cohort':directory,'arm':arm,'n':len(rows),'cost':stats(r['cost'] for r in rows),'stop_count':sum(bool(r['stop_messages']) for r in rows),'cap60_count':sum(r['cap60'] for r in rows),'high_cost_count':len(high),'below_2M_count':len(low),'high_gradient_energy':stats(r['terminal_gradient']['normalized_gradient_energy'] for r in high if r['terminal_gradient']),'low_gradient_energy':stats(r['terminal_gradient']['normalized_gradient_energy'] for r in low if r['terminal_gradient']),'high_tau':stats(r['terminal_gradient']['tau'] for r in high if r['terminal_gradient'])})
out['menu_rows']=[];out['menu_members']=[];out['menu_summary']=[]
for p in sorted((args.data/'menu').glob('*-o*.log')):
    scene=p.stem;t=p.read_text()
    rows=[dict(scene=scene,**r) for r in kv(t,'MENU_TOTAL')];members=[dict(scene=scene,**r) for r in kv(t,'MENU_MEMBER')]
    out['menu_rows']+=rows;out['menu_members']+=members
    for rank in [0,8,16]:
        rs=[r for r in rows if r['rank']==rank];ms=[r for r in members if r['rank']==rank]
        out['menu_summary'].append({'scene':scene,'rank':rank,'member_hits':sum(r['hit'] for r in ms),'members':len(ms),'gpu_host_ms':stats(r['gpu_host_ms'] for r in rs),'charged_ms':stats(r['charged_ms'] for r in rs),'single_center_ms':stats(r['single_center_ms'] for r in rs if 'single_center_ms' in r),'actual_ranks':sorted({r['used'] for r in rs if 'used' in r}),'max_projected_action_error':max((r['model_relative'] for r in ms if 'model_relative' in r),default=None),'max_projected_rhs_error':max((r['rhs_relative'] for r in ms if 'rhs_relative' in r),default=None)})
out['probe_rows']=[]
for directory in ['relaxation','relaxation-extended']:
    for arm in ['v2','eta2']:
        for p in sorted((args.data/directory).glob(arm+'-[0-9][0-9].log')):out['probe_rows'].append(dict(cohort=directory,arm=arm,**read_run(p)))
args.output.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
for key in ['fixed_summary','target_summary','audit_summary','menu_summary']:print(key,json.dumps(out[key],indent=2))
