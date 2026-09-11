#!/usr/bin/env python3
import json
from pathlib import Path
import csv
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

P = Path(__file__).resolve().parent
rows = json.loads((P / 'all-results.json').read_text())
out = P / 'figures'
out.mkdir(exist_ok=True)
colors = {'champion': '#1764a0', 'stop_disabled': '#bb502c',
          'lm-10000': '#59933b', 'dogleg-10000': '#89569e'}

ven = [r for r in rows if r['stage'] == 'venice' and r['valid']]
if ven:
    fig, ax = plt.subplots(figsize=(8.4, 4.7))
    for arm in ['champion', 'stop_disabled']:
        group = [r for r in ven if r['arm'] == arm]
        for i, r in enumerate(group):
            with (P / r['source'] / 'curve.csv').open() as f:
                trace = list(csv.DictReader(line for line in f if not line.startswith('#')))
            # CSV starts after initial solver allocations. Anchor hits to the
            # native TARGET timestamp. For misses, endpoint-native alignment
            # also includes final tail work, so it conservatively delays them.
            anchor = r['target_seconds'] if r['hit'] else r['native_seconds']
            offset = max(0., anchor - float(trace[-1]['wall_s']))
            ax.plot([float(t['wall_s']) + offset for t in trace], [float(t['cost']) for t in trace],
                    color=colors[arm], alpha=.5, linewidth=1.2,
                    label=f"{arm}: {sum(v['hit'] for v in group)}/{len(group)} hits" if i == 0 else None)
    for i, path in enumerate(sorted((P / 'provenance').glob('venice-52-ceres-lm-10000-600-*.log'))):
        trace = [(float(t), float(c)) for _, c, t, a in re.findall(
            r'TRACE iter=(\d+) cost=(\S+) seconds=(\S+) accepted=(\d+)', path.read_text()) if int(a)]
        ax.plot([t for t, _ in trace], [c for _, c in trace], color=colors['lm-10000'],
                linestyle='--', alpha=.65, linewidth=1.2,
                label='Ceres LM (banked same-host runs, N=3)' if i == 0 else None)
    ax.axhline(243740.27, color='#333333', linestyle='--', label='Registered 1% target')
    ax.axhline(241326.95669747482, color='#59933b', linestyle=':', label='Banked Ceres LM endpoint')
    ax.set(xlim=(0, 60), ylim=(240500, 265000), xlabel='Native seconds', ylabel='Original-observation L2 cost',
           title='Venice52: stopping-policy reachability (objective zoom)')
    ax.grid(alpha=.2)
    ax.legend(fontsize=8)
    fig.text(.5, .01, 'Eta2 traces aligned to native TARGET time or, for misses, conservatively to endpoint time.\n'
             'Ceres curves are banked accepted callback states. See TIMING.md.', ha='center', fontsize=7)
    fig.tight_layout(rect=(0, .055, 1, 1))
    fig.savefig(out / 'venice_reachability.png', dpi=180)
    fig.savefig(out / 'venice_reachability.pdf')
    plt.close(fig)

storm = [r for r in rows if r['stage'] in ['storm', 'ceres-storm'] and r.get('target') is not None]
if storm:
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.6), sharey=True)
    for ax, scene in zip(axes, ['final-3068', 'final-4585']):
        for arm in ['champion', 'lm-10000', 'dogleg-10000']:
            group = [r for r in storm if r['scene'] == scene and r['arm'] == arm]
            if not group:
                continue
            times = sorted(r['target_seconds'] for r in group if r['valid'] and r['hit'])
            ax.step([.01, *times, 3600], [0, *[(i + 1) / len(group) for i in range(len(times))], len(times) / len(group)],
                    where='post', color=colors[arm], linewidth=2,
                    label=f"{arm}: {len(times)}/{len(group)}")
        ref = next((r['target'] for r in storm if r['scene'] == scene), None)
        ax.set(xscale='log', xlim=(.01, 3600), ylim=(-.02, 1.04), xlabel='Native seconds (log scale)',
               title=f"{scene}\nIdentical target: {ref:,.2f}" if ref else scene)
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    axes[0].set_ylabel('Fraction of all runs reaching target')
    fig.text(.5, .02, 'Eta2: 60 s / 600 outers, N=10. Ceres: 3600 s process cap / 600 iterations, N=3.\n'
             'Different maximum allowances are explicit; misses remain in each arm denominator.', ha='center', fontsize=8)
    fig.tight_layout(rect=(0, .1, 1, 1))
    fig.savefig(out / 'storm_target_attainment.png', dpi=180)
    fig.savefig(out / 'storm_target_attainment.pdf')
    plt.close(fig)
