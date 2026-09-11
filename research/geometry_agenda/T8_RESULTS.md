# T8: local prediction works; full-solve transfer does not

The depth-two policy fails the time-to-target gate. No larger RL agent was
trained. This closes this specific feature/action/reward screen, not the
general possibility of useful computation allocation.

Forty independent development parents (depth and clustered families, two
snapshots per seed) were replayed for all six actions, N=3. The ordinary LM
trial is a common cache; additional OCA/curvature RHSs reuse its factors, a
new lambda refactors, and point/coarse updates own complete states. All true
costs, failures and work are retained. The tree uses fractional depth risk
and nonlinear defect, choosing OCA, point polishing or geodesic correction.

On new seeds its local log-gap-decrease/time score is 97.1% of the hindsight
oracle on depth states and 98.3% on clustered states. On the entirely unseen
rotation family it is 88.4%, below the deterministic rule's 94.7% and fixed
OCA's 96.2%. This oracle bounds the measured one-action utility, not total
time to converge. It knows outcomes unavailable at deployment.

## Complete solves, N=3

Times include preparation, extra work, feature extraction and inference.
Ratios are ordinary-schedule time / arm time; larger is faster. Synthetic
rows are medians of ten paired seed medians; real rows are single fixed
samples with three timing repetitions.

| Held-out cohort | Learned tree | Deterministic rule | Fixed extra lambda/3 | Tree target hits |
|---|---:|---:|---:|---:|
| Depth, new seeds | 0.980x | 0.698x | 0.868x | 30/30 |
| Cluster, new seeds | 0.885x | 0.573x | 1.112x | 30/30 |
| Rotation, unseen generator | 0.861x | 0.873x | 1.152x | 30/30 |
| Ladybug49 sample, unseen real family | 1.048x | 0.978x | 1.339x | 3/3 |
| Dubrovnik88 sample, unseen real family | 1.016x | 1.093x | 1.379x | 3/3 |
| Venice52 sample, unseen real family | 0.968x | 0.972x | 1.553x | 3/3 |

Tree features/inference consume 8–12% on synthetic cohorts and about 5% on
real samples. At target crossing it has one depth seed with point NRMSE>.15
versus ordinary's two, and no rotation/cluster failures. These are not full
refinement geometry guarantees. Fixed extra lambda has one rotation geometry
failure and a depth timing regression: its real-sample result is an engineering
lead, not a generally superior solver or native Eta2/Caspar comparison.

Always-coarse misses nine of thirty depth targets, with nine of ten depth
seeds failing geometry; it is much slower on rotation and real samples.
Twenty-seven coarse attempts have degenerate automatic metrics and use the
ordinary fallback. Failed work is charged, and no parent is dropped. An
initially uncaught instance aborted replay; the preserved log and correction
are documented in the protocol. The policy was not retuned on held-out data.

The local score does not reliably rank full-run strategies. On cluster
snapshots fixed OCA captures 99.1% of the oracle, yet its full solve runs at
0.993x ordinary; fixed extra lambda captures 89.5% locally and runs at 1.112x.
This motivates studying longer returns, but does not establish that sequential
learning will beat a simpler schedule. Transferable speed advantage is absent,
so the conditional RL experiment was not launched.

[A Game of Bundle Adjustment](https://arxiv.org/html/2308.13270), section 3,
already learns damping with SAC and a reward containing negative iteration
seconds plus a terminal bonus. The possible distinction here is allocation
among different computations, with charged features and family transfer.
A good offline label score alone does not establish novelty.

Reproduce `check_allocation.py`, `t8_replay.py --split development`, then
`--split held_out`, then `run_t8.py`. The tree, forty development and sixty-six
held-out NPZ parents, hashes, 1,908 action replays, and 792 complete runs are
retained. Rotation and the three BAL families were excluded from training.
