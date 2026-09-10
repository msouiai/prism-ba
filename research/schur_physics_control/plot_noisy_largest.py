#!/usr/bin/env python3
"""Summarize all registered seeds and plot measured accepted-state staircases."""
import argparse
import csv
import json
import math
import pathlib
import statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument('--data', type=pathlib.Path, default=pathlib.Path('/tmp/prism-schur-physics-noise'))
args = ap.parse_args()
rows = json.loads((args.data/'runs.json').read_text())
completion = json.loads((args.data/'completion.json').read_text())
assert completion['complete'] and len(rows) == 12
assert len({(r['case']['seed'], r['case']['requested_sample_median_px'], r['rank']) for r in rows}) == 12
target = rows[0]['target']
curves = []
for row in rows:
    with (args.data/row['csv']).open() as f:
        trace = list(csv.DictReader(line for line in f if not line.startswith('#')))
    points = [{'iteration': int(r['iter']), 'seconds_after_setup': float(r['wall_s']),
               'cost': float(r['cost'])} for r in trace]
    assert all(math.isfinite(p['cost']) and p['cost'] > 0 for p in points)
    assert all(b['seconds_after_setup'] >= a['seconds_after_setup'] for a, b in zip(points, points[1:]))
    assert abs(points[-1]['cost']/row['final_cost']-1) < 1e-7
    curves.append({'seed': row['case']['seed'], 'pixels': row['case']['requested_sample_median_px'],
                   'rank': row['rank'], 'points': points})
with (ROOT/'noise_curves.csv').open('w') as f:
    w = csv.DictWriter(f, fieldnames=['seed', 'pixels', 'rank', 'iteration', 'seconds_after_setup', 'cost'], lineterminator='\n')
    w.writeheader()
    for curve in curves:
        for p in curve['points']:
            w.writerow({k: v for k, v in curve.items() if k != 'points'} | p)

plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'savefig.dpi': 180})
for target_view in [False, True]:
    fig, axes = plt.subplots(2, 3, figsize=(13.8, 7.8), sharex=True)
    for li, pixels in enumerate([.25, 1.]):
        for si, seed in enumerate([17, 29, 43]):
            ax = axes[li, si]
            for rank, color, style, label in [(0, '#1967a3', '-', 'Eta2 incumbent'), (16, '#ec8a23', '--', 'Eta2 + rank16 correction')]:
                curve = next(c for c in curves if (c['seed'], c['pixels'], c['rank']) == (seed, pixels, rank))
                row = next(r for r in rows if (r['case']['seed'], r['case']['requested_sample_median_px'], r['rank']) == (seed, pixels, rank))
                x = [p['seconds_after_setup'] for p in curve['points']]
                scale = target if target_view else curve['points'][0]['cost']
                y = [p['cost']/scale for p in curve['points']]
                ax.step(x, y, where='post', color=color, linestyle=style, linewidth=2.1, label=label)
                ax.scatter(x[-1], y[-1], color=color, s=22, marker='o' if rank == 0 else 'x', zorder=4)
            pair = [r for r in rows if r['case']['seed'] == seed and r['case']['requested_sample_median_px'] == pixels]
            active = next(r['coarse_active'] for r in pair if r['rank'] == 16)
            hit = sum(r['hit_within_budget'] for r in pair)
            ax.axhline(1 if target_view else target/scale, color='#777', linewidth=.8, linestyle=':')
            ax.set(yscale='log' if target_view else 'linear', title=f'{pixels:g} px median noise · seed {seed}', xlim=(0, 13))
            if target_view:
                ax.set_ylim(bottom=.75)
            else:
                ax.set_ylim(0, 1.08)
            ax.grid(alpha=.2)
            ax.text(.03, .07, f'Target hits: {hit}/2\nActive coarse solves: {active}', transform=ax.transAxes,
                    ha='left', va='bottom', fontsize=9, bbox={'facecolor': 'white', 'alpha': .85, 'edgecolor': 'none'})
            if si == 0:
                ax.set_ylabel('Objective / fixed target (log scale)' if target_view else 'Objective / starting objective')
            if li == 1:
                ax.set_xlabel('Logged solver time after setup (s)')
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(.5, .94), ncol=2, frameon=False)
    fig.suptitle('Final13682: recovery from initialization noise', y=.985, fontsize=17)
    fig.subplots_adjust(left=.075, right=.985, bottom=.16, top=.85, hspace=.30, wspace=.25)
    fig.text(.5, .045, 'Three independent noise seeds per level; one run per arm per input. Observations and intrinsics unchanged.\n'
             '12 s native cap; recorded states only. The CSV clock excludes setup; native target times are reported separately.',
             ha='center', fontsize=9, color='#444')
    folder = ROOT/'figures/convergence'
    folder.mkdir(exist_ok=True, parents=True)
    for ext in ['png', 'pdf', 'svg']:
        path = folder/f"final13682_initialization_noise{'_target' if target_view else ''}.{ext}"
        fig.savefig(path, bbox_inches='tight')
        if ext == 'svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    plt.close(fig)

groups = []
for pixels in [.25, 1.]:
    for rank in [0, 16]:
        rr = [r for r in rows if r['case']['requested_sample_median_px'] == pixels and r['rank'] == rank]
        hits = [r for r in rr if r['hit_within_budget']]
        groups.append({'pixels': pixels, 'rank': rank, 'runs': len(rr), 'hits': len(hits),
                       'median_hit_seconds': statistics.median(r['target_seconds'] for r in hits) if hits else None,
                       'median_final_cost': statistics.median(r['final_cost'] for r in rr),
                       'total_rejects': sum(r['rejects'] for r in rr),
                       'total_active_coarse_solves': sum(r['coarse_active'] for r in rr)})
summary = {'completion': completion, 'target': target, 'groups': groups,
           'cases': json.loads((args.data/'cases.json').read_text()),
           'clock': 'Curves use unchanged CSV elapsed clock after setup; target statistics use native TARGET clock.',
           'matched_caspar': False}
(ROOT/'noise_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(groups, indent=2))
