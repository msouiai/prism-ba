#!/usr/bin/env python3
"""Render measured rows without converting incomplete evidence into a verdict."""
import json
from pathlib import Path

P = Path(__file__).resolve().parent
summary = json.loads((P / 'summary.json').read_text())
rows = json.loads((P / 'all-results.json').read_text())
counts = {s:sum(r['stage'] == s for r in rows) for s in ['venice', 'storm', 'ceres-storm']}
complete = counts == {'venice':20, 'storm':20, 'ceres-storm':12}
valid = all(r['valid'] for r in rows)
status = 'All registered runs available.' if complete else 'INCOMPLETE: measurements are still in progress.'
lines = ['# Eta2 external coverage and stopping-policy reachability', '', status,
         '', 'Read [FINDINGS.md](FINDINGS.md) for the completed verdict and [SAME_TARGET_LEDGER.md](SAME_TARGET_LEDGER.md) for the combined baseline table.',
         '', f"Available rows: {counts}. All available rows valid: {valid}.", '',
         'The original solver and champion remain unchanged. This is a coverage and stopping-policy experiment, not a new champion selection.', '',
         'The matched local objective is one half the sum of squared reprojection residuals on the original observation set, with a separate focal length and k1 per camera and k2 fixed at zero (SIMPLE_RADIAL). Eta2 stores a nine-coordinate camera block but does not enable --free_k2. This is not the unrestricted two-radial-coefficient BAL model. Caspar32 solves with float data; its ranked endpoint is rescored against the original double observations, as detailed in banked/PROVENANCE.md.', '',
         '## Venice52: fixed target 243740.27', '',
         'The two frozen-binary arms alternate at N=10. Champion keeps its original persistent-flatness stop and 600-outer cap. The diagnostic disables OCA_FTOL, raises the outer cap to 10000 and keeps a 60-native-second allowance. Both stop at the identical target.', '',
         '| Arm | N available | Valid | Hits | Median endpoint | Median native seconds | Median target seconds among hits |',
         '|---|---:|---:|---:|---:|---:|---:|']

def med(r, key):
    value = r.get(key)
    return f"{value['median']:,.6f}" if value else '—'

for r in summary:
    if r['stage'] == 'venice':
        lines.append(f"| {r['arm']} | {r['n']} | {r['valid']} | {r['hits']} | {med(r,'cost')} | {med(r,'native_seconds')} | {med(r,'target_seconds')} |")
lines += ['', 'The banked same-host Ceres LM runs reach this target in 4.9353 seconds median (N=3), at accepted iteration 18. Their 36.7203-second median full solve time is not time-to-target. These banked measurements are not new contemporaneous pairs.', '',
          'Disabling FTOL changes stop-confirmation/backtracking interactions as well as termination. A hit establishes reachability within 1% of the stated Ceres reference; it does not establish the exact Ceres endpoint. A bounded miss does not prove mathematical unreachability.', '',
          'Claude supplied six MFREE endpoint rows: plain 300-outer median 241637.513 in 30.035 seconds; deep-retry median 241619.703 in 30.104 seconds. Those are collaborator endpoint summaries without crossing traces or exported states, not locally audited target-time measurements.', '',
          '## Ceres storm coverage and Eta2 fixed targets', '',
          'Ceres uses the exact banked binary: LM iterative Schur / Schur-Jacobi and dogleg sparse Schur / SuiteSparse, radius 10000, eight threads, 600 iterations, 3600 process seconds, N=3 per profile and scene. Eta2 uses 60 native seconds and 600 outers, N=10. Targets are frozen after each scene has a complete Ceres endpoint stage and before any corresponding Eta2 run, at 1.01 times the lower valid profile median.', '',
          '| Scene | Arm | N available | Valid | Target hits | Median endpoint | Median native seconds | Median target seconds among hits |',
          '|---|---|---:|---:|---:|---:|---:|---:|']
for r in summary:
    if r['stage'] in ['ceres-storm', 'storm']:
        hits = 'unregistered' if r['hits'] is None else r['hits']
        lines.append(f"| {r['scene']} | {r['arm']} | {r['n']} | {r['valid']} | {hits} | {med(r,'cost')} | {med(r,'native_seconds')} | {med(r,'target_seconds')} |")
probe_rows = [r for r in summary if r['stage'] == 'venice-probes']
if probe_rows:
    lines += ['', '### Exploratory Venice follow-up', '',
              'Two probes were registered after the first primary misses, N=3 each, 600 outers /60 seconds. These change the trajectory from initialization and do not replace the champion.', '',
              '| Arm | N available | Valid | Hits | Median endpoint | Median target seconds among hits |',
              '|---|---:|---:|---:|---:|---:|']
    for r in probe_rows:
        lines.append(f"| {r['arm']} | {r['n']} | {r['valid']} | {r['hits']} | {med(r,'cost')} | {med(r,'target_seconds')} |")
    lines += ['', 'probe_relaxed_ftol changes FTOL to1e-7; probe_tighter_forcing disables FTOL and changes the forcing multiplier from2 to0.1. See PROBE_PROTOCOL.md.']
lines += ['', 'The [combined same-target ledger](SAME_TARGET_LEDGER.md) adds every available frozen Caspar32 profile/cap, including misses and full solve times, plus Claude’s MFREE CSV and explicitly incomplete f64 aggregate provenance. Host, endpoint audit, repetition count and crossing-time upper bounds remain labeled separately.', '',
          'Target times use accepted Ceres callback states, without interpolation; rejected trial objectives are excluded. Timing among successful runs is conditional when any repetitions miss. Endpoints at unlike stops are not interchangeable with matched-target convergence speed. Iteration caps and termination reasons are in runs.csv and the raw logs.', '',
          '## Claim scope and evidence', '',
          'The earlier Eta2 three-instance ledger supports fastest among the measured implementations on that panel. Strict endpoint domination of Caspar32 and a universal fastest-BA claim are not supported. See CLAIM_AUDIT.md for the exact table and a counterexample to strict endpoint domination.', '',
          'The older paused 37/48 sweep tests different A/B/C/D configurations, not Eta2, and remains paused by explicit decision. Optional MegBA integration requires a matched objective adapter and target/state instrumentation; it was inspected, not benchmarked. See EXTERNAL_GPU_FEASIBILITY.md.', '',
          'The host is RTX 2000 Ada with an AMD EPYC 9354 CPU and a 6.8-core container CPU quota. CPU and GPU measurements are serialized. Native solve seconds exclude input loading and endpoint audit; setup/process seconds remain available separately where the frozen drivers expose them.', '',
          'Reproduction: PROTOCOL.md, ORDER_NOTE.md, ORDER_NOTE_2.md, run_ceres.py, run_eta2.py and run_ready_storm.py. The second ordering note lets Final3068 run once its own baseline is complete; its target rule is unchanged. Evidence: provenance/, evidence/, runs.csv, all-results.json, summary.json, storm-targets.json when registered. Verification: audit.py. Figures: plot.py. No solver-source modification is part of this experiment.', '']
(P / 'README.md').write_text('\n'.join(lines))
print(status, counts)
