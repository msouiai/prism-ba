#!/usr/bin/env python3
import json,math,pathlib,statistics
ROOT=pathlib.Path('/tmp/prism-ba-accuracy');REPO=pathlib.Path('/workspace/prism-ba')
def read(n):return json.loads((ROOT/n).read_text())
def table(rows,quality=False):
 lines=['| Scene | Lambda | Quality | Arm | Hits | Target seconds median [min,max] | Audited cost | Outers | Rejects | Matvecs |',
 '|---|---:|---|---|---:|---:|---:|---:|---:|---:|']
 for s,l,q,a in dict.fromkeys((r['scene'],r['lambda0'],r.get('quality','primary'),r['arm']) for r in rows):
  rr=[r for r in rows if (r['scene'],r['lambda0'],r.get('quality','primary'),r['arm'])==(s,l,q,a)]
  vs=[r['target_seconds'] for r in rr if r['hit']];tm=f'{statistics.median(vs):.4f} [{min(vs):.4f}, {max(vs):.4f}]' if vs else 'MISS'
  if vs and len(vs)<len(rr):tm+=' (hits only)'
  vals=[statistics.median(r[k] for r in rr) for k in ['audit_cost','outers','rejects','matvecs']]
  lines.append(f'| {s} | {l} | {q} | {a} | {len(vs)}/{len(rr)} | {tm} | {vals[0]:.3f} | {vals[1]:g} | {vals[2]:g} | {vals[3]:g} |')
 return lines
def main():
 sel=read('selection.json');v=read('transfer-verdict.json');large=(ROOT/'large-verdict.json').exists()
 train=read('train-rows.json');transfer=read('transfer-rows.json')
 runs=[json.loads(p.read_text()) for p in (ROOT/'runs').glob('*/result.json')]
 metrics=dict(runs=len(runs),native_seconds=sum(r['seconds'] for r in runs),maximum_audit_error=max(r['audit_error'] for r in runs),transfer_hits=sum(r['hit'] for r in transfer),transfer_runs=len(transfer))
 (ROOT/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
 lines=['# BA-specific accuracy and damping pilot','',
 '**Verdict: '+('medium transfer passes the registered gate; see largest-scene verification below.' if v['extend'] else 'retain the sustained eta2 champion; the selected rule failed the registered transfer gate.')+'**','',
 f"Selected from development only: `{sel['selected']}`. Transfer geometric speedup versus champion: "+(f"{v['geometric_speedup']:.4f}x." if v['geometric_speedup'] else 'withheld because a target was missed.'),'',
 '## Mechanism and mathematical limits','',
 'At fixed geometry, the full gradient g=(bc,bp) is independent of damping. The reduced camera RHS bc-W(V+lambda Dp)^-1bp changes with lambda. Using consecutive reduced norms to set CG accuracy therefore mixes geometric progress with the change in the eliminated point system. This is an exact algebraic observation, not proof that the existing forcing is suboptimal on every scene.','',
 'The prototype uses a fixed initial normalization for the camera and point gradient norms, costing two extra GPU reductions per new assembly. This is a progress signal only: the true CG residual check remains in the solver coordinate system. It is not invariant to arbitrary within-block reparameterization.','',
 'The model variant places a sqrt(abs(1-rho)) floor on forcing accuracy. The joint variant also limits accepted lambda decay using that discrepancy. These mappings are explicitly heuristic. Full model prediction and true cost are used for rho, but discrepancy does not certify the error of an inexact damped solve. All radius, rejection, numeric repair and acceptance safeguards are preserved.','',
 'Interpretation after transfer: removing lambda dependence does not necessarily improve the forcing signal. With exact point back-substitution, the full damped linear residual is (camera Schur residual,0). Full-gradient progress includes point components eliminated by that solve. Replacing reduced progress by a normalized full gradient can discard useful information about the camera problem. This is a structural explanation to investigate, not a causal ablation proving why each timing changed.','',
 '## Prior art and novelty assessment','',
 '[Eisenstat and Walker](https://users.wpi.edu/~walker/Papers/forcing_terms%2CSISC_17%2C1996%2C16-32.pdf) established adaptive forcing; [large-scale BA already uses inexact Newton methods](https://www.microsoft.com/en-us/research/publication/bundle-adjustment-in-the-large/). Full-gradient forcing and model-discrepancy feedback should not be presented as new general concepts. This pilot tests their implementation and coupling in Prism, with established controls retained. Neither a new formula nor a speedup alone establishes algorithmic novelty.','',
 'For an ideal SPD quadratic A, the unclaimed damped model improvement is 0.5*e^T*A^-1*e, where e=A*d+g. A certified lower eigenvalue bound would upper-bound this quantity; the smallest explored Ritz value is generally not such a bound. Clipping and mixed-precision assembly further prevent treating a simple spectral heuristic as a certificate. No convergence theorem for this implementation is claimed.','',
 '## Development comparisons','',
 'N3 per arm/scene/initialization. Original = prior reduced-norm heuristic; champion = sustained multiplier2; constant = eta0.5; reduced-ew2 = safeguarded EW2 with forcing held through retries; gradient-ew2 substitutes the normalized full gradient; model adds discrepancy; joint additionally modifies accepted damping decay. These are not all single-factor ablations: reduced-ew2 also changes retry history versus original.','']+table(train)
 lines+=['','Selection losses are mean log median-time ratios versus champion, with a missed run penalized at4*cap. No transfer outcomes enter selection.','',
 '| Arm | Penalized development score, higher is better |','|---|---:|']
 for a,x in sel['log_losses'].items():lines.append(f'| {a} | {math.exp(-x):.4f}x |')
 lines+=['','These penalty-derived ratios are not measured speedups when a target is missed. Lambda10 is a stress setting, not the global champion initialization; successes against a failed stress comparator do not establish deployment gains.','',
 'Leave-family-out selection diagnostic: `'+json.dumps(sel['family_holdout'],sort_keys=True)+'`.','',
 '## Frozen transfer at two quality targets','',
 'Initial lambda0.1 for all arms, including Muell. The baseline is the new global eta2 champion, not the older scene-specific initialization map. All targets were registered before this sweep. Transfer scenes were excluded from rule selection, but were familiar from previous research; these are not pristine holdouts.','']+table(transfer)
 if large:
  lv=read('large-verdict.json');lines+=['','## Largest-scene verification','',json.dumps(lv),'']+table(read('large-rows.json'))
 else:lines+=['','Largest-scene extension was not run because the medium transfer gate failed. No new Caspar comparison is claimed.','',
  'At primary targets, joint requires241 vs195 matvecs on Trafalgar,20 vs16 on Final1936, and1024 vs980 on Muell. Thus the regressions are accompanied by extra linear work, not just the two added reductions. At tighter targets it uses340 vs455 on Trafalgar and22 vs33 on Final1936. All three arms miss the tighter Muell target within12s, so no six-setting aggregate speedup is assigned.','',
  'A more targeted follow-up would compare consecutive reduced gradients at the same reference damping and camera metric, using a counterfactual point elimination at the new geometry. That would separate geometric progress from damping changes while retaining camera-space relevance. It requires extra point-factor/RHS work and has NOT been implemented or validated in this pilot.']
 lines+=['','## Verification and artifacts','',
 f"{metrics['runs']} independently audited endpoints; native solver total {metrics['native_seconds']:.3f}s; maximum relative reported/audited discrepancy {metrics['maximum_audit_error']:.3g}. N3 parent/new off and champion smoke checks preserve work counts and costs within1e-7. CPU tests verify forcing safeguards, retry idempotence, accepted-only damping updates, lambda dependence of the Schur RHS, and the exact block residual identity on a toy system.",'',
 'Native target times include new reductions and control work; exclude input loading, state export and CPU audits. A hit requires both an actual target event within cap and an original-observation CPU FP64 endpoint at or below target. No interpolation. Same RTX2000 Ada host2237c6528e79; SIMPLE_RADIAL, k2fixed0, half-sum squared original residuals.','',
 '[Registered protocol](ba_accuracy_protocol.md). Code: `gpu/ba_accuracy.h`, `bench/build_ba_accuracy.py`, `bench/ba_accuracy_study.py`, `bench/report_ba_accuracy.py`. Full source/build, hashes, manifests, traces and endpoints: `/tmp/prism-ba-accuracy`. Production defaults unchanged.']
 text='\n'.join(lines)+'\n';(ROOT/'RESULTS.md').write_text(text);(REPO/'docs/ba_accuracy_results.md').write_text(text)
 print(json.dumps(dict(selection=sel['selected'],transfer=v,large=read('large-verdict.json') if large else None,metrics=metrics),indent=2))
if __name__=='__main__':main()
