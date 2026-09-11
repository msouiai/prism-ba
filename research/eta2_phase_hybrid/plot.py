#!/usr/bin/env python3
"""Empirical target attainment; misses stay in the denominator."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

P = Path(__file__).resolve().parent
rows = json.loads((P / 'large-results.json').read_text())
fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.3), sharey=True)
colors = {'champion': '#1464a5', 'menu_feedback': '#c75427'}
labels = {'champion': 'Eta2', 'menu_feedback': 'Opening menu + shift feedback'}
for ax, scene in zip(axes, ['final-3068', 'final-4585']):
    for arm in colors:
        rr = [r for r in rows if r['scene'] == scene and r['arm'] == arm]
        times = sorted(r['target_seconds'] for r in rr if r['hit'])
        assert len(rr) == 10
        ax.step([0, *times, 15], [0, *[i / len(rr) for i in range(1, len(times) + 1)], len(times) / len(rr)],
                where='post', color=colors[arm], linewidth=2.3,
                label=f"{labels[arm]} ({len(times)}/10)")
    target = next(r['target'] for r in rows if r['scene'] == scene)
    ax.set_title(f"{scene.title()}\nIdentical objective target: {target:,.2f}", fontsize=11)
    ax.set(xlim=(0, 15), ylim=(-.02, 1.04), xlabel='Native seconds')
    ax.grid(alpha=.22)
    ax.legend(loc='upper left', fontsize=8.5)
axes[0].set_ylabel('Fraction of all runs reaching target')
fig.suptitle('Eta2 remains ahead in the bounded opening-menu test', fontsize=13)
fig.text(.5, .015, 'N=10 per arm and scene; 15 s / 600-outer budget. FTOL and budget misses remain misses.\n'
         'Same host and binary; hybrid hands over after 8 accepted steps. No Caspar arm in this study.',
         ha='center', fontsize=8.3)
fig.tight_layout(rect=(0, .10, 1, .94))
out = P / 'figures'
out.mkdir(exist_ok=True)
fig.savefig(out / 'large_target_attainment.png', dpi=180)
fig.savefig(out / 'large_target_attainment.pdf')
