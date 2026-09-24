#!/usr/bin/env python3
"""Summarize retry and scoring work alongside the common-cost report."""
import argparse
import json
from pathlib import Path
from statistics import median


def fmt(rows, key):
    values = [row.get(key, 0) for row in rows]
    return f"{median(values):.1f} [{min(values):.1f}, {max(values):.1f}]"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('experiments', nargs='+', type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args()
    lines = ['# Retry and scoring work', '',
             'Values are medians [observed ranges]. Rescues are failed shift menus',
             'accepted by full-step backtracking without rebuilding the system.',
             'Rejects count attempts that still require the original damping ladder.',
             'Total scoring includes menu, original alpha grid, and backtracking.',
             'N below three is incomplete and supports no verdict.', '']
    for directory in args.experiments:
        manifest = json.loads((directory/'preregistered.json').read_text())
        lines += [f'## {directory.name}', '',
                  f"Config {manifest['config']}, outer budget {manifest['max_iter']}.", '',
                  '| Scene | Arm | N | Rejects | Rescues | Backtrack evaluations | Total scoring | Matvecs |',
                  '|---|---|---:|---:|---:|---:|---:|---:|']
        for scene in manifest['scenes']:
            for arm in ['reference', 'optimized']:
                rows = [json.loads(p.read_text()) for p in directory.glob(f'{scene}-{arm}-*.json')]
                if not rows:
                    continue
                fields = [fmt(rows, key) for key in ['rejects', 'backtrack_rescues',
                          'backtrack_evals', 'total_scored', 'matvecs']]
                lines += [f"| {scene} | {arm} | {len(rows)} | " + ' | '.join(fields) + ' |']
        lines += ['']
    args.output.write_text('\n'.join(lines).rstrip()+'\n')


if __name__ == '__main__':
    main()
