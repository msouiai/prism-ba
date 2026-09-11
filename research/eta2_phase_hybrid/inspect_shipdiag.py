#!/usr/bin/env python3
"""Read delivered data only; never import or execute the upstream study script."""
import hashlib
import json
import re
import statistics
from pathlib import Path

P = Path(__file__).resolve().parent
D = P / 'evidence/claude_shipdiag'
receipt = json.loads((D / 'RECEIPT.json').read_text())
for name, meta in receipt['files'].items():
    assert hashlib.sha256((D / name).read_bytes()).hexdigest() == meta['sha256']

traces = []
for f in sorted(D.glob('sd_*.log')):
    rows = [dict(outer=int(a), checkpoint=int(b), maxrel=float(c), cumulative_rejects=int(d))
            for a, b, c, d in re.findall(r'\[sd\] it=(\d+) ck=(\d+) maxrel=(\S+) nrej=(\d+)', f.read_text())]
    late = [r['maxrel'] for r in rows if r['outer'] >= 20]
    traces.append(dict(file=f.name, observations=len(rows), first=rows[0], last=rows[-1],
                       late_window='outer >= 20, observed fired checkpoints only',
                       late_count=len(late), late_median=statistics.median(late) if late else None,
                       late_min=min(late) if late else None, late_max=max(late) if late else None,
                       rows=rows))

spectral = []
for scene in json.loads((D / 'spectral_study.json').read_text()):
    for phase in ['opening', 'grind']:
        r = scene[phase]
        assert len(r['plain']) == len(r['nystrom']) == 5
        spectral.append(dict(scene=scene['name'], phase_label=phase,
                             max_independent_cg_shared_proxy=max(r['plain']),
                             sum_exact_top50_preconditioned_cg=sum(r['nystrom']),
                             center_exact_top50_preconditioned_cg=r['nystrom'][2]))

out = dict(delivered_hashes_checked=len(receipt['files']),
           upstream_source_binary_verified=False, executed_upstream_script=False,
           gpu_runs=0, traces=traces, spectral=spectral)
(P / 'shipdiag_review.json').write_text(json.dumps(out, indent=2) + '\n')
print('Verified seven delivered file hashes; parsed three traces and six spectral rows. No GPU execution.')
