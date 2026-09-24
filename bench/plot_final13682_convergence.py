#!/usr/bin/env python3
"""Plot measured curves and independently audited endpoints for Final-13682."""
import argparse
import csv
import json
import math
import pathlib
import re
import shutil
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, FuncFormatter, MultipleLocator

ARMS = ['rayleigh', 'off', 'caspar32', 'caspar64']
LABELS = {'rayleigh': 'Prism · current guard', 'off': 'Prism · guard off',
          'caspar32': 'Caspar FP32', 'caspar64': 'Caspar FP64'}
COLORS = {'rayleigh': '#087f5b', 'off': '#426eb4',
          'caspar32': '#ce7612', 'caspar64': '#99479e'}
STYLES = {'rayleigh': '-', 'off': (0, (5, 3)), 'caspar32': '-', 'caspar64': '-'}


def parse_trace(root, row):
    stem = root/pathlib.Path(row['artifact']).name
    log = stem.with_suffix('.log').read_text()
    arm = row['arm']
    samples = []
    offset = None
    if arm.startswith('caspar'):
        initial = float(re.search(r'^INITIAL score=(\S+)', log, re.M)[1])
        samples.append(dict(iteration=0, elapsed_s=0., cost=initial, event='initial'))
        trace = re.findall(r'TRACE iter=(\d+) cost=(\S+) seconds=(\S+) accepted=(\d+) pcg=(\d+)', log)
        assert len(trace) == row['outers']
        for iteration, cost, sec, accepted, pcg in trace:
            samples.append(dict(iteration=int(iteration)+1, elapsed_s=float(sec), cost=float(cost),
                                event='accepted' if int(accepted) else 'rejected'))
    else:
        with stem.with_suffix('.csv').open() as f:
            raw = list(csv.DictReader(line for line in f if not line.startswith('#')))
        assert len(raw) >= 2
        # CsvRow() and TargetReached() are adjacent in the frozen source.
        # Their clocks have different origins. Align the last CSV sample to
        # the same-run TARGET event; this retains the final fflush delay in
        # the intermediate timestamps (a conservative shift, not removed work).
        endpoint_time = row['crossing'] if row['crossing'] is not None else row['seconds']
        offset = endpoint_time - float(raw[-1]['wall_s'])
        assert offset >= 0
        if row['crossing'] is not None:
            assert int(raw[-1]['iter']) == int(re.search(r'TARGET reached outer=(\d+)', log)[1])
        assert math.isclose(float(raw[-1]['cost']), row['reported'], rel_tol=1e-12)
        samples.append(dict(iteration=0, elapsed_s=0., cost=float(raw[0]['cost']), event='initial'))
        for r in raw:
            samples.append(dict(iteration=int(r['iter']), elapsed_s=float(r['wall_s'])+offset,
                                cost=float(r['cost']), csv_wall_s=float(r['wall_s']),
                                event='setup_complete' if int(r['iter']) == 0 else 'outer_complete'))
        # The separate JSON diagnostic omits the final target-reaching step.
        # Confirm the saved intermediate costs agree with the complete CSV.
        jrows = json.loads(stem.with_suffix('.jsonl').read_text())['iters']
        for j in jrows:
            matching = [s for s in samples if s['iteration'] == j['outer']]
            assert any(math.isclose(s['cost'], j['cost'], rel_tol=1e-10) for s in matching)
    for sample in samples:
        assert math.isfinite(sample['cost']) and sample['cost'] > 0
        assert math.isfinite(sample['elapsed_s']) and sample['elapsed_s'] >= 0
    for prev, cur in zip(samples, samples[1:]):
        assert cur['elapsed_s'] >= prev['elapsed_s']
        assert cur['cost'] <= prev['cost']*(1+1e-7)
    endpoint_time = row['crossing'] if row['crossing'] is not None else row['seconds']
    assert samples[-1]['elapsed_s'] <= endpoint_time + 1e-4
    return dict(arm=arm, rep=row['rep'], samples=samples,
                csv_to_native_offset_s=offset,
                endpoint_time_s=endpoint_time, audited_cost=row['cost'],
                native_endpoint_cost=samples[-1]['cost'], result=row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=pathlib.Path, default=pathlib.Path('/workspace/prism-final13682-convergence'))
    ap.add_argument('--docs', type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1]/'docs')
    a = ap.parse_args()
    figure_dir = a.docs/'figures'/'convergence'
    rows = json.loads((a.root/'results.json').read_text())
    protocol = json.loads((a.root/'protocol.json').read_text())
    assert len(rows) == 12 and {(r['arm'], r['rep']) for r in rows} == {(k, n) for k in ARMS for n in [1, 2, 3]}
    assert all(r['valid'] and r['hit'] for r in rows), 'Invalid/censored runs require explicit reporting'
    target = protocol['scenes']['final-13682']['target']
    assert all(r['target'] == target and r['scene'] == 'final-13682' for r in rows)
    traces = [parse_trace(a.root, r) for r in rows]
    summary = {}
    for arm in ARMS:
        group = sorted((t for t in traces if t['arm'] == arm), key=lambda t: t['endpoint_time_s'])
        chosen = group[1]
        for t in group:
            t['representative'] = t is chosen
        rr = [t['result'] for t in group]
        summary[arm] = dict(label=LABELS[arm], n=3, hits=3,
                            median_seconds=chosen['endpoint_time_s'],
                            min_seconds=group[0]['endpoint_time_s'], max_seconds=group[-1]['endpoint_time_s'],
                            representative_rep=chosen['rep'],
                            median_audited_cost=statistics.median(r['cost'] for r in rr),
                            accepts=[r['accepts'] for r in rr], rejects=[r['rejects'] for r in rr],
                            numeric_rebuilds=[r['numeric_rebuilds'] for r in rr])
    prism_time = summary['rayleigh']['median_seconds']
    ratios = {arm: summary[arm]['median_seconds']/prism_time for arm in ['caspar32', 'caspar64']}
    output = dict(scene='final-13682', target=target, summary=summary,
                  prism_speedup=ratios, traces=traces)
    (a.root/'curves.json').write_text(json.dumps(output, indent=2)+'\n')
    fields = ['scene', 'arm', 'rep', 'representative', 'iteration', 'elapsed_s', 'cost',
              'cost_kind', 'event', 'csv_wall_s', 'csv_to_native_offset_s']
    with (a.root/'curves.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for t in traces:
            base = dict(scene='final-13682', arm=t['arm'], rep=t['rep'], representative=t['representative'],
                        csv_to_native_offset_s=t['csv_to_native_offset_s'])
            for s in t['samples']:
                writer.writerow(dict(base, **s, cost_kind='native'))
            writer.writerow(dict(base, iteration=t['samples'][-1]['iteration'],
                                 elapsed_s=t['endpoint_time_s'], cost=t['audited_cost'],
                                 cost_kind='independent_fp64', event='audited_endpoint'))

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.labelcolor': '#343a40', 'text.color': '#25313b',
                         'xtick.color': '#46515c', 'ytick.color': '#46515c',
                         'svg.fonttype': 'none', 'pdf.fonttype': 42})
    fig, axes = plt.subplots(1, 2, figsize=(15, 7.2), gridspec_kw={'width_ratios': [1, 1.08]})
    fig.subplots_adjust(left=.075, right=.973, bottom=.255, top=.735, wspace=.235)
    xmax = math.ceil(max(t['endpoint_time_s'] for t in traces)) + 1
    for ax in axes:
        ax.axhspan(0, target/1e6, color='#f0f3f5', zorder=0)
        ax.axhline(target/1e6, color='#59636d', linestyle=(0, (3, 3)), linewidth=1.25, zorder=2)
        ax.set_xlim(0, xmax)
        ax.xaxis.set_major_locator(MultipleLocator(2))
        ax.set_xlabel('Elapsed solver time (seconds)', labelpad=10)
        ax.set_ylabel('Reprojection cost (millions)', labelpad=8)
        ax.grid(axis='both', alpha=.16, linewidth=.7)
        # Plot complete actual trajectories; no pointwise median, invented
        # timestamps, smoothed crossings, or continuation after termination.
        for representative in [False, True]:
            for arm in ARMS:
                for t in traces:
                    if t['arm'] != arm or t['representative'] != representative:
                        continue
                    xs = [s['elapsed_s'] for s in t['samples']]
                    ys = [s['cost']/1e6 for s in t['samples']]
                    ax.step(xs, ys, where='post', color=COLORS[arm], linestyle=STYLES[arm],
                            linewidth=2.1 if representative else 1., alpha=1 if representative else .25,
                            zorder=4 if representative else 3)
                    if representative:
                        ax.scatter(xs[1:], ys[1:], s=12, color=COLORS[arm], zorder=5)
                    ax.scatter([t['endpoint_time_s']], [t['audited_cost']/1e6], marker='D',
                               s=44 if representative else 20, facecolor='white', edgecolor=COLORS[arm],
                               linewidth=1.6 if representative else .8, alpha=1 if representative else .35,
                               zorder=7 if representative else 6)
    axes[0].set_yscale('log')
    axes[0].set_ylim(24.5, 1300)
    axes[0].yaxis.set_major_locator(FixedLocator([25, 50, 100, 200, 500, 1000]))
    axes[0].yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:g}'))
    axes[0].yaxis.set_minor_locator(FixedLocator([]))
    axes[0].set_title('Full decrease · logarithmic cost scale', loc='left', fontsize=12, pad=12)
    axes[1].set_ylim(25, 54)
    axes[1].yaxis.set_major_locator(MultipleLocator(5))
    axes[1].set_title('Near the fixed target · linear cost scale', loc='left', fontsize=12, pad=12)
    axes[1].text(.57*xmax, target/1e6-1.2, f'Common target: {target/1e6:.3f}M', color='#59636d', fontsize=9.5)
    for arm, xytext, ha in [('rayleigh', (9, 0), 'left'),
                           ('caspar32', (8, 10), 'left'), ('caspar64', (-8, 16), 'right')]:
        t = next(t for t in traces if t['arm'] == arm and t['representative'])
        axes[1].annotate(f"{t['endpoint_time_s']:.2f} s", (t['endpoint_time_s'], t['audited_cost']/1e6),
                         xytext=xytext, textcoords='offset points', color=COLORS[arm],
                         fontsize=11, fontweight='bold', ha=ha, va='center')
    fig.text(.075, .943, 'Final-13682 · convergence to the same target', fontsize=22, fontweight='bold')
    fig.text(.075, .901, '13,682 cameras  ·  4.46M points  ·  28.99M observations  ·  3 fresh runs per configuration',
             fontsize=11.5, color='#59636d')
    handles = [Line2D([0], [0], color=COLORS[k], lw=2.5, linestyle=STYLES[k], label=LABELS[k]) for k in ARMS]
    fig.legend(handles=handles, loc='upper left', bbox_to_anchor=(.068, .873), ncol=4,
               frameon=False, handlelength=3.2, columnspacing=2.25, fontsize=11)
    fig.text(.075, .16,
             f"Prism median: {prism_time:.2f} s   |   {ratios['caspar32']:.2f}× faster than Caspar FP32   |   {ratios['caspar64']:.2f}× faster than Caspar FP64",
             fontsize=13, fontweight='bold', color=COLORS['rayleigh'])
    fig.text(.075, .114, 'Bold = run with median target time; faint = other repeats. Diamonds = independently audited endpoints. Curves stop at the target.',
             fontsize=9.5, color='#59636d')
    fig.text(.075, .08, 'Native cost traces; FP32 endpoint rescored in FP64. Native solver clocks: Caspar graph setup excluded; Prism solver-local setup included.',
             fontsize=9.5, color='#59636d')
    fig.text(.075, .046, 'Prism CSV timing is aligned to its final target event. Guard on/off overlap: the numerical guard never activates on this scene.',
             fontsize=9.5, color='#59636d')
    for ext in ['png', 'pdf', 'svg']:
        fig.savefig(a.root/f'convergence.{ext}', dpi=190, facecolor='white')
    plt.close(fig)

    fp32_error = max(abs(t['audited_cost']-t['native_endpoint_cost'])/t['audited_cost']
                     for t in traces if t['arm'] == 'caspar32')
    body = [
        '# Final-13682 convergence curves', '',
        f'Fresh N=3 comparison of all four configurations from the latest primary benchmark. Prism reaches the common target in median **{prism_time:.3f} s**, **{ratios["caspar32"]:.2f}×** faster than Caspar FP32 and **{ratios["caspar64"]:.2f}×** faster than Caspar FP64 on this scene.', '',
        '![Final-13682 convergence](figures/convergence/final13682_convergence.png)', '',
        '| Configuration | Hits | Median target time | Range | Median audited endpoint cost |',
        '|---|---:|---:|---:|---:|',
    ]
    for arm in ARMS:
        s = summary[arm]
        body.append(f'| {s["label"]} | 3/3 | {s["median_seconds"]:.3f} s | {s["min_seconds"]:.3f}–{s["max_seconds"]:.3f} s | {s["median_audited_cost"]:,.3f} |')
    body += ['',
        f'The fixed target is **{target:,.6f}**, 1% above the previously fixed anchor of {protocol["scenes"]["final-13682"]["anchor"]:,.6f}. Cost is half the sum of squared pixel residuals over all 28,987,644 observations, using SIMPLE_RADIAL with k2=0. Lower is better. All 12 exported endpoints pass the same independent FP64 audit as the previous study (relative agreement tolerance 1e-6).', '',
        'This is convergence **to useful quality**, with each solver stopping at its target. The curves do not show continued optimization after the target or establish the eventual best achievable cost. Prism overshoots the target on its fifth accepted step; the lower terminal cost is not an equal-budget final-error comparison.', '',
        'The current guard and guard-off arms use the same camera-radius TR solver; only the numerical Schur-recovery switch differs. Guard off is not vanilla BA. There are no numerical repairs in these six Prism runs, so their numerical trajectories coincide to rounding and any small time difference is descriptive run variability.', '',
        '## Timing and plotting method', '',
        '- Three fresh repeats per configuration, same host and GPU, rotating run order and serialized GPU execution. Frozen executable hashes and exact commands are recorded. Native budget: 20 s, secondary limit: 600. No binary was rebuilt or solver policy changed.',
        '- Bold lines show the entire actual run whose verified target time is the median. Faint lines retain the other two repeats. These are not pointwise median curves or confidence intervals.',
        '- Staircases show the last recorded accepted-state cost until a new state is available. No interpolation is used to invent an earlier target crossing. Curves end at their last measurement; diamonds mark independently audited final states.',
        '- Prism uses the frozen executable’s existing `--csv` logger. Its clock starts after solver-local setup, while the TARGET clock starts at solver entry. The CSV’s final row is immediately before TARGET in the source. We shift every CSV time by `TARGET_seconds - final_CSV_wall_s`, aligning the same endpoint and restoring setup time. This also conservatively retains the final CSV flush-to-TARGET delay in intermediate timestamps; CSV times are rounded to 0.0001 s. The known initial state is placed at solver time zero. No timing is inferred from iteration counts or product counts.',
        '- Caspar TRACE timestamps and runtime share its native solver clock. Caspar graph setup is excluded; Prism solver-local setup is included. Parsing, state export and independent audit are excluded. This follows the existing speed-comparison convention and is not an end-to-end COLMAP pipeline measurement.',
        f'- Internal costs are plotted without rescaling. Only final states were independently rescored. The largest native-versus-independent FP32 endpoint discrepancy in this batch is **{100*fp32_error:.5f}%**. The FP32 stopping threshold retains the predeclared 0.1% inward margin; reported target times refer to independently verified terminal states, not an unaudited earlier native crossing.', '',
        '## Artifacts and reproduction', '',
        '[PNG](figures/convergence/final13682_convergence.png) · [PDF](figures/convergence/final13682_convergence.pdf) · [SVG](figures/convergence/final13682_convergence.svg) · [curve data CSV](final13682_convergence.csv)', '',
        f'Raw logs, complete CSV traces, manifests, exported states, audit results, protocol and full curve JSON are in `{a.root}`. Existing benchmark runs remain separate.', '',
        '```bash',
        'python3 bench/run_final13682_convergence.py',
        'python3 bench/plot_final13682_convergence.py',
        '```', '',
        'The collection script resumes completed runs without replacing them. Plotting only reads saved traces and audited results. Copies of the scripts are included with the raw artifacts.', '',
    ]
    assert all(n == 0 for arm in ['rayleigh', 'off'] for n in summary[arm]['numeric_rebuilds'])
    assert all(n == 5 for arm in ['rayleigh', 'off'] for n in summary[arm]['accepts'])
    a.docs.mkdir(exist_ok=True, parents=True)
    figure_dir.mkdir(exist_ok=True, parents=True)
    (a.docs/'final13682_convergence.md').write_text('\n'.join(body))
    (a.root/'README.md').write_text('\n'.join(body).replace('final13682_convergence.png', 'convergence.png')
                                 .replace('final13682_convergence.pdf', 'convergence.pdf')
                                 .replace('final13682_convergence.svg', 'convergence.svg')
                                 .replace('final13682_convergence.csv', 'curves.csv'))
    for ext in ['png', 'pdf', 'svg']:
        shutil.copy2(a.root/f'convergence.{ext}', figure_dir/f'final13682_convergence.{ext}')
    shutil.copy2(a.root/'curves.csv', a.docs/'final13682_convergence.csv')
    shutil.copy2(__file__, a.root/'scripts'/pathlib.Path(__file__).name)
    print(json.dumps({'summary': summary, 'prism_speedup': ratios,
                      'fp32_endpoint_relative_error_max': fp32_error,
                      'figure': str(figure_dir/'final13682_convergence.png')}, indent=2))


if __name__ == '__main__':
    main()
