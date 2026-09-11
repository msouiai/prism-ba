# Same-target ledger: measured hits and misses

Banked profiles remain separate. Times below are native solve seconds; no time-to-target is assigned to a miss.
Claude-host measurements are not same-host timing comparisons. Successful-run medians are conditional.
Counts describe the available repetitions, not known population success probabilities.

## final-3068

Target: 1744796.9841897595

| Arm | Observed hits | Host / evidence | Endpoint median [range] | Full solve median [range], s | Conditional target time median [range], s |
|---|---:|---|---:|---:|---:|
| Caspar32 default / 200 | 0/3 | Codex / banked | 2,646,874.732 [2,636,053.334, 2,649,434.550] | 0.832 [0.670, 2.350] | — |
| Caspar32 default / 2000 | 0/3 | Codex / banked | 2,646,054.180 [2,645,825.877, 2,649,272.865] | 0.696 [0.673, 0.720] | — |
| Caspar32 paper / 200 | 0/3 | Codex / banked | 2,039,539.249 [2,031,893.930, 2,043,660.955] | 0.772 [0.746, 1.017] | — |
| Caspar32 paper / 2000 | 0/3 | Codex / banked | 2,041,578.800 [2,039,563.115, 2,043,646.650] | 0.761 [0.748, 0.837] | — |
| Ceres dogleg-10000 | 2/3 | Codex / fresh | 1,727,521.767 [1,706,022.362, 1,775,095.884] | 1,131.100 [1,089.697, 2,003.140] | 1,302.743 [686.494, 1,918.991] |
| Ceres lm-10000 | 0/3 | Codex / fresh | 2,183,295.461 [2,183,295.457, 2,183,295.465] | 10.715 [9.931, 11.277] | — |
| Ceres setup control | 0/3 | Codex / separate setup screen | 2,183,295.459 [2,183,295.459, 2,183,295.461] | 11.273 [10.545, 11.474] | — |
| Ceres setup normalize | 0/3 | Codex / separate setup screen | 1,930,209.408 [1,930,209.397, 1,930,209.422] | 10.874 [10.834, 12.115] | — |
| Ceres setup normalize_strict | 0/3 | Codex / separate setup screen | 1,813,919.574 [1,813,901.853, 1,814,053.156] | 60.734 [60.546, 60.763] | — |
| Ceres setup normalize_strict_eta01 | 0/3 | Codex / separate setup screen | 1,810,675.541 [1,810,164.003, 1,811,893.132] | 60.825 [60.291, 60.863] | — |
| Ceres setup strict_stop | 0/3 | Codex / separate setup screen | 1,822,254.768 [1,822,196.209, 1,822,280.095] | 60.906 [60.887, 60.969] | — |
| Eta2 champion | 8/10 | Codex / fresh | 1,742,918.321 [1,726,448.571, 1,822,013.389] | 3.789 [2.890, 5.665] | 3.692 [2.882, 4.270] |
| MFREE base | 0/10 | Claude / collaborator CSV | 2,148,981.703 [2,148,004.074, 2,150,348.481] | 8.811 [4.844, 19.936] | — |
| MFREE deep | 5/10 | Claude / collaborator CSV | 1,925,318.490 [1,703,217.862, 2,144,397.697] | 15.272 [7.206, 16.676] | ≤ 15.694 [14.971, 16.500] (upper bounds) |
| Caspar f64 | reported miss; N unavailable | Claude / original aggregate | ≈ 2,635,100 | unavailable | — |

## final-4585

Target pending completion of the registered Ceres endpoint stage.

| Arm | Observed hits | Host / evidence | Endpoint median [range] | Full solve median [range], s | Conditional target time median [range], s |
|---|---:|---|---:|---:|---:|
| Caspar32 default / 200 | pending (1 runs) | Codex / banked | 11,035,627.091 [11,035,627.091, 11,035,627.091] | 13.972 [13.972, 13.972] | — |
| Caspar32 default / 2000 | pending (1 runs) | Codex / banked | 8,942,006.457 [8,942,006.457, 8,942,006.457] | 128.390 [128.390, 128.390] | — |
| Caspar32 paper / 200 | pending (1 runs) | Codex / banked | 16,932,055.545 [16,932,055.545, 16,932,055.545] | 9.591 [9.591, 9.591] | — |
| Caspar32 paper / 2000 | pending (2 runs) | Codex / banked | 15,800,645.988 [15,420,314.380, 16,180,977.597] | 53.682 [20.375, 86.989] | — |
| Ceres dogleg-10000 | pending (2 runs) | Codex / fresh | 7,998,055.634 [7,690,492.466, 8,305,618.803] | 2,433.279 [2,425.714, 2,440.845] | — |
| Ceres lm-10000 | pending (1 runs) | Codex / fresh | 8,040,781.917 [8,040,781.917, 8,040,781.917] | 67.990 [67.990, 67.990] | — |

Final3068: Eta2 has 8/10 observed hits and a 3.692-second conditional median. MFREE-deep has 5/10 and a 15.694-second median upper bound on crossing time. These samples do not establish a population reliability ranking or a same-host speed ratio.

Ceres dogleg has 2/3 hits at 686.494–1918.991 seconds; its conditional median divided by Eta2’s is about 353 on this host and this frozen configuration. This excludes misses and is not an unconditional speedup. The separate Ceres setup sensitivity experiment tests how dependent that comparison is on the baseline setup.

Any Ceres setup rows are a separate 60-native-second exploratory screen with a new instrumented driver. They keep the same target but are not pooled into the frozen primary Ceres medians. See ceres_setup/PROTOCOL.md and ceres_setup/README.md when available.

Caspar32 endpoint hits are checked with the banked CPU FP64 original-observation score. Its FP32 traces are retained as diagnostics but cannot certify an FP64 crossing. The reported f64 aggregate has no delivered raw repetitions or times; the old table’s 3/3 column belongs to other solvers at a different target.

Sources and limitations: [banked/PROVENANCE.md](banked/PROVENANCE.md). Machine-readable runs and aggregates: same-target-runs.csv, same-target-runs.json, same-target-ledger.json. The primary experiment remains separate in summary.json and runs.csv.
