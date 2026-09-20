#!/usr/bin/env python3
"""Publish the bounded model/precision investigation from retained raw records."""
import json
import math
import pathlib
import re
import statistics as st

ROOT=pathlib.Path('/workspace/prism-model-followup')
REPO=pathlib.Path(__file__).resolve().parents[1]
SCENES=['ladybug-1723','final-1936','trafalgar-126','final-4585']
LABELS={'candidate':'Prism + numerical guard','champion':'Frozen champion','caspar32':'Caspar FP32','caspar64':'Caspar FP64'}
def read(name):return json.loads((ROOT/name).read_text())
def cell(rows):
    hits=[r['crossing'] for r in rows if r['hit']]
    if len(hits)!=len(rows):return f'{len(hits)}/{len(rows)} hits'
    return f'{st.median(hits):.3f} [{min(hits):.3f}, {max(hits):.3f}]'
def table(rows,scenes,arms):
    lines=['| Scene | '+' | '.join(LABELS[a]+' (s)' for a in arms)+' |', '|---|'+'---:|'*len(arms)]
    for s in scenes:lines.append('| '+s+' | '+' | '.join(cell([r for r in rows if r['scene']==s and r['arm']==a]) for a in arms)+' |')
    return '\n'.join(lines)

def main():
    pairs=read('final-caspar-pairs/results.json');assert len(pairs)==36
    assert all(r['returncode']==0 and r['audit_error']<1e-7 for r in pairs)
    # Validate actual candidate trajectories, including repaired linear systems.
    validations=[]
    for row in pairs:
        if row['arm']!='candidate':continue
        p=ROOT/'final-caspar-pairs'/f'{row["scene"]}-candidate-{row["rep"]}.log'
        log=p.read_text();repairs=[];last_floor=1e-16
        for l in log.splitlines():
            if l.startswith('NUMERIC_REPAIR o='):
                v={k:float(x) for k,x in re.findall(r'(\w+)=([^ ]+)',l)}
                assert v['next_lambda']>v['lambda'] and v['next_lambda']>=last_floor
                lower=v['rayleigh']+v['next_lambda']-v['lambda'];assert lower>0
                repairs.append(dict(v,directional_lower_bound=lower));last_floor=v['next_lambda']
            elif l.startswith('CLASSICAL_LM o='):
                v={k:float(x) for k,x in re.findall(r'(\w+)=([^ ]+)',l)}
                assert v['lambda']==v['tau'] and v['lambda']>=last_floor*(1-1e-12)
                if v['accept']:assert v['rho']>.1 and v['prediction']>0
            elif l.startswith('ATTR_RADIUS o='):
                v={k:float(x) for k,x in re.findall(r'(\w+)=([^ ]+)',l)}
                if v['accept']:assert v['norm']<=v['radius']*(1+1e-8)
        assert len(repairs)==row['numeric_rebuilds']
        validations.append(dict(scene=row['scene'],rep=row['rep'],repairs=repairs))
    (ROOT/'trajectory-validation.json').write_text(json.dumps(validations,indent=2)+'\n')
    internal=read('numeric-guard-pairs/results.json');double=read('double-screen/results.json')
    tighter=read('sensitivity-halfpct-prism/results.json');assert len(tighter)==6
    off=read('flag-off-check/results.json');assert len(off)==2
    assert all(r['returncode']==0 and r['audit_error']<1e-7 for r in tighter+off)
    assert all(r['hit'] and r['accepts']==4 and r['matvecs']==22 and r['numeric_rebuilds']==0 for r in off)
    assert abs(off[0]['cost']-off[1]['cost'])/off[0]['cost']<1e-12
    model=read('model-analysis-final.json');math_check=read('math-check.json');assert math_check['all_passed']
    protocol=read('final-caspar-pairs/protocol.json')
    ratios={}
    for s in SCENES:
        groups={a:[r for r in pairs if r['scene']==s and r['arm']==a] for a in ['candidate','caspar32','caspar64']}
        ratios[s]={a:st.median(r['crossing'] for r in groups[a])/st.median(r['crossing'] for r in groups['candidate']) for a in ['caspar32','caspar64'] if all(r['hit'] for r in groups[a]+groups['candidate'])}
    geo={a:math.exp(st.mean(math.log(v[a]) for v in ratios.values() if a in v)) for a in ['caspar32','caspar64'] if any(a in v for v in ratios.values())}
    evidence=dict(final_pairs=read('final-caspar-pairs/summary.json'),speed_ratios=ratios,geomean_on_complete_scenes=geo,trajectory_validations=len(validations),math_cases=math_check['cases'],maximum_endpoint_audit_error=max(r['audit_error'] for r in pairs),tighter_prism=read('sensitivity-halfpct-prism/summary.json'),flag_off_checked=True,excluded_tighter_caspar=read('sensitivity-halfpct/audit-discrepancy.json'))
    (ROOT/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    target_table='\n'.join(f'| {s} | {protocol["scenes"][s]["anchor"]:.6f} | {protocol["scenes"][s]["target"]:.6f} | {protocol["scenes"][s]["cap"]} |' for s in SCENES)
    quality_table='\n'.join(f'| {s} | {LABELS[a]} | {st.median(r["cost"] for r in pairs if r["scene"]==s and r["arm"]==a):,.3f} |' for s in SCENES for a in ['candidate','caspar32','caspar64'])
    negative=[r for r in model if 'curvature' in r]
    curvature_table='\n'.join(f'| {r["metadata"]["outer"]} | {r["curvature"]["stored_pap"]:.6f} | {r["curvature"]["true_schur_energy"]:.6f} | {r["curvature"]["point_stationarity_relative"]:.3f} |' for r in negative)
    failed=[r for r in model if r.get('rho',1)<0]
    curve_table='\n'.join(f'| {r["scene"]}, outer {r["metadata"]["outer"]} | {r["top_one_percent_tracks_error_share"]*100:.2f}% | {r["probes"]["residual_curve"]["alpha"]:.4f} | {r["probes"]["half"]["cost"]:,.3f} | {r["probes"]["residual_curve"]["cost"]:,.3f} |' for r in failed)
    text=f'''# Corrected champion comparison and Schur numerical repair

The leading candidate is the frozen coupled-radius champion with `OCA_SCHUR_NUMERIC_GUARD=1`. The change repairs numerically nonpositive Schur directions by increasing **both camera and point damping** and restarting the linear solve at the same state. It retains FP32 fragment storage, FP64 state/arithmetic/acceptance, Hcc PCG, and the incumbent point safeguard. It introduces no multishift menu or residual Hessian.

The current four-scene, three-repeat results are below. These are fresh same-host pairs using the optimized implementation, not the original five-shift executable mistakenly used in the earlier Ladybug comparison. Every endpoint was scored independently on the original FP64 observations. Production defaults were not changed.

{table(pairs,SCENES,['candidate','caspar32','caspar64'])}

Entries are median [minimum, maximum] seconds; hit counts replace medians when any repeat misses. No finite speed ratio is assigned to a miss. Exact per-scene speed ratios and the geometric mean over **only jointly reached scenes** are in [evidence.json](/workspace/prism-model-followup/evidence.json). The FP32 common subset is particularly small and should not be presented as a broad benchmark average. Three executions are three repeats, not three independent datasets.

**Protocol and endpoint quality.** Host: `{protocol['host']}`, RTX 2000 Ada 16 GB, one GPU process at a time under `/tmp/prism_gpu.lock`. The primary threshold is 1.01 times a historical quality anchor, fixed before testing this change. Ladybug's anchor is a retained audited Caspar FP64 endpoint; the other anchors are prior fixed benchmark targets. They are not certified optimal values. This convention implements a quality tolerance, rather than requiring a specific solver's final fractional-percent refinement.

| Scene | Historical anchor | Common target | Native cap, s |
|---|---:|---:|---:|
{target_table}

All arms use their driver's 600-iteration limit as a secondary bound. Prism counts accepted outer steps while Caspar counts attempted iterations; those caps are not identical work budgets. The native wall cap and common target are the comparison criteria. Numerical rebuilds are counted separately from nonlinear rejects and all their work is inside the timer. Export and independent CPU audits are outside it. Prism includes solver-local allocation/setup; Caspar excludes graph setup, which is separately retained in each result. Input parsing is excluded. This is the pinned standalone Caspar backend, not a full COLMAP reconstruction run.

Caspar FP32 uses a native stop threshold 0.1% below the common target as an empirical rounding margin; only the independent FP64 endpoint qualifies a hit. This margin is not a numerical certificate. Caspar FP32's Ladybug native cost and raw-observation audit differ substantially: the fast termination is not an equal-quality solve. The modest Trafalgar miss at the primary threshold should not be described as a meaningful quality failure; the separate relaxed target below checks that sensitivity.

| Scene | Solver | Median independently audited endpoint cost |
|---|---|---:|
{quality_table}

The complete [final pair records](/workspace/prism-model-followup/final-caspar-pairs/results.json) retain all repeats, misses, endpoints, counters, native and process clocks, setup times, input/binary/state hashes and exact commands. The largest endpoint audit discrepancy is {evidence['maximum_endpoint_audit_error']:.3g} relative, below the 1e-7 validation limit.

**What changed relative to the actual champion.**

{table(internal,SCENES[:3],['champion','candidate'])}

In this matched development batch the original Ladybug arm missed all three targets; the repaired arm reached all three with one numerical rebuild and one nonlinear reject each. It used 18 accepted steps in every run. The Final-1936 and Trafalgar trajectories did not trigger the guard, and their speed differences are small. Across other retained baseline batches Ladybug occasionally reached the target, so the finding is improved observed reliability, not that the unguarded solver can never reach it. Final-4585 was held out for this change; the rule and constants were frozen before that validation, and the guard did not activate before its target.

**The quadratic problem was numerically inconsistent.** Two saved Ladybug PCG directions had negative curvature in the stored Schur operator. Rebuilding the point elimination from original FP64 Jacobians gave positive curvature for the same camera direction and damping:

| Captured outer | Stored pᵀAp | Original-Jacobian Schur energy | Stored point-equation relative residual |
|---|---:|---:|---:|
{curvature_table}

The independent reconstruction computes energy as a sum of squares plus damping, rather than subtracting nearly cancelling camera and eliminated-point energies. The rebuilt point solve's backward error is recorded in [model-analysis-final.json](/workspace/prism-model-followup/model-analysis-final.json). Hcc, rounded cross blocks and rounded point Jacobians need not form one coherent positive-semidefinite Gram matrix. Subtractive Schur evaluation and very small damping can then expose spurious negative curvature. FP64 fragments alone also eventually encounter the limits of tiny damping and did not fix the full trajectory; the measurements do not establish rounding as the only cause of every stall.

The bounded FP64-fragment experiment was rejected: its Ladybug arm missed all three targets, while Final-1936 changed from median 0.565 s to 0.681 s, about 21% slower. See [double-screen/results.json](/workspace/prism-model-followup/double-screen/results.json). Merely doubling fragment storage is not the selected fix.

**Why the new repair is mathematically justified.** With fixed Hcc scaling E and frozen stored blocks, write

\\[
A(\\lambda)=E[B-W(C+\\lambda D_p)^{{-1}}W^T]E+\\lambda I.
\\]

For positive point damping and lambda′ ≥ lambda,

\\[
A(\\lambda')-A(\\lambda)\\succeq(\\lambda'-\\lambda)I.
\\]

This monotonicity does not require the rounded blocks to be one exact Gram matrix. For a failed direction p, let q = pᵀA(lambda)p / pᵀp. The prototype chooses lambda′ = 4 max(lambda, lambda − q), subject to numerical limits. For q ≤ 0 this gives a strictly positive lower bound q + lambda′ − lambda on the repaired direction's Rayleigh quotient. The point factors and reduced RHS are rebuilt; the incompatible CG basis is discarded. No nonlinear candidate is accepted on the strength of this bound.

This is a directional guarantee for the frozen algebra in exact arithmetic, not a certificate for every direction or for floating-point factorizations. The next solve is checked again. The observed regularization floor is retained for the remainder of the solve, which avoids dropping immediately back into the problematic range but can overregularize later states. A 32-rebuild limit and the native time cap bound the extra work. All true-cost, positive-prediction, rho > 0.1, and camera-radius acceptance checks remain active.

The [independent dense check](/workspace/prism-ba/bench/check_schur_numeric_guard.py) passed 100 deliberately inconsistent block problems, checking monotonicity, the failed-direction bound and the coherent sum-of-squares identity. All 12 final candidate runs also passed coupled-damping, acceptance, radius and rebuild-accounting checks in [trajectory-validation.json](/workspace/prism-model-followup/trajectory-validation.json). A separate [flag-off check](/workspace/prism-model-followup/flag-off-check/results.json) matched the original Final-1936 control's four accepts, 22 products and audited cost. GPU atomic reductions prevent a general byte-for-byte repeatability claim; this checks the visited disabled path. This is a numerical safeguard for a BA-specific implementation; these tests do not establish a new trust-region convergence theorem or publication novelty.

**The residual-curve model was tested on saved real BA directions.** Let v=Jd and e=r(x⊕d)−r−v. The proposed residual interpolant r+alpha v+alpha²e matches the current and evaluated residual and the derivative at zero. Its squared norm is a quartic, so a scalar cubic gives candidate contractions without another global linear solve. Full nonlinear costs were recomputed on each suggested ray point.

| Saved failed direction | Top 1% of tracks' absolute model-error share | Curve alpha | Half-step cost | Curve-step cost |
|---|---:|---:|---:|---:|
{curve_table}

The two Ladybug proposals improve immediate cost slightly over a half step; the Trafalgar proposal is worse. All three half steps already pass the strict gain-ratio test, so these samples demonstrate no saved cost evaluations or linear retries. The quartic is therefore retained as an offline prototype, not added to the winning solver. Whole-track concentration supports investigating selective point corrections later, but it does not prove they will be faster.

Analytic directional derivatives were checked at a step-size ladder. Ladybug's very small finite-difference steps suffer cancellation: the best tested discrepancies are approximately 7e-5 and 3e-4 on its failed directions; Trafalgar checks reach approximately 1e-8 or better. The exact residual-defect identity closes near floating-point reduction error. These are fixed-state diagnostics, not evidence for a higher-order convergence rate.

**Where remaining time goes.** A separate instrumented Final-1936 run charged approximately 0.169 s to assembly, 0.132 s to point preparation/RHS, 0.147 s to Krylov work and 0.029 s to candidate scoring. It had four accepts and zero rejects. These categories do not include every part of the solver clock and should not be normalized as an exhaustive GPU profile. On this fast trajectory, eliminating nonlinear rejection work would save nothing. The next execution experiment should target assembly/point-preparation traffic or fuse actual-cost and full-step-model evaluation, with the current candidate as control.

**Target sensitivity.** A separately declared 2% threshold was tested before the repair: on Ladybug, the original champion took median 0.232 s [0.231, 0.240] versus Caspar FP64 0.607 s [0.606, 0.608]. On Trafalgar, it took 0.126 s versus Caspar FP32 1.091 s and FP64 0.676 s. See [sensitivity-2pct/results.json](/workspace/prism-model-followup/sensitivity-2pct/results.json). This explains why a statement that Prism is simply slower was too broad. The primary 1% target was not changed to rescue a failing candidate.

At the tighter 0.5% Ladybug target (450,435.095625), the repaired solver reached 3/3 in median 0.657 s [0.643, 0.726]; the matched original missed 3/3. Each repaired run still needed only one numerical rebuild. The retained floor therefore did not prevent this tighter accuracy in the tested runs. See [tighter Prism comparison](/workspace/prism-model-followup/sensitivity-halfpct-prism/results.json).

The initial tighter-target Caspar run failed the predeclared checker-agreement threshold: reported cost 450,394.444 versus independent FP64 exported-state cost 450,394.343, relative difference 2.25e-7. Long-double evaluation of that state gave 450,394.169, exposing sensitivity to arithmetic order near projection singularities. All are below the target, and the difference is negligible for practical quality, but the validation threshold was not relaxed after seeing the result. That partial side comparison was retained and excluded from speed claims; the Prism-only three-repeat tighter check was then completed. [Audit discrepancy](/workspace/prism-model-followup/sensitivity-halfpct/audit-discrepancy.json). The 36-run primary comparison passed its checks and is unaffected.

**Code and reproduction.**

- [Candidate source and binary](/workspace/prism-model-followup/candidate/manifest.json), binary SHA256 `117773562d33949cdbfdc27905d1f23a2cc1faedb7f77c3e619c17caa50a86dc`.
- [Builder](/workspace/prism-ba/bench/build_model_followup.py), [target harness](/workspace/prism-ba/bench/current_champion_targets.py), [capture helper](/workspace/prism-ba/gpu/model_followup_capture.cuh), [model analysis](/workspace/prism-ba/bench/analyze_model_followup.py).
- [Frozen builds archive](/workspace/prism-model-followup/frozen-builds.tar.gz) contains the verified parent, diagnostic, FP64 ablation and selected candidate source/headers/binaries. [Captured states and directions](/workspace/prism-model-followup/model-captures.tar.gz) preserve the inputs to the CPU checks.
- [Final protocol](/workspace/prism-model-followup/final-caspar-pairs/protocol.json) records fixed inputs, targets, flags and binary hashes. Each individual manifest contains the exact standalone command.

Run the candidate with the parent selected flags, `OCA_SCHUR_NUMERIC_GUARD=1`, `--lam0 0.1`, `--dof9 --zero_k2 --mf-no-alpha`, and an explicit target/time cap. The current code is an isolated research build; the repository's production solver defaults and unrelated working-tree edits were preserved. The literature motivation and broader alternatives are in [TR model research](tr_model_research.md); the new claims in this report rest on the local experiments above.
'''
    (REPO/'docs/model_followup_results.md').write_text(text)
    (ROOT/'REPORT.md').write_text(text)
    selected=json.loads(pathlib.Path('/workspace/prism-controller-attribution/selected_candidate.json').read_text())
    selected.update(arm='coupled_radius_numeric_guard',binary_sha256='117773562d33949cdbfdc27905d1f23a2cc1faedb7f77c3e619c17caa50a86dc',binary=str(ROOT/'candidate/prism-tr'),scope='Research leader on this four-scene 1%-tolerant panel; directional Schur damping repair, FP32 fragments, FP64 arithmetic/state/acceptance. No production default change. Further independent scenes and tighter-target behavior remain unproven.')
    selected.pop('binary_in_archive',None);selected['flags']['OCA_SCHUR_NUMERIC_GUARD']='1'
    (ROOT/'selected_candidate.json').write_text(json.dumps(selected,indent=2)+'\n')
    print(json.dumps(evidence,indent=2))

if __name__=='__main__':main()
