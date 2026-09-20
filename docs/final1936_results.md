# New large-scene comparison: final-1936 — 2026-09-07

Dataset: 1,936 cameras, 649,673 points, 5,213,733 observations, from the
[official BAL Final collection](https://grail.cs.washington.edu/projects/bal/final.html).
The scene was selected before seeing results and was absent from the earlier
local collection. The frozen compact mode-2 FP64 solver and selected rearm-only
policy transfer without retuning. Guarded single uses the same infrastructure
with one lambda; Caspar uses the same frozen FP32 default solver as earlier.

N=1 per method, 30-second native solve budget; 180-second process timeout after
GPU lock. CPU raw-z FP64 checks every endpoint. Overbudget candidates cannot
commit; return time may overshoot. Native clocks handle setup as documented in
[the fixed-policy study](fixed_policy_validation.md); this is not equal
end-to-end latency. PRISM FP64/raw-z and Caspar FP32/epsilon-guarded projection
remain different internal numerical models. Default solver settings unchanged.

| Method | CPU final cost (lower better) | Native solve s | Overshoot s | Accepted | Rejected | Sampled GPU MiB |
|---|---:|---:|---:|---:|---:|---:|
| selected | 5,049,606.000 | 20.428 | 0.000 | 17 | 0 | 1980 |
| single | 5,049,621.209 | 23.910 | 0.000 | 27 | 0 | 1918 |
| caspar32 | 5,052,932.941 | 25.621 | 0.000 | 122 | 76 | 1084 |

At the tested budget, selected multi cost vs Caspar: -0.066%;
single vs Caspar: -0.066%;
selected multi vs single: -0.000%.
All three methods stopped before the budget: both PRISM runs met the configured
relative-improvement stopping condition, and Caspar reached its damping exit
limit. Thus these native runtimes measure their respective stopping rules,
not a shared time-to-quality threshold.

These are endpoint differences, not speedup ratios. N=1 gives no dispersion
estimate and cannot establish universal algorithm superiority.

Multi made 1249 matvecs, scored 335 candidates,
and rearmed 0 times; single made 1449 matvecs
and scored 288 candidates. Work counts include unfinished
overbudget attempts. PRISM CPU/GPU endpoint discrepancies:
2.03e-15 (multi), 4.06e-15 (single).
Caspar native/CPU final discrepancy: 0.001998%;
float-converted initial-state discrepancy: 0.000010%.
Caspar exit reason 2, budget guard fired: False.
Exit reason 0 is MAX_ITERATIONS (also retained by budget guard), 1 is score
threshold, 2 is damping-limit exit. A damping exit is not proof of optimality.
Caspar setup 0.642 s; whole driver process
29.074 s (parsing/checks included). GPU values are sampled,
not allocator-certified peaks. No extra repetitions or tuning were performed.

Artifacts: `/workspace/prism-final1936/`, including protocol, frozen binary and
source, manifests, results, logs, exact PRISM state exports, and GPU samples.
Input SHA256: `46e039c2a5f5715f48450ca74bce19bf4d1b26ac6daf2c14bf188508b0e39313`.
Reproduction command (the root must contain the frozen binary and selection):

```sh
python3 bench/memory_screen.py largest --root /workspace/prism-final1936 --mode 2 --scene final-1936
```

The driver gained an optional scene argument; its prior defaults remain intact.
Python compilation and git diff checks pass. Broad queue stays paused. Changes
and results are local, not pushed.
