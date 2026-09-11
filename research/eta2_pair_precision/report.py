#!/usr/bin/env python3
"""Render the complete registered ledger; no new solver measurements."""
import csv,json,statistics
from pathlib import Path
P=Path(__file__).resolve().parent
def main():
    s=json.loads((P/'summary.json').read_text());a=json.loads((P/'audit.json').read_text())
    ext=json.loads((P/'external-results.json').read_text())
    active=json.loads((P/'active-spectrum.json').read_text())
    assert s['rows']==122 and len(ext)==len(active)==18 and a['passed']
    groups=s['groups'];rows=[json.loads(f.read_text()) for f in sorted((P/'evidence').glob('*/*/result.json'))]
    def get(stage,arm):return next(g for g in groups if g['stage']==stage and g['arm']==arm)
    def interval(m,r,d=3):return f'{m:.{d}f} [{r[0]:.{d}f}, {r[1]:.{d}f}]' if m is not None else '—'
    out=['# Pair restoration and probe precision: completed follow-up',
      '', '**Verdict: retain the frozen Eta2 champion. Neither restoration nor de-clipping passes the registered target gates. FP64 cross blocks remove the measured Venice probe curvature truncation, but do not produce an accepted rescue there.**',
      '', 'Registration: `62a756b`, before implementation or new solver runs. Branch `research/eta2-pair-precision`; original solver and frozen champion untouched. 122 primary native solves plus 18 external-state operator captures. All primary endpoint states were independently scored in CPU FP64. No new Caspar/Ceres timing comparison is implied.',
      '', '## Final3068: target 1744796.9841897595',
      '', '| Arm | Hits | Target seconds: median [min, max], successful runs only | Above-target stop witnesses rescued | Probe accepts | Curvature cutoffs |',
      '|---|---:|---:|---:|---:|---:|']
    for arm in ['original','pair','pair64']:
        g=get('final',arm)
        out.append(f"| {arm} | {g['hits']}/{g['n']} | {interval(g['conditional_seconds'],g['conditional_range'])} | {g['stop_miss_witnesses_rescued']}/{g['stop_miss_witnesses']} | {int(g['probe_accepts'])}/{g['probes']} | {int(g['probe_truncations'])} |")
    out += ['', 'Both candidate conditional medians are below the registered 3.96s limit, but both fail the decisive witness gate: pair restores rescue 0/4 stopping misses; pair64 rescues 0/6. Every successful target crossing happened before its probe. The 6/10 versus 4/10 fresh hit counts are not a causal estimate of precision harm: floating-point trajectories differ before intervention, so those successes cannot be attributed to it.',
      '', 'The pair arm has one curvature truncation and two 512-iteration cap hits among four probes. Pair64 has zero truncations but four 512-iteration cap hits among six probes. Its one accepted probe gains 17.0864 cost units from 1,900,167.3 and ultimately stops near 1,900,147.9, still above target. A 512 cap is a budget, not a certificate of reaching residual 1e-3; actual residuals are retained in every row.',
      '', 'Implementation restores both outgoing lambda and radius from the last accepted ordinary step with relative decrease >1e-4. The numerical floor is preserved, with radius adjusted to keep lambda*R² constant when lambda is clamped. All restored pairs pass this invariant check. The raw camera directions remain 6–835 times the restored radius for the mixed probes and 34–23,013 times for the FP64 probes. Pair restoration therefore does not guarantee that the deeper direction survives clipping at a later state.',
      '', '## Venice52: target 243740.27',
      '', '| Arm | Target hits | Endpoint: median [min, max] | Native endpoint seconds: median [min, max] | Probe accepts | Curvature cutoffs |',
      '|---|---:|---:|---:|---:|---:|']
    for arm in ['original','pair','pair64','declip','declip64']:
        g=get('venice',arm)
        out.append(f"| {arm} | {g['hits']}/{g['n']} | {interval(g['endpoint_median'],g['endpoint_range'],1)} | {interval(g['native_median'],g['native_range'])} | {int(g['probe_accepts'])}/{g['probes']} | {int(g['probe_truncations'])} |")
    out += ['', 'All arms have zero observed hits, so their endpoint times are not time-to-target speed measurements. Small endpoint differences do not make any arm pass. Pair and pair64 can accept tiny late steps (6/10 and 5/10), but none rescues its stopping witness to target.',
      '', 'The precision mechanism is clean: all ten mixed de-clipping probes truncate, while all ten FP64-cross probes complete 83 CG iterations without truncation, with true relative residuals 0.000538–0.000576. Nonetheless all ten FP64 proposals fail acceptance. Their raw camera norm is about 221,440 against radius 12,901 (still about 17.2x clipped). A representative exact full model predicts a positive 304.60 decrease, but no improving true-cost candidate is retained. The logged candidate==current sentinel means no retained improvement, not an independently measured equal-cost rejected trial; the failed trial objective is not logged.',
      '', 'FP64 cross blocks are lazy and probe-only: 74,989,368 extra bytes on Venice52, 357,223,392 on Final3068. Rebuilds, allocation, RHS, products and back-substitution are charged inside native solve time. No precision work is performed before a probe. Point factors remain based on rounded point rows; cross-only precision is not a universal positive-definiteness guarantee.',
      '', '## External trajectory audit: all 18 supplied states',
      '', 'All input SHA256 hashes, dimensions, exact observations and zero-k2 values match the supplied manifest/shared input conventions. The transfer archive SHA256 is `c73caa99310c603596c88c84005a1c0c4181f474172454bc3ee733c66f02f35a`. Every capture uses the input state unchanged, without an optimization update. Damping is fixed to lambda=tau=1e-8, intrinsics prior=1, rather than claiming to reproduce Claude\'s native damping settings.',
      '', 'At every state, all three 468x468 matrices (stored mixed, W64 with stored point factor, W64 with FP64-QR point factor) have zero negative eigenvalues and zero eigenvalues below 1e-14. The full minimum is approximately 1e-8 because 52 frozen k2 coordinates contribute trivial damping-only eigenvalues. The following supplementary active-coordinate audit removes those coordinates; its matrices are unchanged, only the spectral subspace differs.',
      '', '| Snapshot | CPU cost | Active mixed minimum eigenvalue | Active cross-FP64 minimum | Active full-FP64 minimum |',
      '|---|---:|---:|---:|---:|']
    for r in sorted(ext,key=lambda r:(int(r['state'].split('it')[1]),r['state'])):
        ac=next(v for v in active if v['state']==r['state'])
        out.append(f"| {r['state']} | {r['independent_cost']:.4f} | {ac['operators']['stored']['min_eigenvalue']:.8g} | {ac['operators']['W64_Rstored']['min_eigenvalue']:.8g} | {ac['operators']['W64_R64qr']['min_eigenvalue']:.8g} |")
    native_error=max(v['native_product_relative_error'] for r in ext for v in r['operators'].values())
    asymmetry=max(v['symmetry_error'] for r in ext for v in r['operators'].values())
    out += ['', f'Dense products agree with the native captured products to maximum relative discrepancy {native_error:.3g}. The spectra use the symmetric parts; maximum pre-symmetrization entrywise asymmetry is {asymmetry:.3g}. Extended-precision scalar quotients and nonnegative full-Jacobian energies also agree. Since all full minima are damping-only k2 modes here, those minimum-vector scalar checks are trivial; the full/active spectra and nontrivial native-product checks carry the external positivity evidence. The first complete raw capture, all dense matrices/eigenvectors, native logs, product-check results and hashes are preserved. Other raw operator arrays were processed transiently and removed after validation, as registered.',
      '', '**Cost provenance correction:** our prior three actual failed-probe captures were near 248,405, not 246,300. The latter was an eventual endpoint. These delivered states span about 241,618–246,486, so this is a cross-trajectory check, not an exact cost-matched replay of the failed state. Positive mixed operators here agree with Claude\'s no-cutoff observation; they do not contradict the independently confirmed negative mixed operator at our different states.',
      '', 'The prior same-state audit remains the direct precision attribution: holding our state/direction/damping fixed, W32 gives Rayleigh quotients around -0.56e-9 to -2.57e-9, while W64 alone makes them +3.43e-8 to +4.28e-8. Rebuilding point QR alone does not fix them. The dominant cross-rounding error came from two ill-conditioned, two-observation tracks close to a camera. This is not evidence of a real nonlinear saddle: positively damped Gauss–Newton is positive definite in exact consistent arithmetic.',
      '', '## No-regression screen',
      '', '| Scene | Arm | Median endpoint delta vs original | Median native seconds | Median wall delta | Worst paired wall delta | Paired gate fails / N |',
      '|---|---|---:|---:|---:|---:|---:|']
    for scene in ['dubrovnik-88','ladybug-1197']:
        base=next(g for g in groups if g['stage']=='screen' and g['scene']==scene and g['arm']=='original')
        for arm in ['off','pair','pair64','declip64','both64']:
            g=next(g for g in groups if g['stage']=='screen' and g['scene']==scene and g['arm']==arm)
            pairs=[r for r in s['paired_screen'] if r['stage']=='screen' and r['scene']==scene and r['arm']==arm]
            out.append(f"| {scene} | {arm} | {100*(g['endpoint_median']/base['endpoint_median']-1):+.4f}% | {g['native_median']:.4f} | {100*(g['native_median']/base['native_median']-1):+.1f}% | {100*max(r['wall_delta'] for r in pairs):+.1f}% | {sum(r['fail'] for r in pairs)}/{len(pairs)} |")
    out += ['', 'The registered per-pair thresholds are >0.5% endpoint or >20% native-wall regression. These are ordinary-endpoint screens, not equal-quality speed comparisons. Flags-off differences limit causal interpretation: original Ladybug1197 uses 57–59 outers and 2964–3332 products, versus 57–85 outers and 3094–4285 products with the new binary off. Thus extra work from different floating-point trajectories is visible even without a probe. This screen does not isolate pure intervention overhead. Full ranges and individual pairs are in summary.json.',
      '', 'The conditional both64 target panels were not launched: pair64 failed its Final3068 witness gate and declip64 had zero Venice hits. The pre-registered both64 guard screen was still completed. No arm is promoted.',
      '', '## What the measurements separate',
      '', '1. Numerical validity: probe-only W64 repairs the observed false curvature and permits accurate deeper CG on Venice.',
      '2. Linear accuracy versus nonlinear usefulness: reaching residual about 5.6e-4 does not make the proposed retraction acceptable, even when the quadratic model predicts descent.',
      '3. Controller restoration: restoring a previously useful scalar pair neither reconstructs the old state nor guarantees an appropriate radius for the current direction.',
      '', 'Two mathematical limitations explain why neither proposed rescue was guaranteed. First, camera radius limits do not bound the eliminated point step: d_p(alpha)=-V^-1 b_p-alpha V^-1 W^T d_c. The point-only offset remains even as the camera step shrinks. Second, R is measured in the current camera scaling E; restoring an old scalar radius does not transport the old metric when Hcc changes. These are structural observations, not newly measured causes or replacement experiments.',
      '', 'The useful retained asset is the precision diagnosis and reproducible operator audit. The present restoration/de-clipping policies should stay as negative research arms. Do not relax the curvature cutoff, lower the numeric floor, claim a saddle, or count fresh no-probe hits as rescue evidence.',
      '', '## Reproduction and evidence',
      '', f"All {a['rows']} primary rows are valid. Maximum independent endpoint relative discrepancy: {a['max_endpoint_relative_error']:.3g}. All {a['verified_lossless_states']} exported endpoint states have verified lossless compressed copies. Source, binaries, commands, flags and input hashes are recorded. See PROTOCOL.md, README.md, provenance/, audit.json, summary.json, gates.json, external-results.json, active-spectrum.json, and the verified archive pointer in archive.json."]
    (P/'FINDINGS.md').write_text('\n'.join(out)+'\n')
    keys=['stage','scene','arm','rep','target','hit','cost','target_seconds','native_seconds','outers','accepts','rejects','matvecs','stop_reason','cap_hit','audit_relative_error','source']
    with (P/'ledger.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(rows)
    print('Rendered FINDINGS.md and 122-row ledger.csv')
if __name__=='__main__':main()
