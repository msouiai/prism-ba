#!/usr/bin/env python3
"""Summarize saved experiments without concealing missing repeats or crossings."""
import argparse,json,pathlib,statistics,math

def main():
    p=argparse.ArgumentParser();p.add_argument('experiments',nargs='+',type=pathlib.Path)
    p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
    lines=['# Measured iteration-performance results','',
           'Times are solver wall seconds; ranges are observed sample ranges, not tail bounds.',
           'Positive cost/time changes mean the optimized arm is worse/slower.',
           'No verdict is assigned before both arms have at least three repeats.','']
    for folder in a.experiments:
        manifest=json.loads((folder/'preregistered.json').read_text())
        lines += [f'## {folder.name}', '',f"Config {manifest['config']}, max_iter={manifest['max_iter']}; optimized flags: `{manifest['arms']['optimized']}`.", '',
                  '| Scene | N ref/opt | Cost change | Ref seconds median [range] | Opt seconds median [range] | Time change | Cost comparison | Timing ranges |',
                  '|---|---:|---:|---:|---:|---:|---|---|']
        if manifest.get('reference_reuse'):
            lines[-2:-2]=['Reference provenance: '+manifest['reference_reuse'],'']
        rows=[]
        for file in folder.glob('*.json'):
            r=json.loads(file.read_text())
            if isinstance(r,dict) and 'rep' in r:rows.append(r)
        crosses=[]
        for scene in manifest['scenes']:
            group={arm:[r for r in rows if r['scene']==scene and r['arm']==arm] for arm in ['reference','optimized']}
            ref,opt=group.values();n=f'{len(ref)}/{len(opt)}'
            if not ref or not opt:
                lines.append(f'| {scene} | {n} | — | — | — | — | incomplete | incomplete |');continue
            med=lambda rr,key:statistics.median(r[key] for r in rr)
            delta=100*(med(opt,'cost')/med(ref,'cost')-1)
            timing=100*(med(opt,'seconds')/med(ref,'seconds')-1)
            disjoint=max(r['cost'] for r in ref)<min(r['cost'] for r in opt) or max(r['cost'] for r in opt)<min(r['cost'] for r in ref)
            verdict='incomplete' if min(len(ref),len(opt))<3 else ('resolved difference' if abs(delta)>.15 and disjoint else 'not resolved')
            timing_verdict='overlap'
            if max(r['seconds'] for r in opt)<min(r['seconds'] for r in ref):timing_verdict='disjoint, faster'
            if min(r['seconds'] for r in opt)>max(r['seconds'] for r in ref):timing_verdict='disjoint, slower'
            if min(len(ref),len(opt))<3:timing_verdict='incomplete'
            def wall(rr):return f"{med(rr,'seconds'):.3f} [{min(r['seconds'] for r in rr):.3f}, {max(r['seconds'] for r in rr):.3f}]"
            lines.append(f'| {scene} | {n} | {delta:+.4f}% | {wall(ref)} | {wall(opt)} | {timing:+.2f}% | {verdict} | {timing_verdict} |')
            directions=[]
            for arm,other in [('reference','optimized'),('optimized','reference')]:
                target=med(group[other],'cost');times=[]
                for r in sorted(group[arm],key=lambda r:r['rep']):
                    # Original CLI traces start after setup and end before cleanup.
                    # Charge all untraced time before a crossing: conservative upper
                    # bound on solver wall to that crossing, not an exact timestamp.
                    overhead=max(0,r['seconds']-float(r['trace'][-1]['wall_s']))
                    hit=next((float(t['wall_s'])+overhead for t in r['trace'] if float(t['cost'])<=target),None)
                    # Cover CSV (4 decimals) and solve-wall (6 decimals)
                    # rounding, then round the displayed upper bound upward.
                    times.append('never' if hit is None else f'≤{math.ceil((hit+.000101)*1000)/1000:.3f}')
                directions.append(f'{arm} → {other} median: '+', '.join(times))
            crosses.append(f"- **{scene}**: {'; '.join(directions)}")
        lines+=['','Crossings in both directions, in replicate order. Targets are the other arm’s',
                'median endpoint; comparisons use exact costs without a tie tolerance. “Never”',
                'means not reached within the tested budget. Bounds charge all setup/cleanup',
                'time omitted by the original CSV clock before the crossing.','']+crosses+['']
    a.output.write_text('\n'.join(lines)+'\n')

if __name__=='__main__':main()
