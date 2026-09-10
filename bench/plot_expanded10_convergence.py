#!/usr/bin/env python3
"""Plot a complete ten-scene panel with actual, unsmoothed convergence traces."""
import argparse
import csv
import json
import math
import pathlib
import shutil
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from plot_final13682_convergence import COLORS, LABELS, STYLES, parse_trace
from run_expanded10_convergence import SCENES

ARMS = ['rayleigh', 'caspar32', 'caspar64']


def representative(group):
    ordered = sorted(group, key=lambda trace: trace['endpoint_time_s'])
    selected = ordered[len(ordered)//2]
    for trace in ordered:
        trace['representative'] = trace is selected
    return selected


def cells(root, protocol):
    rows = json.loads((root/'results.json').read_text())
    assert len(rows) == len(SCENES)*len(ARMS)*3 and all(row['valid'] for row in rows)
    result = {}
    for scene in SCENES:
        group = [row for row in rows if row['scene'] == scene]
        assert len(group) == 9 and {(r['arm'], r['rep']) for r in group} == {(arm, rep) for arm in ARMS for rep in [1, 2, 3]}
        target = protocol['scenes'][scene]['target']
        traces = [parse_trace(root/scene, row) for row in group]
        stats = {}
        for arm in ARMS:
            arm_traces = [trace for trace in traces if trace['arm'] == arm]
            selected = representative(arm_traces)
            hits = [trace['result']['crossing'] for trace in arm_traces if trace['result']['hit']]
            stats[arm] = dict(
                hits=len(hits), runs=3,
                median_target_seconds=statistics.median(hits) if len(hits) == 3 else None,
                median_endpoint_seconds=statistics.median(trace['endpoint_time_s'] for trace in arm_traces),
                median_endpoint_cost=statistics.median(trace['audited_cost'] for trace in arm_traces),
                median_endpoint_ratio=statistics.median(trace['audited_cost']/target for trace in arm_traces),
                representative_rep=selected['rep'],
                cap_hits=sum(trace['result']['cap_hit'] for trace in arm_traces),
                rejects=[trace['result']['rejects'] for trace in arm_traces],
            )
        result[scene] = dict(target=target, traces=traces, summary=stats)
    return result


def draw_trace(ax, trace, target, *, bold):
    xs = [sample['elapsed_s'] for sample in trace['samples']]
    ys = [sample['cost']/target for sample in trace['samples']]
    arm = trace['arm']
    ax.step(xs, ys, where='post', color=COLORS[arm], linestyle=STYLES[arm],
            linewidth=2.2 if bold else 1., alpha=1 if bold else .24, zorder=4 if bold else 3)
    if bold:
        ax.scatter(xs[1:], ys[1:], s=11, color=COLORS[arm], zorder=5)
    ax.scatter([trace['endpoint_time_s']], [trace['audited_cost']/target], marker='D',
               s=42 if bold else 18, facecolor='white', edgecolor=COLORS[arm],
               linewidth=1.5 if bold else .8, alpha=1 if bold else .35, zorder=7 if bold else 6)


def configure_axis(ax, target, traces, title=None):
    ax.axhspan(0, 1, color='#f0f3f5', zorder=0)
    ax.axhline(1, color='#59636d', linestyle=(0, (3, 3)), linewidth=1.1, zorder=2)
    ax.set_yscale('log')
    ratios = [sample['cost']/target for trace in traces for sample in trace['samples']]
    endpoints = [trace['audited_cost']/target for trace in traces]
    ax.set_ylim(min(min(ratios), min(endpoints))*.88, max(ratios)*1.14)
    ax.set_xlim(0, math.ceil(max(trace['endpoint_time_s'] for trace in traces))+0.2)
    ax.grid(alpha=.16, linewidth=.7)
    ax.set_xlabel('Elapsed solver time (s)')
    ax.set_ylabel('Cost / fixed target')
    if title:
        ax.set_title(title, loc='left', fontsize=11, pad=9)


def scene_figure(scene, cell, out):
    target, traces, summary = cell['target'], cell['traces'], cell['summary']
    fig, ax = plt.subplots(figsize=(9.5, 5.9))
    fig.subplots_adjust(left=.115, right=.97, bottom=.25, top=.73)
    for bold in [False, True]:
        for trace in traces:
            if trace['representative'] == bold:
                draw_trace(ax, trace, target, bold=bold)
    configure_axis(ax, target, traces, f'{scene} · complete actual convergence traces')
    ax.text(.98, .055, 'Fixed target', transform=ax.transAxes, ha='right', va='bottom', fontsize=9.5, color='#59636d')
    fig.text(.115, .93, f'{scene} · current Prism vs Caspar', fontsize=19, fontweight='bold')
    with (pathlib.Path('/workspace/bal')/(scene+'.txt')).open(encoding='utf-8') as input_file:
        dims = input_file.readline().split()
    fig.text(.115, .885, f'{int(dims[0]):,} cameras  ·  {int(dims[1]):,} points  ·  {int(dims[2]):,} observations  ·  N=3 each',
             fontsize=10.5, color='#59636d')
    handles = [Line2D([0], [0], color=COLORS[arm], lw=2.5, linestyle=STYLES[arm], label=LABELS[arm]) for arm in ARMS]
    fig.legend(handles=handles, loc='upper left', bbox_to_anchor=(.105, .862), ncol=3, frameon=False,
               handlelength=3, columnspacing=2.2, fontsize=10.5)
    chunks = []
    for arm in ARMS:
        stat = summary[arm]
        if stat['hits'] == 3:
            chunks.append(f"{LABELS[arm]}: 3/3, {stat['median_target_seconds']:.3f} s")
        else:
            chunks.append(f"{LABELS[arm]}: {stat['hits']}/3, endpoint {stat['median_endpoint_ratio']:.3f}×")
    fig.text(.115, .16, chunks[0], fontsize=10.5, fontweight='bold', color=COLORS['rayleigh'])
    fig.text(.115, .125, '   |   '.join(chunks[1:]), fontsize=9.4, fontweight='bold', color='#59636d')
    fig.text(.115, .082, 'Bold = run with median endpoint time; faint = remaining repeats. Diamonds = independently audited endpoints.',
             fontsize=9.2, color='#59636d')
    fig.text(.115, .047, 'Curves stop at the target or native cap/iteration limit. No smoothing, interpolation, or post-stop continuation.',
             fontsize=9.2, color='#59636d')
    for extension in ['png', 'pdf', 'svg']:
        fig.savefig(out.with_suffix('.'+extension), dpi=180, facecolor='white')
    plt.close(fig)


def grid_figure(panel, out):
    fig, axes = plt.subplots(2, 5, figsize=(18, 7.6), sharey=False)
    fig.subplots_adjust(left=.065, right=.99, bottom=.11, top=.79, hspace=.47, wspace=.28)
    for ax, scene in zip(axes.flat, SCENES):
        cell = panel[scene]
        for trace in cell['traces']:
            if trace['representative']:
                draw_trace(ax, trace, cell['target'], bold=True)
        configure_axis(ax, cell['target'], cell['traces'], scene)
        ax.tick_params(labelsize=8)
        ax.xaxis.label.set_size(8)
        ax.yaxis.label.set_size(8)
    fig.text(.065, .935, 'Expanded ten-scene BAL convergence panel', fontsize=22, fontweight='bold')
    fig.text(.065, .895, 'Current Prism, Caspar FP32 and Caspar FP64 · one actual median-endpoint trace per arm · cost normalized by each scene’s fixed target',
             fontsize=10.5, color='#59636d')
    handles = [Line2D([0], [0], color=COLORS[arm], lw=2.5, linestyle=STYLES[arm], label=LABELS[arm]) for arm in ARMS]
    fig.legend(handles=handles, loc='upper left', bbox_to_anchor=(.06, .873), ncol=3, frameon=False, fontsize=10)
    fig.savefig(out, dpi=190, facecolor='white')
    fig.savefig(out.with_suffix('.pdf'), facecolor='white')
    fig.savefig(out.with_suffix('.svg'), facecolor='white')
    plt.close(fig)


def write_outputs(root, docs, protocol, panel):
    figure_dir = docs/'figures'/'convergence'
    figure_dir.mkdir(exist_ok=True, parents=True)
    all_rows = []
    lines = [
        '# Expanded ten-scene convergence panel', '',
        'Ten predeclared BAL scenes, each measured three fresh times with current Prism, Caspar FP32 and Caspar FP64. Targets were fixed before collection. All reported endpoints passed the independent FP64 audit; target misses remain in the table and figures.', '',
        '![Expanded ten-scene panel](figures/convergence/expanded10_convergence_grid.png)', '',
        '| Scene | Prism | Caspar FP32 | Caspar FP64 | Fixed target |',
        '|---|---:|---:|---:|---:|',
    ]
    for scene, cell in panel.items():
        summary = cell['summary']
        def text(arm):
            stat = summary[arm]
            return f"3/3, {stat['median_target_seconds']:.3f} s" if stat['hits'] == 3 else f"{stat['hits']}/3, {stat['median_endpoint_ratio']:.3f}× endpoint"
        lines.append(f"| [{scene}](figures/convergence/expanded_{scene.replace('-', '')}_convergence.png) | {text('rayleigh')} | {text('caspar32')} | {text('caspar64')} | {cell['target']:,.3f} |")
        folder = root/scene
        stem = f'expanded_{scene.replace("-", "")}_convergence'
        scene_figure(scene, cell, folder/'convergence')
        for extension in ['png', 'pdf', 'svg']:
            shutil.copy2(folder/f'convergence.{extension}', figure_dir/f'{stem}.{extension}')
        for trace in cell['traces']:
            for sample in trace['samples']:
                all_rows.append(dict(scene=scene, arm=trace['arm'], rep=trace['rep'], representative=trace['representative'],
                                     iteration=sample['iteration'], elapsed_s=sample['elapsed_s'], cost=sample['cost'],
                                     cost_over_target=sample['cost']/cell['target'], cost_kind='native', event=sample['event']))
            all_rows.append(dict(scene=scene, arm=trace['arm'], rep=trace['rep'], representative=trace['representative'],
                                 iteration=trace['samples'][-1]['iteration'], elapsed_s=trace['endpoint_time_s'],
                                 cost=trace['audited_cost'], cost_over_target=trace['audited_cost']/cell['target'],
                                 cost_kind='independent_fp64', event='audited_endpoint'))
    grid_figure(panel, root/'expanded10_convergence_grid.png')
    for extension in ['png', 'pdf', 'svg']:
        shutil.copy2(root/f'expanded10_convergence_grid.{extension}', figure_dir/f'expanded10_convergence_grid.{extension}')
    fields = ['scene', 'arm', 'rep', 'representative', 'iteration', 'elapsed_s', 'cost', 'cost_over_target', 'cost_kind', 'event']
    with (docs/'expanded10_convergence.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(all_rows)
    lines += ['', 'The panel uses native solver clocks. Prism includes solver-local setup; Caspar graph setup is excluded. Parsing, state export and independent endpoint audit are excluded. FP32 has its predeclared 0.1% inward native stopping margin; qualification always uses the independent original-observation FP64 audit.', '', 'All 90 reported endpoints passed the audit. One Venice-1778 FP32 execution completed its solve but had its stdout truncated before the driver’s final check; its raw state/log are retained and excluded, and one audited replacement is included in the N=3 set.', '', 'Individual PNG/PDF/SVG plots and the aggregate normalized panel are in [docs/figures/convergence](figures/convergence/). [Raw curve CSV](expanded10_convergence.csv).']
    (docs/'expanded10_convergence.md').write_text('\n'.join(lines)+'\n')
    (root/'panel.json').write_text(json.dumps(panel, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=pathlib.Path, default=pathlib.Path('/workspace/prism-expanded10-convergence'))
    parser.add_argument('--docs', type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1]/'docs')
    args = parser.parse_args()
    protocol = json.loads((args.root/'protocol.json').read_text())
    panel = cells(args.root, protocol)
    write_outputs(args.root, args.docs, protocol, panel)
    (args.root/'scripts').mkdir(exist_ok=True)
    shutil.copy2(__file__, args.root/'scripts'/pathlib.Path(__file__).name)
    print(json.dumps({scene: panel[scene]['summary'] for scene in panel}, indent=2))


if __name__ == '__main__':
    main()
