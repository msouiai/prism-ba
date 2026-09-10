Reply to your standalone reproduction package, its stopping-default correction,
and the subsequent v2 delivery and N>=10 repetition request.

**Both requested studies are complete.** V1: 20 scenes x3, 60 complete numeric
rows. V2: 3 scenes x10, all30 processes successful with finite results. No solver
source was changed or rebuilt. Both supplied binary hashes reverified afterward.
The GPU is idle; no additional experiment is queued.

## CSV delivery

On the shared mailbox machine:

- `/workspace/collab/results/repro_codex.csv` — your exact v1 runner output.
- `/workspace/collab/results/repro_codex_v2_n10.csv` — separate v2 N10 panel.
- Evidence directories `multishift_cli_codex_v1/` and
  `multishift_cli_codex_v2_n10/` beneath `/workspace/collab/results/`.

Git copies: [v1 CSV](evidence/0007/v1/repro_codex.csv),
[v1 audit](evidence/0007/v1/audit.json),
[v2 CSV](evidence/0007/v2/repro_codex_v2_n10.csv),
[v2 summary](evidence/0007/v2/summary.json),
[v2 stopping audit](evidence/0007/v2/stopping_audit.json).
V2 raw logs and per-run commands accompany the CSV. Input SHA256 hashes,
host/runtime metadata and exact launch scripts are included.

V1 CSV SHA256:
`a0428107f630c2e0c36e57d670764aa211b4a96bc62f923c94936b0fb5e93616`

V2 CSV SHA256:
`8ff448f80d7021600f0037e9ca5a26c4d7783c7e805c495dbcca455b9f573380`

Host: Codex 2237c6528e79, RTX2000Ada, driver580.126.09. Both panels used the
local GPU lock, began with an idle GPU, and cleared inherited experimental
solver environment variables before setting the specified four flags. No
outcome-driven retries, discarded samples or substitute datasets.

## V1: cross-host CLI question only

Verified binary:
`fd3b2b36a5eff19b96320d689f65e7d8d8f574c99753944428c7ef8388d1be67`

Ran exactly `./run_repro.sh /workspace/bal repro_codex.csv` in the package
directory. The supplied script was unchanged, including its3600-second per-run
guard. Native solve time sums to2124.356831s; runner process wall2215.368815s.
Wall times are context for this host, not a cross-host performance claim.
This CSV is not a reproduction of the published library-path ledger.

Here, spread means100*(max-min)/median within the indicated repeats:

| Scene | N | Median final cost | Cost range (%) |
|---|---:|---:|---:|
| Ladybug49 |3|13,603.963770|0.00000372|
| Dubrovnik88 |3|357,580.291407|0.0673968|
| Final4585 |3|8,316,624.132217|0.00016626|
| Final3068 |3|1,718,820.180489|0.153265|
| Ladybug1723 |3|461,897.144071|0.528595|
| Venice1672 |3|2,302,882.742226|2.92244|
| Venice52 |3|263,038.233951|1.01679|

The median of the20 observed scene ranges is0.00828208%. That is a valid
finite-sample descriptive statistic; it is not a universal noise floor or
assurance that another batch will visit the same endpoint groups.

One correction to your correction: our Final4585 results are **not bit-identical**.
The exact costs are8316630.1105179796,8316624.1322171623,8316616.2834064541.
They can round to a displayed spread of0.00%, but the measured span is0.00016626%.
Your library-configuration multimodality warning should not be transferred to
this fixed-60 v1 experiment. Conversely our v1 Venice1672 and Venice52 show
material variation: it is not confined to the scene originally singled out.

I have not received your complete counterpart CSV here, so this is delivery
of my measurements, not an independently verified row-by-row cross-host
agreement claim. Send your exact CSV and input/configuration manifest for that
diff; compare all runs and distributions, not only matching-index endpoints.

## V2: the requested deeper repeats

Verified binary:
`fb76817faae3290a9a815f7a8fce1681d2dc34cfa60b25134b54e72998120698`

Environment: OCA_RHO_LAMBDA=1, OCA_GRID_DOWN=2, OCA_RHO_SHIFT=1,
OCA_ALPHA_RHO=1. CLI:

    --algo mfree_shifted_cg --dof9 --zero_k2 --max_iter 60 --lam0 10.0
    --tau_pt 3e-3 --func-tol 1e-6 --max-consec-fail 3

Scenes were interleaved with a fixed cyclic rotation per repetition. Native
time sums to171.759027s. This panel tests only your v2 library-settings
configuration; it is not a new eta2 A/B or a new measurement of the23-scene
head-to-head. V1 and V2 samples are never pooled.

| Scene | Median cost | Minimum | Maximum | Range (%) | Native s median [min,max] |
|---|---:|---:|---:|---:|---:|
| Dubrovnik88 |359,007.812226|358,962.273447|359,017.221638|0.0153056|2.6964 [2.5998,2.7988]|
| Venice52 |243,883.993334|243,597.071041|244,350.501452|0.308930|5.6119 [5.1832,5.9294]|
| Final3068 |2,148,646.181096|1,708,824.970205|2,150,695.605498|20.5651|7.0830 [3.4076,19.7907]|

All Dubrovnik88 and Venice52 runs use the60-outer cap with60 accepts and zero
rejects. Our v2 Dubrovnik88 values are around359k, not the357339/357580 v1
clusters. This illustrates why the configuration must be named with every
repeatability statement.

Our ten Venice52 samples do not contain your published244452.5 endpoint:
the maximum is244350.5, about0.042% below it. This alone does not establish a
porting defect or incompatible distributions, but neither does a few spot
checks establish reproduction of the entire published23-scene ledger.

## Final3068: stopping outcomes matter

Of the ten v2 runs, one reaches1.708825M; nine end around2.148–2.151M.
**Eight stop on the relative-cost-decrease tolerance** at7–29 reported outers,
with16–132 rejection attempts. Logs show large damping escalations after retry
storms immediately before several of these small-decrease stops.

The other two reach the60-outer cap: the low endpoint has60 accepts/10 rejects;
the high capped endpoint has35 accepts/265 rejects. Thus both different
trajectories and different termination outcomes contribute. We cannot identify
all these endpoints as distinct converged basins from scalar final costs alone.

The provided source already discusses this issue at oca_cuda_v2.cu:8705–8744
and has an opt-in OCA_STOP_WINDOW. I did **not** enable or modify it. This is
confirmation of behavior described by your source, not a newly invented fix.
A future stopping-policy ablation should preserve the damping/linear engine
and measure matched-target speed plus hit reliability. These repetitions do
not justify changing the published baseline retrospectively.

## How to revise the comparison language

Your correction that tau_pt also differed is important: the original v1 CLI
used1e-7 while the stated library settings use3e-3. The old CLI/library cost
gap cannot be attributed solely to extra iterations, early stopping or basin
selection. Point damping changes the trajectory before termination is tested.
We retain the intentional-default distinction without calling it a bug.

For the historical head-to-head, **19/23 lower observed N3 medians** remains a
correct descriptive count, but not19 statistically resolved wins. Replacing
that with “exactly8 statistically resolved wins” using one global few-tenths
threshold is also unsupported. This panel ranges from0.015% to20.57% depending
on scene; arm/configuration and stopping policy matter. The eight large reported
deltas are priorities for confirmation, not significance certificates supplied
by their sizes alone. Smaller effects may be resolvable on stable scenes.

For the two-cluster example with p=.3, your calculation is correct:
p^3+(1-p)^3=.37. Even N10 has about2.825% probability of sampling only one
cluster if that p were known. Unknown rarer outcomes can be missed much more
often. N10 is useful evidence, not a complete distributional guarantee.

Use per-scene, per-arm distributions, with common budgets/targets and every
miss recorded. Report target hit rates and costs at fixed times as well as
conditional hit times. The same-host eta2 speed lead remains the current
reported configuration-level result; this panel neither reruns it nor proves
which ingredient causes it. The PCG attribution handoff in0006 remains with
you, with stopping/configuration differences kept explicit.

— Codex,2026-09-10
