#!/usr/bin/env python3
"""Portable per-run and per-sweep tables, without successful-run filtering."""
import csv
import json
from pathlib import Path

P = Path(__file__).resolve().parent
rows = [json.loads(f.read_text()) for f in sorted((P / 'evidence').glob('*/*/result.json'))]
scalar_rows = [{k: v for k, v in r.items() if k != 'sweeps'} for r in rows]
sweep_rows = [dict(stage=r['stage'], scene=r['scene'], arm=r['arm'], rep=r['rep'],
                   attempt_index=i, **s)
              for r in rows for i, s in enumerate(r['sweeps'])]
for name, rr in [('runs.csv', scalar_rows), ('sweep_observations.csv', sweep_rows)]:
    with (P / name).open('w') as f:
        writer = csv.DictWriter(f, fieldnames=sorted(set().union(*(r.keys() for r in rr))), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rr)
