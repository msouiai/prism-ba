#!/usr/bin/env python3
"""Report the separate setup screen, including every attempted run."""
import json
from pathlib import Path
import statistics

P=Path(__file__).resolve().parent
rows=[json.loads(f.read_text()) for f in sorted((P/'evidence').glob('*/result.json'))]
reg=json.loads((P/'registration.json').read_text())
lines=['# Ceres setup sensitivity on Final3068','',
 'This is a separate comparator screen, not a replacement of the original registered Ceres results. The original Eta2 champion and target are unchanged.','',
 f"Fixed target: {reg['target']!r}. Complete records: {len(rows)}/15. N=3 per arm; 600 iterations and 60 native seconds.",'',
 '| Arm | Completed | Valid | Hits | Endpoint median [range] | Full solve median [range], s | Conditional crossing median [range], s |',
 '|---|---:|---:|---:|---:|---:|---:|']

def fmt(v):
    return f'{statistics.median(v):,.3f} [{min(v):,.3f}, {max(v):,.3f}]' if v else '—'

for arm in reg['arms']:
    rr=[r for r in rows if r['arm']==arm]
    valid=[r for r in rr if r['valid']]
    hits=[r for r in valid if r['hit']]
    lines.append(f"| {arm} | {len(rr)}/3 | {len(valid)} | {len(hits)} | {fmt([r['cost'] for r in valid])} | {fmt([r['native_seconds'] for r in valid])} | {fmt([r['target_seconds'] for r in hits])} |")
lines += ['',
 'All arms use LM / ITERATIVE_SCHUR / SCHUR_JACOBI, radius 10000 and eight threads. control reproduces the old minimal options. normalize changes world coordinates by a similarity; strict_stop sets gradient, function and parameter stopping tolerances to 1e-16; normalize_strict combines them; normalize_strict_eta01 also uses inner eta=.01 instead of .1.', '',
 'Normalization preserves the intended reprojection objective, as checked before solving and after converting endpoints back to original coordinates. It can still change damping, conditioning, numerical errors and the parameter-norm stopping test. It is not a pure stopping intervention. Stricter tolerances and inner accuracy are likewise kept as separately labeled arms.', '',
 'The three new control runs must reproduce the old LM endpoint regime to within .1% before other arms start. See control-validation.json. The native target callback uses accepted states only, and successful endpoints are independently rescored against original observations in FP64. A target event after the 60-second allowance does not count as a hit.', '',
 'The [Ceres 2.2 BAL example](https://github.com/ceres-solver/ceres-solver/blob/2.2.0/examples/bundle_adjuster.cc) motivated this screen. These five settings do not establish globally optimal tuning of Ceres. The screen was registered after the primary Final3068 stage; there is no held-out baseline-selection claim.', '',
 'Reproduction and provenance: PROTOCOL.md, registration.json, run.py, build-manifest.json, evidence/. Independent verification of exported states and the frozen Ceres shared-library dependencies: audit.py and audit.json after completion.', '']
(P/'README.md').write_text('\n'.join(lines))
print(f'Setup report: {len(rows)}/15 records')
