#!/usr/bin/env python3
from run_study import *

base.ARMS['menu_feedback']['OCA_PHASE_OPEN_LIMIT'] = '600'
binary = P / 'build_collapse/prism-hybrid'
rows = [run('ladybug-49', 'menu_feedback', rep, 'handover-smoke',
            binary=binary, maxiter=20) for rep in range(3)]
observed = 0
for row in rows:
    text = (P / row['source'] / 'stdout.log').read_text()
    marker = re.search(r'PHASE_HANDOVER outer=(\d+) reason=collapse', text)
    if marker:
        assert re.search(r'PCG_PREP o=\d+', text[marker.end():]), row['source']
        observed += 1
assert observed, 'No genuine collapse followed by PCG was observed; check is inconclusive.'
write(P / 'handover-validation.json', dict(runs=rows, actual_collapse_then_pcg=observed))
