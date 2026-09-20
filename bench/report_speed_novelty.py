#!/usr/bin/env python3
"""Report all frozen-panel cells, including misses and recovery attribution."""
import hashlib
import json
import math
import pathlib
import re
import statistics as st

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = pathlib.Path('/tmp/prism-speed-novelty')
REPO = pathlib.Path(__file__).resolve().parents[1]
NAMES = {'champion':'Prism eta2','caspar32':'Caspar FP32','caspar64':'Caspar FP64',
         'ceres_lm':'Ceres LM (CPU)','ceres_dogleg':'Ceres Dogleg (CPU)',
         'off':'Prism guard off','x4_floor':'Prism ×4 + floor'}

def read(p):
    return json.loads(pathlib.Path(p).read_text())

def med(xs):
    return st.median(xs)

def interval(xs):
    return f'{med(xs):.4f} [{min(xs):.4f}, {max(xs):.4f}]'

def main():
    assert read(ROOT/'COMPLETE.json')['runs']==153
    rows = read(ROOT/'measure-rows.json')
    proto = read(ROOT/'protocol.json')
    scenes = list(proto['scenes'])
    arms = proto['selection']['timing_arms']
    multipliers = proto['selection']['quality_multipliers']
    anchors = read(ROOT/'anchors.json')['anchors']
    def cell(sc, arm, mult=1.01):
        return [r for r in rows if r['scene']==sc and r['arm']==arm and r['phase']=='q'+str(mult)]
    def successful(rr):
        return len(rr)==3 and all(r['hit'] for r in rr)
    def timing(rr,setup=False):
        if successful(rr):
            return interval([r['crossing']+(r['setup_seconds'] if setup else 0) for r in rr])
        return f"{sum(r['hit'] for r in rr)}/{len(rr)} hits"
    findings = dict(primary={},tolerances={},curvature={},scope='Three new instances in familiar dataset families; not global fastest.')
    for mult in multipliers:
        ff = {}
        for sc in scenes:
            usable = [a for a in arms if successful(cell(sc,a,mult))]
            winner = min(usable,key=lambda a:med([r['crossing'] for r in cell(sc,a,mult)])) if usable else None
            ratios = {a:med([r['crossing'] for r in cell(sc,a,mult)])/med([r['crossing'] for r in cell(sc,'champion',mult)])
                for a in arms if a!='champion' and successful(cell(sc,a,mult)) and successful(cell(sc,'champion',mult))}
            ff[sc] = dict(winner=winner,ratios_baseline_over_champion=ratios,
                hits={a:sum(r['hit'] for r in cell(sc,a,mult)) for a in arms})
        findings['tolerances'][str(mult)] = ff
    findings['primary'] = findings['tolerances']['1.01']
    formula_checks = []
    for sc in scenes:
        cc,xx,oo = [cell(sc,a) for a in ['champion','x4_floor','off']]
        active = any(r.get('numeric_rebuilds',0)>0 or r.get('negcurv',0)>0 for r in cc+xx+oo)
        ratio = med([r['crossing'] for r in xx])/med([r['crossing'] for r in cc]) if successful(xx) and successful(cc) else None
        findings['curvature'][sc] = dict(active=active,x4_over_curvature_time=ratio,
            champion_hits=sum(r['hit'] for r in cc),x4_hits=sum(r['hit'] for r in xx),off_hits=sum(r['hit'] for r in oo),
            repairs={a:[r.get('numeric_rebuilds') for r in cell(sc,a)] for a in ['champion','x4_floor','off']})
    for r in rows:
        previous_floor = 1e-16
        for e in r.get('repair_events',[]):
            lam,q = e['lambda'],e['rayleigh']
            repaired = 4*(lam if r['arm']=='x4_floor' else max(lam,lam-q))
            expected = max(previous_floor,min(1e16,max(1e-14,repaired)))
            assert abs(e['next_lambda']-expected)<=1e-10*max(1e-16,expected)
            previous_floor=expected
            formula_checks.append(dict(scene=r['scene'],arm=r['arm'],rep=r['rep'],phase=r['phase'],
                rayleigh=q,lambda_used=lam,x4_directional_bound=q+3*lam,
                x4_sufficient=q+3*lam>0,measured_multiplier=4*max(lam,lam-q)/lam))
    active = [v for v in findings['curvature'].values() if v['active']]
    wins = [v for v in active if v['x4_over_curvature_time'] is not None and v['x4_over_curvature_time']>=1.10]
    # A missing/non-comparable active cell cannot satisfy a no-regression requirement.
    supported = len(wins)>=2 and all(v['x4_over_curvature_time'] is not None and v['x4_over_curvature_time']>=1/1.10 for v in active)
    findings['curvature_criterion_met'] = supported
    findings['guard_active_instances'] = len(active)
    findings['repair_events'] = len(formula_checks)
    findings['x4_sufficient_events'] = sum(x['x4_sufficient'] for x in formula_checks)
    findings['totals'] = dict(measured_runs=len(rows),valid=sum(r['valid'] for r in rows),
        native_seconds=sum(r.get('seconds',0) for r in rows),process_wall=sum(r['process_wall'] for r in rows),
        max_audit_error=max(r.get('audit_error',0) for r in rows),
        calibration_runs=len(read(ROOT/'calibrate-rows.json')))
    native_checks=[]
    for r in rows:
        if r['arm'].startswith('caspar') and r['valid']:
            log=pathlib.Path(r['artifact']+'.log').read_text()
            m=re.search(r'RESULT exit=(\d+) iters=(\d+) final_score=(\S+)',log)
            native=float(m[3])
            native_checks.append(dict(scene=r['scene'],arm=r['arm'],phase=r['phase'],rep=r['rep'],
                exit_reason=int(m[1]),hit=r['hit'],native_cost=native,audited_cost=r['cost'],
                native_relative_error=abs(native-r['cost'])/max(1,r['cost'])))
    findings['caspar_native_checks']=native_checks
    (ROOT/'verdict.json').write_text(json.dumps(findings,indent=2)+'\n')
    (ROOT/'repair-validation.json').write_text(json.dumps(formula_checks,indent=2)+'\n')
    # Check loader score agreement across all measured implementations, allowing only FP32 input quantization.
    initial = {}
    for sc in scenes:
        values = {}
        for arm in arms:
            vals=[]
            for r in cell(sc,arm):
                log=pathlib.Path(r['artifact']+'.log').read_text()
                pat=r'MFCG score_init=(\S+)' if arm=='champion' else r'CHECK_INITIAL score=(\S+)' if arm.startswith('caspar') else r'INITIAL score=(\S+)'
                m=re.search(pat,log)
                if m:vals.append(float(m[1]))
            if vals:values[arm]=med(vals)
        base=values['champion']
        initial[sc]=dict(costs=values,relative_gaps={a:abs(v-base)/max(1,base) for a,v in values.items()})
        assert all(initial[sc]['relative_gaps'][a]<1e-6 for a in values if a!='caspar32')
    (ROOT/'initial-score-check.json').write_text(json.dumps(initial,indent=2)+'\n')
    late=read(ROOT/'late-diagnostic-rows.json')
    late_summary={}
    late_checks=[]
    for arm in ['off','x4_floor','champion']:
        rr=[r for r in late if r['arm']==arm]
        late_summary[arm]=dict(seconds=[r['seconds'] for r in rr],costs=[r['cost'] for r in rr],
            rejects=[r['rejects'] for r in rr],repairs=[r['numeric_rebuilds'] for r in rr])
    for r in late:
        floor=1e-16
        for e in r['repair_events']:
            lam,q=e['lambda'],e['rayleigh']
            proposed=4*(lam if r['arm']=='x4_floor' else max(lam,lam-q))
            floor=max(floor,min(1e16,max(1e-14,proposed)))
            assert abs(e['next_lambda']-floor)<1e-10*max(1e-16,floor)
            late_checks.append(dict(arm=r['arm'],rep=r['rep'],outer=e['o'],lambda_used=lam,
                rayleigh=q,next_lambda=floor,x4_directional_bound=q+3*lam,
                implemented_x4_bound=q+min(1e16,max(1e-14,4*lam))-lam))
    findings['late_diagnostic']=dict(summary=late_summary,repair_checks=late_checks,
        interpretation='Time to stall is not time to equal quality. One activation-selected instance; not a primary-panel novelty win.')
    (ROOT/'verdict.json').write_text(json.dumps(findings,indent=2)+'\n')
    lines=['# Frozen new-instance speed and curvature results','',
        'The frozen sustained-eta2 champion was evaluated on three previously unmeasured local BAL instances. All targets were frozen after separate reference calibration and before measured runs. These are instances from familiar dataset families, not three independent new capture domains.','',
        'Prism had the lowest median time among evaluated configurations in all nine scene–tolerance comparisons, with 27/27 audited target hits. Caspar FP32 reached 16/27 and FP64 reached 21/27; both Ceres arms reached 27/27. This supports a fastest-among-tested claim for this frozen three-instance panel on this host. It does not establish the globally fastest BA solver. The practical-target results do not establish incremental value from curvature sizing because numerical recovery never activated before those targets.','',
        f"Measured runs: **{len(rows)}**, valid independent endpoint audits: **{sum(r['valid'] for r in rows)}**. Native solve time: **{findings['totals']['native_seconds']:.2f} s**. N=3 per cell; all times below are median [min, max] seconds. A miss remains a miss and is not assigned the cap as its observed time to target.",'',
        '## Primary time-to-target comparison','',
        '| Scene | Prism eta2 | Caspar FP32 | Caspar FP64 | Ceres LM CPU | Ceres Dogleg CPU | Fastest 3/3 arm |',
        '|---|---:|---:|---:|---:|---:|---|']
    for sc in scenes:
        w=findings['primary'][sc]['winner']
        lines.append('| '+sc+' | '+' | '.join(timing(cell(sc,a)) for a in arms)+' | '+(NAMES[w] if w else 'none')+' |')
    lines += ['', 'All algorithms optimize the same original-observation SIMPLE_RADIAL L2 objective, with k2 fixed to zero. The primary target is 1% above the frozen bounded-calibration anchor. Caspar FP32 stops against an additional conservative 0.1% native margin; original-observation FP64 endpoint auditing determines qualification.', '',
        '| Scene | Anchor | 0.5% target | 1% target | 2% target | Native cap |','|---|---:|---:|---:|---:|---:|']
    for sc in scenes:
        lines.append(f'| {sc} | {anchors[sc]:.9f} | '+' | '.join(f'{anchors[sc]*m:.9f}' for m in multipliers)+f" | {proto['selection']['native_caps'][sc]} s |")
    lines += ['', '## Target sensitivity: every registered comparison cell', '',
        '| Scene | Tolerance above anchor | Prism eta2 | Caspar FP32 | Caspar FP64 | Ceres LM CPU | Ceres Dogleg CPU |','|---|---:|---:|---:|---:|---:|---:|']
    for sc in scenes:
        for mult in multipliers:
            lines.append(f'| {sc} | {(mult-1)*100:.1f}% | '+' | '.join(timing(cell(sc,a,mult)) for a in arms)+' |')
    lines += ['', '![Fixed-target comparison](figures/convergence/frozen_new_instances_time_to_target.png)', '',
        '## Curvature attribution at the primary target', '',
        '| Scene | Guard off | ×4 + retained floor | Curvature + retained floor | ×4 / curvature time |',
        '|---|---:|---:|---:|---:|']
    for sc in scenes:
        ratio=findings['curvature'][sc]['x4_over_curvature_time']
        ratio_text=f'{ratio:.3f}x' if ratio is not None else 'not comparable'
        lines.append('| '+sc+' | '+' | '.join(timing(cell(sc,a)) for a in ['off','x4_floor','champion'])+f' | {ratio_text} |')
    lines += ['',f"Guard-active instances at the primary target: **{len(active)}/3**. Registered curvature-sizing criterion met: **{supported}**. This criterion requires at least two 1.10x improvements at equal reliability and no greater than 1.10x regression on another active instance.",'',
        ('There were no numerical repair events in the measured practical-target panel; no repair-formula validation can be inferred from those inactive runs. The separate late-stage diagnostic below exercises and checks the repair rules.' if not formula_checks else
         f"Repair formulas and floors matched for {len(formula_checks)} events; q + 3 lambda > 0 held in {sum(x['x4_sufficient'] for x in formula_checks)}."),'',
        '## Endpoints and work at the primary target','',
        '| Scene | Arm | Hits | Median audited cost | Median gap above target | Median seconds run | Accepted / rejected per run | Repairs per run | Cap hits |',
        '|---|---|---:|---:|---:|---:|---|---|---:|']
    for sc in scenes:
        for arm in arms+['off','x4_floor']:
            rr=cell(sc,arm);valid=[r for r in rr if r['valid']]
            if not valid:continue
            lines.append(f"| {sc} | {NAMES[arm]} | {sum(r['hit'] for r in rr)}/3 | {med([r['cost'] for r in valid]):.6f} | {100*med([r['target_gap_fraction'] for r in valid]):+.4f}% | {med([r['seconds'] for r in valid]):.4f} | {[(r['accepts'],r['rejects']) for r in valid]} | {[r['numeric_rebuilds'] for r in valid]} | {sum(r['cap_hit'] for r in valid)}/3 |")
    lines += ['', '## Late-stage Ladybug-539 diagnostic', '',
        'The registered activation rule selected Ladybug-539 because its guard-off calibration encountered negative curvature after the practical targets. Nine fresh runs continued to stall or the 15-second/600-iteration cap. These timings are **time to termination**, not fixed time to equal quality, and are excluded from the speed ranking.', '',
        '| Arm | Time to termination | Median final cost | Accepted / rejected per run | Repairs per run |',
        '|---|---:|---:|---|---|']
    for arm in ['off','x4_floor','champion']:
        rr=[r for r in late if r['arm']==arm]
        lines.append(f"| {NAMES[arm]} | {interval([r['seconds'] for r in rr])} | {med([r['cost'] for r in rr]):.9f} | {[(r['accepts'],r['rejects']) for r in rr]} | {[r['numeric_rebuilds'] for r in rr]} |")
    lines += ['',
        'Curvature recovery activated in all three champion repeats, and ×4 recovery in one of its three repeats. Activation locations differ, so this is not a comparison from identical failed Krylov states. The champion terminates sooner at similar endpoint costs in this small diagnostic, but a persistent floor can change when the stall criterion fires. This does not establish a fixed-target speed gain or satisfy the predeclared two-active-instance criterion.', '',
        '| Arm / repeat | Outer | Lambda before | Failed Rayleigh quotient | Lambda after | Simple implemented ×4 directional lower bound |',
        '|---|---:|---:|---:|---:|---:|']
    for e in late_checks:
        lines.append(f"| {e['arm']} / {e['rep']} | {int(e['outer'])} | {e['lambda_used']:.6g} | {e['rayleigh']:.6g} | {e['next_lambda']:.6g} | {e['implemented_x4_bound']:.6g} |")
    lines += ['',
        'The camera-only sufficient bound is negative for these events, including the successful ×4 rebuild. It is sufficient, not necessary: coupled point regularization and recomputation of floating-point factors can restore a usable direction even when this lower bound does not certify it. All observed repair formulas and retained floors match their registered rules.']
    lines += ['', '## Timing scope and limitations','',
        f"Host `{proto['host']}`, GPU `{proto['gpu']}`. Ceres 2.2.0 uses eight CPU threads. GPU and CPU runs were serialized. Native timing includes Prism solver-local setup; external graph setup is separately recorded. Loading, export and independent auditing are excluded. For successful primary cells, adding recorded graph setup yields:",'',
        '| Scene | Prism eta2 | Caspar FP32 | Caspar FP64 | Ceres LM CPU | Ceres Dogleg CPU |','|---|---:|---:|---:|---:|---:|']
    for sc in scenes:
        lines.append('| '+sc+' | '+' | '.join(timing(cell(sc,a),True) for a in arms)+' |')
    early=[x for x in native_checks if not x['hit'] and x['exit_reason']==2]
    lines += ['', '## Caspar stopping and precision diagnostics', '',
        f"Caspar had **{len(early)}** measured misses with exit reason 2 (`CONVERGED_DIAG_EXIT`), indicating its damping-based termination rather than a target hit or exhausted native time. These runs are retained as misses; increasing the time cap alone would not change their declared stopping rule.", '',
        'The audit tolerance compares independent FP64 evaluation to the driver\'s separately computed FP64 `CHECK` value. It does not assert that the native FP32 objective agrees to that tolerance. Maximum observed native-score versus audited-cost relative discrepancies:', '',
        '| Precision | Maximum relative discrepancy |','|---|---:|']
    for arm in ['caspar32','caspar64']:
        lines.append(f"| {NAMES[arm]} | {max(x['native_relative_error'] for x in native_checks if x['arm']==arm):.9g} |")
    if early:
        lines += ['', '| Scene / target | Repeat | Native cost | Audited cost |','|---|---:|---:|---:|']
        for x in early:
            lines.append(f"| {x['scene']} / {x['phase']} | {x['rep']} | {x['native_cost']:.6f} | {x['audited_cost']:.6f} |")
    lines += ['',
        'These are comparisons to frozen, explicitly configured implementations on one host. The extra Ceres arms are CPU baselines, not evidence against all current GPU solvers. No parameters or scene selection were changed after outcomes. Reference endpoints are bounded calibration results, not certified optima. N=3 estimates repeatability on these inputs; it does not establish population certainty.', '',
        'The original champion binary is unchanged. A preflight-only validator bypass was necessary to test guard-off with eta2; failed preliminary attempts and the amendment are retained. Original/derivative compatibility checks passed on the visited Ladybug-49 trajectories; CUDA device sections are byte-identical. The 100-case dense Schur monotonicity/energy-identity test also passed. See [protocol](speed_novelty_protocol.md) and [novelty assessment](curvature_novelty_assessment.md).','',
        'Raw commands, source/binary/input hashes, logs, independently audited compressed states, calibration and frozen targets: `/tmp/prism-speed-novelty/`. Machine-readable result tables: `measure-rows.json`, `measure-summary.json`, `verdict.json`, `repair-validation.json`, `initial-score-check.json`. Rebuild/report scripts are in `bench/build_speed_novelty.py`, `bench/speed_novelty_study.py`, and `bench/report_speed_novelty.py`.','',
        '## Invalid measured runs','']
    failures=[r for r in rows if not r['valid']]
    lines += [f"- {r['artifact']}: {r.get('error')}" for r in failures] or ['None.']
    (REPO/'docs/speed_novelty_results.md').write_text('\n'.join(lines)+'\n')
    fig,axes=plt.subplots(1,3,figsize=(14,4.8),sharey=True)
    colors=['#087e8b','#d95f02','#756bb1','#737373','#bd9e39']
    offsets=np.linspace(-.13,.13,len(arms))
    for ax,sc in zip(axes,scenes):
        cap=proto['selection']['native_caps'][sc]
        for ai,(arm,color) in enumerate(zip(arms,colors)):
            for xi,mult in enumerate(multipliers):
                rr=cell(sc,arm,mult);x=xi+offsets[ai]
                if successful(rr):
                    ts=[r['crossing'] for r in rr];y=med(ts)
                    ax.errorbar(x,y,yerr=[[y-min(ts)],[max(ts)-y]],fmt='o',color=color,capsize=3,
                        label=NAMES[arm] if xi==0 else None,markersize=5)
                else:
                    ax.plot(x,cap,marker='x',color=color,label=NAMES[arm] if xi==0 else None)
                    ax.annotate(f"{sum(r['hit'] for r in rr)}/3",(x,cap),xytext=(0,5+(ai%2)*12),
                        textcoords='offset points',ha='center',fontsize=7,color=color)
        ax.axhline(cap,color='#aaaaaa',ls=':',lw=.8)
        ax.set_title(sc);ax.set_xticks([0,1,2],['0.5%','1%','2%']);ax.set_xlabel('Tolerance above frozen reference cost')
        ax.set_yscale('log');ax.set_ylim(.06,16);ax.grid(axis='y',alpha=.2);ax.set_xlim(-.4,2.4)
    axes[0].set_ylabel('Native time to audited target (seconds)')
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',ncol=5,frameon=False)
    fig.suptitle('Frozen new-instance comparison • N=3 • median and full range',fontsize=13)
    fig.text(.5,.075,'× at cap: fewer than 3/3 target hits; position denotes censoring, not observed time-to-target.',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.12,1,.93])
    dest=REPO/'docs/figures/convergence/frozen_new_instances_time_to_target'
    for ext in ['png','svg','pdf']:
        fig.savefig(str(dest)+'.'+ext,dpi=180,bbox_inches='tight')
    print(json.dumps(findings,indent=2))

if __name__=='__main__':
    main()
