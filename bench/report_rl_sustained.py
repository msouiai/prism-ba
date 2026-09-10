#!/usr/bin/env python3
"""Report fixed forcing confirmation independently from the RL discovery."""
import json,math,pathlib,re,statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=pathlib.Path('/tmp/prism-rl-sustained');REPO=pathlib.Path('/workspace/prism-ba')
def read(p):return json.loads(pathlib.Path(p).read_text())
def main():
    rows=read(ROOT/'rows.json');assert len(rows)==64
    cells=[]
    for panel,sc,arm in dict.fromkeys((r['panel'],r['scene'],r['arm']) for r in rows):
        rr=[r for r in rows if (r['panel'],r['scene'],r['arm'])==(panel,sc,arm)]
        c=dict(panel=panel,scene=sc,arm=arm,n=len(rr),hits=sum(r['hit'] for r in rr))
        for key in ['target_seconds','audit_cost','outers','rejects','matvecs','setup_seconds']:
            vs=[r[key] for r in rr if r.get(key) is not None]
            if vs:c[key]=dict(median=statistics.median(vs),min=min(vs),max=max(vs))
        cells.append(c)
    ratios={}
    for panel,sc in dict.fromkeys((c['panel'],c['scene']) for c in cells if c['panel']!='caspar'):
        cs={c['arm']:c for c in cells if c['panel']==panel and c['scene']==sc}
        ok=all(c['hits']==c['n'] for c in cs.values())
        ratios[f'{panel}/{sc}']=cs['incumbent']['target_seconds']['median']/cs['eta2']['target_seconds']['median'] if ok else None
    vals=[v for k,v in ratios.items() if not k.startswith('tighter/')]
    geo=math.exp(statistics.mean(math.log(v) for v in vals)) if all(v is not None for v in vals) else None
    candidate_ok=geo is not None and geo>=1.1 and min(vals)>=1/1.1
    largest={c['arm']:c for c in cells if c['scene']=='final-13682' and c['panel'] in ['primary','caspar']}
    caspar={a:largest[a]['target_seconds']['median']/largest['eta2']['target_seconds']['median']
        for a in ['caspar32','caspar64'] if largest[a]['hits']==largest[a]['n'] and largest['eta2']['hits']==largest['eta2']['n']}
    verdict=dict(geometric_mean_speedup=geo,scene_speedups=ratios,candidate_passes=candidate_ok,
        largest_speedup_vs_caspar=caspar,hits=sum(r['hit'] for r in rows),runs=len(rows),
        native_seconds=sum(r['seconds'] for r in rows),maximum_audit_error=max(r['audit_error'] for r in rows))
    for name,obj in [('summary.json',cells),('verdict.json',verdict)]:
        (ROOT/name).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
    lines=['# Sustained CG forcing: confirmation','',
        '**Verdict: '+('candidate passes the registered six-scene gate.' if candidate_ok else 'no general promotion under the registered six-scene gate.')+'**','',
        'Candidate uses one global initial lambda0.1 and twice the incumbent adaptive CG tolerance, capped at0.5. Incumbent uses its previously established lambda10 on Muell and0.1 elsewhere. All other settings match. This is a fixed numerical configuration, not a learned-policy improvement.','',
        f"Six-scene geometric mean speedup: {geo:.4f}x." if geo else 'Geometric mean withheld because a target was missed.','',
        '| Panel | Scene | Arm | Hits | Native target seconds: median [min,max] | Audited cost | Outers | Rejects | Matvecs |',
        '|---|---|---|---:|---:|---:|---:|---:|---:|']
    for c in cells:
        v=c.get('target_seconds');tm=f"{v['median']:.4f} [{v['min']:.4f}, {v['max']:.4f}]" if v else 'miss'
        if c['hits']<c['n']:tm+=' (partial hits)'
        lines.append(f"| {c['panel']} | {c['scene']} | {c['arm']} | {c['hits']}/{c['n']} | {tm} | {c['audit_cost']['median']:.3f} | {c['outers']['median']:.0f} | {c['rejects']['median']:.0f} | "+(f"{c['matvecs']['median']:.0f}" if 'matvecs' in c else '—')+' |')
    tight=ratios['tighter/final-13682'];main_ratio=ratios['primary/final-13682']
    lines+=['',f'Target sensitivity matters: largest-scene speedup is {main_ratio:.3f}x at the primary target, versus {tight:.3f}x at the tighter historical anchor. The tighter target requires an additional candidate outer. The primary speedup is not a uniform claim over convergence quality.' if tight and main_ratio else 'Target sensitivity includes a miss; consult the complete table.',
        '', 'Primary discovery scenes use fresh N5; two additional scenes and tighter-target sensitivity use N3. No outcome was used to retune this configuration. These are familiar research scenes, not pristine holdouts. Within-scene repeats do not establish population certainty.','',
        'The original five-setting actor panel remains a counterexample to universally loosening CG: eta2 with lambda10 on Muell was about47% slower. This new test explicitly evaluates the combined global lambda0.1/eta2 configuration against the previous best initialization map.','',
        '## Fresh Caspar comparison on Final13682','']
    for a,v in caspar.items():lines.append(f'- Candidate speedup versus {a}: {v:.3f}x at target27591576.557625167.')
    lines+=['','Caspar32 requests0.999×target to provide a conservative precision buffer; all reported endpoints pass the same original-observation CPU FP64 audit. Native solve time excludes input loading, state export and audit. Caspar graph setup is also excluded; its median seconds are '+', '.join(f"{a}: {largest[a]['setup_seconds']['median']:.3f}" for a in ['caspar32','caspar64'])+'.','',
        '![Final13682 convergence](figures/convergence/final13682_sustained_caspar.png)','',
        'Curves show actual median-time runs with recorded-cost staircases; no target interpolation. Prism CSV timestamps receive a constant terminal TARGET offset, so intermediate timing alignment is approximate. Tables use native TARGET events. Caspar uses native trace timestamps and audited terminal runtime.','',
        '## Evidence','',
        f"{verdict['hits']}/{len(rows)} target hits; {verdict['native_seconds']:.3f} native solver seconds; maximum relative native/audit discrepancy {verdict['maximum_audit_error']:.3g}. Host2237c6528e79, RTX2000 Ada16GB. All endpoints use half-sum squared original pixel residuals, SIMPLE_RADIAL with k2fixed0.",'',
        '[Protocol](rl_sustained_protocol.md), [actor results](rl_actor_results.md), [reward research](rl_reward_control_research.md). Frozen manifests, hashes, endpoints and logs: `/tmp/prism-rl-sustained/`; compact export: `/workspace/prism-rl-sustained/`. Production defaults remain unchanged.']
    text='\n'.join(lines)+'\n';(ROOT/'RESULTS.md').write_text(text);(REPO/'docs/rl_sustained_results.md').write_text(text)
    folder=ROOT/'figures';folder.mkdir(exist_ok=True)
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    labels={'incumbent':'Prism incumbent','eta2':'Prism sustained CG ×2','caspar32':'Caspar FP32','caspar64':'Caspar FP64'}
    for arm,color in zip(labels,['#26364a','#00866b','#cf6941','#9564aa']):
        rr=[r for r in rows if r['scene']=='final-13682' and r['panel'] in ['primary','caspar'] and r['arm']==arm]
        r=sorted(rr,key=lambda r:r['target_seconds'] or r['seconds'])[len(rr)//2]
        if arm.startswith('caspar'):
            log=pathlib.Path(r['artifact']+'.log').read_text();tr=re.findall(r'TRACE iter=(\d+) cost=(\S+) seconds=(\S+) accepted=(\d+) pcg=(\d+)',log)
            initial=float(re.search(r'INITIAL score=(\S+)',log)[1]);xs=[0]+[float(q[2]) for q in tr];ys=[initial]+[float(q[1]) for q in tr]
        else:
            raw=read(ROOT/'runs'/r['name']/'result.json');tr=raw['trace'];shift=r['target_seconds']-tr[-1]['wall_s'] if r['hit'] else 0
            xs=[0]+[q['wall_s']+shift for q in tr if q['iter']>0];ys=[tr[0]['cost']]+[q['cost'] for q in tr if q['iter']>0]
        for ax in axes:
            ax.step(xs,[y/1e6 for y in ys],where='post',label=labels[arm],color=color,lw=2)
            ax.scatter([r['target_seconds'] or r['seconds']],[r['audit_cost']/1e6],color=color,s=28)
    for ax in axes:
        ax.axhline(27.591576557625167,color='black',ls=':',label='Fixed target');ax.grid(alpha=.15)
        ax.set_xlabel('Native solve time (s)');ax.set_ylabel('L2 cost (millions)');ax.spines[['top','right']].set_visible(False)
    axes[0].set_yscale('log');axes[0].set_title('Recorded trajectory');axes[0].legend(fontsize=8)
    axes[1].set_ylim(24,60);axes[1].set_title('Near fixed target')
    fig.suptitle('Final-13682: sustained CG accuracy control vs fresh Caspar\nActual median-time runs; dots are independently audited endpoints')
    fig.tight_layout()
    for ext in ['png','svg','pdf']:fig.savefig(folder/f'final13682_sustained_caspar.{ext}',dpi=150)
    plt.close(fig);print(json.dumps(verdict,indent=2))
if __name__=='__main__':main()
