#!/usr/bin/env python3
"""Report bounded rejection experiments; never mix diagnostic timing with pilots."""
import argparse,json,re,statistics
from pathlib import Path

def records(path):
    out=[]
    for line in path.read_text().splitlines():
        line=re.sub(r'(?<![a-zA-Z])(?:-?nan|-?inf)(?![a-zA-Z])','null',line)
        try:out.append(json.loads(line))
        except json.JSONDecodeError:raise ValueError(f'Incomplete/malformed diagnostic: {path}')
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path('/workspace/prism-rejection'));ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    cohorts={};best={};diagnostics=[];forks=[]
    for cohort in ['coverage-pilot','rearm-pilot','coverage-v2-pilot']:
        rows=[]
        for p in (a.root/cohort).glob('*.json'):
            r=json.loads(p.read_text())
            if 'status' not in r:continue
            rows.append(r)
            if r['status']=='ok':best[r['scene']]=min(best.get(r['scene'],float('inf')),r['cost'])
        cohorts[cohort]=rows
    for p in sorted((a.root/'diagnostic').glob('*.jsonl')):
        rs=records(p);aa=[r for r in rs if r['t']=='a'];cc=[r for r in rs if r['t']=='c'];off=[r for r in rs if r['t']=='bt_off'];rej=[r for r in aa if not r['acc']]
        center=next(r['grid_down'] for r in rs if r['t']=='hdr')
        diagnostics.append(dict(name=p.stem,attempts=len(aa),rejects=len(rej),after_off=sum(r['a']>=off[0]['next_a'] for r in rej) if off else 0,gate_on_reject=sum(r['gated']>0 for r in rej),center_unscored=sum(not any(c['a']==r['a'] and c['sh']==center for c in cc) for r in rej),truncated_rejects=sum(r['tr'] for r in rej),nonfinite_candidates=sum(not c['fin'] for c in cc),off=off))
    for p in sorted((a.root/'forks').glob('tau*.jsonl')):
        rs=records(p);aa=[r for r in rs if r['t']=='a'];cc=[r for r in rs if r['t']=='c'];r=aa[-1]
        forks.append(dict(name=p.stem,lambda_center=r['lam'],point_tau=r['tau'],initial_cost=r['cost0'],final_cost=r['bcost'],accepted=r['acc'],best_shift=r['bsh'],best_menu_cost=min(c['cost'] for c in cc if c['fin'])))
    lines=['# Bounded rejection study results','','Exploratory: two repeats per original pilot arm; one repeat per corrected-coverage recheck arm. Medians and observed ranges are not confidence intervals.','All timed arms use full fp64 scoring, the same 600-outer budget and eight-probe backtracking.','Diagnostic runs have extra logging and are excluded from runtime comparisons.','']
    for cohort,rows in cohorts.items():
        good=[r for r in rows if r['status']=='ok'];failed=[r for r in rows if r['status']!='ok'];groups={}
        for r in good:
            groups.setdefault((r['scene'],r['arm']),[]).append(r)
            overhead=max(0,r['seconds']-float(r['trace'][-1]['wall_s']))
            r['quality_seconds']={str(e):next((float(t['wall_s'])+overhead for t in r['trace'] if float(t['cost'])<=best[r['scene']]*(1+e)),None) for e in [.01,.03,.05]}
        lines += [f'## {cohort}', '',f'Completed: {len(good)}; recorded execution failures: {len(failed)}.','', '| Scene | Arm | N | Cost median [range] | Seconds median [range] | Rejects | Rescues | Matvecs | All scoring |','|---|---|---:|---:|---:|---:|---:|---:|---:|']
        for (scene,arm),rr in sorted(groups.items()):
            med=lambda k:statistics.median(r[k] for r in rr)
            ran=lambda k:f'{med(k):,.3f} [{min(r[k] for r in rr):,.3f}, {max(r[k] for r in rr):,.3f}]'
            lines += [f'| {scene} | {arm} | {len(rr)} | {ran("cost")} | {ran("seconds")} | {med("rejects"):g} | {med("backtrack_rescues"):g} | {med("matvecs"):g} | {med("total_scored"):g} |']
        lines += ['','Time to 1%, 3%, 5% above the lowest endpoint observed across the pilot cohorts on each scene.','Untraced solver overhead is charged before the crossing; missing attainment stays missing.','','| Scene | Arm | 1% seconds | 3% seconds | 5% seconds |','|---|---|---:|---:|---:|']
        for (scene,arm),rr in sorted(groups.items()):
            cells=[]
            for e in [.01,.03,.05]:
                v=[r['quality_seconds'][str(e)] for r in rr if r['quality_seconds'][str(e)] is not None]
                cells.append(f'{statistics.median(v):.4f} ({len(v)}/{len(rr)})' if v else f'— (0/{len(rr)})')
            lines.append(f'| {scene} | {arm} | '+' | '.join(cells)+' |')
        lines += ['']
    lines += ['## Logged diagnosis','','| Scene/arm | Rejections | After safeguard disabled | Rejections with gate firing | Rejections without center scored | Curvature-truncated rejections | Nonfinite candidates |','|---|---:|---:|---:|---:|---:|---:|']
    for r in diagnostics:lines.append('| '+r['name']+' | '+' | '.join(str(r[k]) for k in ['rejects','after_off','gate_on_reject','center_unscored','truncated_rejects','nonfinite_candidates'])+' |')
    lines += ['','These are associations on each trajectory. An unscored center is not proof it would have succeeded.','','## Same-state camera/point damping forks','','One saved Ladybug-1197 state at outer 40, full menu without model gating, one outer and no retries/backtracking.','Point damping and camera center varied independently; controller history is reset. This isolates a local response, not a full-run performance claim.','','| Camera center | Point tau | Initial cost | Best menu cost | Final cost after optional alpha grid | Accepted |','|---:|---:|---:|---:|---:|---:|']
    for r in forks:lines.append(f'| {r["lambda_center"]:g} | {r["point_tau"]:g} | {r["initial_cost"]:,.5f} | {r["best_menu_cost"]:,.5f} | {r["final_cost"]:,.5f} | {r["accepted"]} |')
    a.output.write_text('\n'.join(lines)+'\n')
    (a.root/'results.json').write_text(json.dumps(dict(cohorts=cohorts,empirical_reference=best,diagnostics=diagnostics,forks=forks),indent=2)+'\n')
    print('successful',sum(sum(r['status']=='ok' for r in rr) for rr in cohorts.values()),'failed',sum(sum(r['status']!='ok' for r in rr) for rr in cohorts.values()))
if __name__=='__main__':main()
