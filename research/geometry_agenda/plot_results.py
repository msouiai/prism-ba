"""Standalone scientific figures from saved results; no solver runs."""
import json
import pathlib
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT/'figures'/'convergence'; OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                     'pdf.fonttype': 42, 'svg.fonttype': 'none', 'figure.dpi': 130})
COLORS = ['#243746', '#007d79', '#e17c05', '#9854a5', '#cf4446', '#5b8e28']
exports = []

def read(name): return json.loads((ROOT/(name+'.json')).read_text())['rows']

def panel(ax, rows, criteria, arms, title, names=None):
    subset = [r for r in rows if all(r.get(k) == v for k, v in criteria.items())]
    for i, arm in enumerate(arms):
        data = [r for r in subset if r['arm'] == arm]
        assert data, (title, arm)
        times = [r.get('target_seconds') or r['seconds'] for r in data]
        center = int(np.argmin(np.abs(np.array(times)-np.median(times))))
        for j, row in enumerate(data):
            trace = [t for t in row['trace'] if 'cost' in t and np.isfinite(t['cost'])]
            x = np.array([t['seconds'] for t in trace])*1000
            y = np.array([t['cost'] for t in trace])/row['target']
            ax.step(x, y, where='post', color=COLORS[i % len(COLORS)],
                    alpha=1 if j == center else .18, linewidth=1.9 if j == center else 1.,
                    label=(names[i] if names else arm) if j == center else None)
            for t in trace:
                exports.append({'panel': title, 'arm': arm, 'rep': row['rep'], 'seconds': t['seconds'],
                                'cost': t['cost'], 'target': row['target']})
    ax.axhline(1, color='#333333', ls='--', lw=.9, alpha=.65)
    ax.set_yscale('log'); ax.set_title(title, loc='left', fontsize=11)
    ax.set_xlabel('Elapsed CPU time (ms)'); ax.set_ylabel('Original cost / fixed target')
    ax.grid(True, alpha=.15, which='both'); ax.legend(fontsize=8, loc='best')

def save(fig, name, title, footer):
    fig.suptitle(title, fontsize=15, x=.035, ha='left')
    fig.text(.035, .013, footer, fontsize=8, color='#555555')
    fig.tight_layout(rect=[.01, .04, .995, .95])
    fig.savefig(OUT/(name+'.png'), dpi=180)
    fig.savefig(OUT/(name+'.pdf'))
    plt.close(fig)

fig, axes = plt.subplots(2, 3, figsize=(15, 8))
for ax, size, b in zip(axes[0], ['small', 'larger', 'larger'], [4, 4, 16]):
    panel(ax, read('t4_transfer_'+size+'_v2'), {'seed': 300, 'bridges': b},
          ['fine', 'auto-linear', 'auto-nonlinear'],
          ('12 cams / 180 points' if size == 'small' else '30 cams / 900 points')+f', bridges={b}',
          ['Ordinary BA', 'Automatic linear coarse', 'Automatic nonlinear coarse'])
for ax, scene in zip(axes[1], ['ladybug-49', 'dubrovnik-88', 'venice-52']):
    panel(ax, read('t4_real'), {'scene': scene}, ['fine', 'linear', 'nonlinear'], scene+' — fixed sample',
          ['Ordinary BA', 'Automatic linear coarse', 'Automatic nonlinear coarse'])
save(fig, 't4_controlled_and_real', 'T4: controlled collective-mode gains, unsuccessful real transfer',
     'FP64 CPU, fixed intrinsics; setup included. Synthetic seed300 chosen by index. Three repetitions; bold curve is the median-time run. Dashed line: target.')

for name, arms, title in [
    ('t2', ['lm', 'oca', 'geo', 'lambda', 'hybrid'], 'T2: curvature versus damping and recursion'),
    ('t3', ['raw', 'post1', 'post3', 'pre1', 'pre3', 'selective'], 'T3: point relaxation before or after selection'),
    ('t7', ['full', 'manual5', 'manual4', 'pruned'], 'T7: simpler menus beat spectral monitoring')]:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for ax, family in zip(axes, ['depth', 'rotation']):
        panel(ax, read(name+'_held_out'), {'seed': 100, 'family': family}, arms, family+' initialization, seed100')
    save(fig, name+'_mechanism', title,
         'FP64 CPU reference. All work included. Three repetitions; bold: median-time run. Seed100 fixed by index, not by measured gain.')

fig, axes = plt.subplots(2, 2, figsize=(12, 8))
for ax, scenario in zip(axes.flat, ['correct', 'mixed', 'corrupt', 'disconnected']):
    panel(ax, read('t5_held_out'), {'seed': 100, 'scenario': scenario},
          ['fixed', 'ordinary', 'residual', 'information'], scenario+' bridges, seed100')
    ax.set_ylabel('Final robust cost / fixed target')
save(fig, 't5_robust_continuation', 'T5: report false bridges and disconnected geometry alongside successes',
     'All curves use the same final Cauchy loss, including during intermediate stages. Crossing the line before the final scale does not count as a hit.')

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
for ax, baseline in zip(axes, [.1, 1.]):
    panel(ax, read('t6_held_out'), {'seed': 100, 'baseline': baseline},
          ['ordinary', 'depth:0.02', 'depth:0.10', 'isotropic:0.02', 'isotropic:0.10', 'multistart'],
          f'Baseline multiplier {baseline:g}, seed100')
save(fig, 't6_depth_smoothing', 'T6: temporary smoothing must return to the original objective',
     'Displayed original cost can rise during smoothing. Target hits count only at zero radius. All arms share 36 terminal attempts; low cost need not imply correct geometry.')

fig, axes = plt.subplots(2, 3, figsize=(15, 8))
for ax, family in zip(axes.flat, ['depth', 'cluster', 'rotation', 'ladybug-49', 'dubrovnik-88', 'venice-52']):
    panel(ax, read('t8_held_out'), {'family': family, 'seed': 100 if family in ['depth', 'cluster', 'rotation'] else 0},
          ['fresh', 'lambda', 'point', 'rule', 'tree'], family+(' seed100' if family in ['depth', 'cluster', 'rotation'] else ' sample'),
          ['Ordinary schedule', 'Extra damping', 'Point polishing', 'Deterministic rule', 'Learned tree'])
save(fig, 't8_closed_loop', 'T8: local action prediction does not establish faster convergence',
     'Training: depth and cluster development only. Rotation and real families held out. Features/inference charged. CPU reference, not native Eta2 or Caspar.')

with (OUT/'plotted_traces.csv').open('w') as f:
    w = csv.DictWriter(f, fieldnames=list(exports[0])); w.writeheader(); w.writerows(exports)
print('wrote', len(list(OUT.glob('*.png'))), 'figures and', len(exports), 'trace samples')
