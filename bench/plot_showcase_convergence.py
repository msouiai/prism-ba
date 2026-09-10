#!/usr/bin/env python3
"""Render the two fresh showcase convergence experiments without smoothing traces."""
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
from matplotlib.ticker import FuncFormatter, MultipleLocator

from plot_final13682_convergence import COLORS, LABELS, STYLES, parse_trace

ARMS = ['rayleigh', 'caspar32', 'caspar64']
PRESENTATION = {
    'ladybug-1469': dict(
        title='Ladybug-1469 · Caspar FP32 terminates far above the target',
        subtitle='1,469 cameras  ·  145k points  ·  642k observations  ·  3 fresh runs per configuration',
        zoom_max=1.35,
        message_y=.93,
        message='FP32 ends at {fp32_ratio:.2f}× the target after {fp32_time:.2f} s; FP64 reaches the target.',
        caveat='Ladybug subsets are correlated recordings; this is a precision diagnostic, not a separate independent panel win.',
    ),
    'final-4585': dict(
        title='Final-4585 · Prism reaches useful quality while Caspar remains far above it',
        subtitle='4,585 cameras  ·  1.33M points  ·  9.13M observations  ·  3 fresh runs per configuration',
        zoom_max=1.75,
        message_y=.18,
        message='Both Caspar precisions exhaust the 12 s cap\nwithout reaching the target.',
        caveat='This is a large-scene solver/configuration separation; it is not an FP32-only precision claim.',
    ),
}


def median_trace(traces, arm):
    group = sorted((t for t in traces if t['arm'] == arm), key=lambda t: t['endpoint_time_s'])
    selected = group[len(group)//2]
    for trace in group:
        trace['representative'] = trace is selected
    return group, selected


def plot_scene(root, protocol, scene, docs):
    config = PRESENTATION[scene]
    folder = root/scene
    rows = [r for r in json.loads((root/'results.json').read_text()) if r['scene'] == scene]
    assert len(rows) == 9 and {(r['arm'], r['rep']) for r in rows} == {(arm, rep) for arm in ARMS for rep in [1, 2, 3]}
    assert all(r['valid'] for r in rows)
    target = protocol['scenes'][scene]['target']
    traces = [parse_trace(folder, row) for row in rows]
    summaries = {}
    for arm in ARMS:
        group, representative = median_trace(traces, arm)
        result_rows = [t['result'] for t in group]
        hit_times = [r['crossing'] for r in result_rows if r['hit']]
        summaries[arm] = dict(
            label=LABELS[arm], hits=len(hit_times), runs=len(group),
            median_target_seconds=statistics.median(hit_times) if len(hit_times) == len(group) else None,
            endpoint_seconds=[t['endpoint_time_s'] for t in group],
            endpoint_costs=[t['audited_cost'] for t in group],
            median_endpoint_cost=statistics.median(t['audited_cost'] for t in group),
            median_endpoint_ratio=statistics.median(t['audited_cost'] for t in group)/target,
            representative_rep=representative['rep'],
            cap_hits=sum(t['result']['cap_hit'] for t in group),
            rejects=[t['result']['rejects'] for t in group],
        )
    for trace in traces:
        trace['endpoint_ratio_target'] = trace['audited_cost']/target
    output = dict(scene=scene, target=target, summary=summaries, traces=traces)
    (folder/'curves.json').write_text(json.dumps(output, indent=2)+'\n')
    with (folder/'curves.csv').open('w') as f:
        fields = ['scene', 'arm', 'rep', 'representative', 'iteration', 'elapsed_s', 'cost',
                  'cost_kind', 'event', 'csv_wall_s', 'csv_to_native_offset_s']
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for trace in traces:
            base = {k: trace[k] for k in ['arm', 'rep', 'representative']}
            for sample in trace['samples']:
                writer.writerow(dict(scene=scene, **base, **sample, cost_kind='native'))
            writer.writerow(dict(scene=scene, **base, iteration=trace['samples'][-1]['iteration'],
                                 elapsed_s=trace['endpoint_time_s'], cost=trace['audited_cost'],
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
        ax.xaxis.set_major_locator(MultipleLocator(2 if xmax >= 10 else 1))
        ax.set_xlabel('Elapsed solver time (seconds)', labelpad=10)
        ax.set_ylabel('Reprojection cost (millions)', labelpad=8)
        ax.grid(axis='both', alpha=.16, linewidth=.7)
        for representative in [False, True]:
            for arm in ARMS:
                for trace in traces:
                    if trace['arm'] != arm or trace['representative'] != representative:
                        continue
                    xs = [sample['elapsed_s'] for sample in trace['samples']]
                    ys = [sample['cost']/1e6 for sample in trace['samples']]
                    ax.step(xs, ys, where='post', color=COLORS[arm], linestyle=STYLES[arm],
                            linewidth=2.1 if representative else 1., alpha=1 if representative else .25,
                            zorder=4 if representative else 3)
                    if representative:
                        ax.scatter(xs[1:], ys[1:], s=12, color=COLORS[arm], zorder=5)
                    ax.scatter([trace['endpoint_time_s']], [trace['audited_cost']/1e6], marker='D',
                               s=44 if representative else 20, facecolor='white', edgecolor=COLORS[arm],
                               linewidth=1.6 if representative else .8, alpha=1 if representative else .35,
                               zorder=7 if representative else 6)
    axes[0].set_yscale('log')
    initial_max = max(s['cost'] for t in traces for s in t['samples'])/1e6
    terminal_min = min(t['audited_cost'] for t in traces)/1e6
    axes[0].set_ylim(terminal_min*.92, initial_max*1.14)
    axes[0].yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:g}'))
    axes[0].set_title('Full decrease · logarithmic cost scale', loc='left', fontsize=12, pad=12)
    axes[1].set_ylim(target*.92/1e6, target*config['zoom_max']/1e6)
    axes[1].set_title('Target region · linear cost scale', loc='left', fontsize=12, pad=12)
    axes[1].text(.54*xmax, target/1e6-0.025*(target/1e6), f'Fixed target: {target/1e6:.3f}M',
                 color='#59636d', fontsize=9.5)
    for arm in ARMS:
        trace = next(t for t in traces if t['arm'] == arm and t['representative'])
        if trace['audited_cost'] <= target*config['zoom_max']:
            label = f"{trace['endpoint_time_s']:.2f} s" if trace['result']['hit'] else f"{trace['audited_cost']/target:.2f}×"
            axes[1].annotate(label, (trace['endpoint_time_s'], trace['audited_cost']/1e6), xytext=(-5, 12),
                             textcoords='offset points', color=COLORS[arm], fontsize=11, fontweight='bold', ha='right')
    fp32 = summaries['caspar32']
    fp32_time = statistics.median(fp32['endpoint_seconds'])
    axes[1].text(.98, config['message_y'], config['message'].format(fp32_ratio=fp32['median_endpoint_ratio'], fp32_time=fp32_time),
                 transform=axes[1].transAxes, ha='right', va='top', fontsize=10, color=COLORS['caspar32'],
                 bbox=dict(facecolor='white', edgecolor='#d9dee3', boxstyle='round,pad=.35'))
    fig.text(.075, .943, config['title'], fontsize=20, fontweight='bold')
    fig.text(.075, .901, config['subtitle'], fontsize=11.5, color='#59636d')
    handles = [Line2D([0], [0], color=COLORS[arm], lw=2.5, linestyle=STYLES[arm], label=LABELS[arm]) for arm in ARMS]
    fig.legend(handles=handles, loc='upper left', bbox_to_anchor=(.068, .873), ncol=3,
               frameon=False, handlelength=3.2, columnspacing=2.7, fontsize=11)
    prism = summaries['rayleigh']
    statement = f"Prism: 3/3 target hits, median {prism['median_target_seconds']:.3f} s"
    caspar_bits = []
    for arm in ['caspar32', 'caspar64']:
        summary = summaries[arm]
        if summary['hits'] == 3:
            caspar_bits.append(f"{LABELS[arm]}: 3/3, {summary['median_target_seconds']:.3f} s")
        else:
            caspar_bits.append(f"{LABELS[arm]}: {summary['hits']}/3; median endpoint {summary['median_endpoint_ratio']:.2f}× target")
    fig.text(.075, .16, statement+'   |   '+'   |   '.join(caspar_bits), fontsize=11.6,
             fontweight='bold', color=COLORS['rayleigh'])
    fig.text(.075, .114, 'Bold = complete run with median endpoint time; faint = other repeats. Diamonds = independently audited endpoints.',
             fontsize=9.5, color='#59636d')
    fig.text(.075, .08, 'Prism stops at the fixed target; Caspar curves end at their target or the native cap/iteration limit. No continuation is inferred.',
             fontsize=9.5, color='#59636d')
    fig.text(.075, .046, 'Native cost traces; FP32 endpoints independently rescored in FP64. Caspar graph setup excluded; Prism solver-local setup included.',
             fontsize=9.5, color='#59636d')
    for ext in ['png', 'pdf', 'svg']:
        fig.savefig(folder/f'convergence.{ext}', dpi=190, facecolor='white')
    plt.close(fig)
    return output


def report_scene(output, protocol, scene, docs):
    folder = pathlib.Path(protocol['_root'])/scene
    summary = output['summary']
    target = output['target']
    doc_stem = scene.replace('-', '')+'_convergence'
    target_source = protocol['scenes'][scene]['reference_protocol']
    body = [
        f'# {scene.title()} convergence', '',
        PRESENTATION[scene]['message'].replace('\n', ' ').format(
            fp32_ratio=summary['caspar32']['median_endpoint_ratio'],
            fp32_time=statistics.median(summary['caspar32']['endpoint_seconds'])), '',
        f'![{scene} convergence](figures/convergence/{doc_stem}.png)', '',
        '| Configuration | Target hits | Median target time | Median final audited cost | Final / target |',
        '|---|---:|---:|---:|---:|',
    ]
    for arm in ARMS:
        s = summary[arm]
        time = f"{s['median_target_seconds']:.3f} s" if s['median_target_seconds'] is not None else '—'
        body.append(f"| {s['label']} | {s['hits']}/{s['runs']} | {time} | {s['median_endpoint_cost']:,.3f} | {s['median_endpoint_ratio']:.3f}× |")
    body += ['',
        f'Fixed historical target: **{target:,.6f}**, 1% above its historical anchor. It was copied unchanged from `{target_source}`. All nine fresh endpoints passed the independent FP64 audit (relative tolerance 1e-6).', '',
        PRESENTATION[scene]['caveat'], '',
        'The bold curve is the complete run with median endpoint time; faint curves are the other repeats. The plot does not smooth, interpolate, or continue a stopped solver. Prism uses the frozen current guard configuration. Caspar FP32 uses its predeclared 0.1% inward native stop margin; target qualification uses the independent original-observation FP64 audit.', '',
        f'[PNG](figures/convergence/{doc_stem}.png) · [PDF](figures/convergence/{doc_stem}.pdf) · [SVG](figures/convergence/{doc_stem}.svg) · [curve data CSV]({doc_stem}.csv)', '',
    ]
    docs.mkdir(exist_ok=True, parents=True)
    figure_dir = docs/'figures'/'convergence'
    figure_dir.mkdir(exist_ok=True, parents=True)
    (docs/f'{doc_stem}.md').write_text('\n'.join(body))
    shutil.copy2(folder/'curves.csv', docs/f'{doc_stem}.csv')
    for ext in ['png', 'pdf', 'svg']:
        shutil.copy2(folder/f'convergence.{ext}', figure_dir/f'{doc_stem}.{ext}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=pathlib.Path, default=pathlib.Path('/workspace/prism-showcase-convergence'))
    ap.add_argument('--docs', type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1]/'docs')
    args = ap.parse_args()
    protocol = json.loads((args.root/'protocol.json').read_text())
    protocol['_root'] = str(args.root)
    result = {}
    for scene in PRESENTATION:
        result[scene] = plot_scene(args.root, protocol, scene, args.docs)
        report_scene(result[scene], protocol, scene, args.docs)
    (args.root/'showcase-curves.json').write_text(json.dumps(result, indent=2)+'\n')
    shutil.copy2(__file__, args.root/'scripts'/pathlib.Path(__file__).name)
    print(json.dumps({scene: data['summary'] for scene, data in result.items()}, indent=2))


if __name__ == '__main__':
    main()
