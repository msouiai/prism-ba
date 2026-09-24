#!/usr/bin/env python3
"""Render the Muell GBA146 Prism/Caspar N=3 convergence comparison."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import re

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path('/workspace')
PRISM = ROOT / 'prism-muell-variants' / 'runs'
CASPAR = ROOT / 'prism-muell-caspar' / 'runs'
OUT = ROOT / 'prism-muell-caspar' / 'figures'
TARGET = 1946488.746262194
INITIAL = 2442177.030208319
TMIN, TMAX = 0.03, 100.0

SERIES = (
    ('Prism: Schur-guarded LM', 'prism', 'measure-schur-guarded-lm', '#0072B2'),
    ('Prism: fixed-five menu', 'prism', 'measure-control-five', '#6A6A6A'),
    ('Prism: DLT repair + five', 'prism', 'measure-retri-five', '#009E73'),
    ('Caspar FP32 default', 'caspar', 'measure-caspar32', '#D55E00'),
    ('Caspar FP64 default', 'caspar', 'measure-caspar64', '#CC79A7'),
)


def prism_trace(stem: str) -> tuple[np.ndarray, np.ndarray]:
    with (PRISM / f'{stem}.csv').open() as file:
        rows = list(csv.DictReader(line for line in file if not line.startswith('#')))
    time = np.array([float(row['wall_s']) for row in rows])
    cost = np.array([float(row['cost']) for row in rows])
    return time, cost


def caspar_trace(stem: str) -> tuple[np.ndarray, np.ndarray]:
    log = (CASPAR / f'{stem}.log').read_text()
    trace = re.findall(r'^TRACE iter=\d+ cost=(\S+) seconds=(\S+)', log, re.M)
    if not trace:
        raise RuntimeError(f'no trace records in {stem}')
    time = np.array([0.0] + [float(seconds) for _, seconds in trace])
    cost = np.array([INITIAL] + [float(value) for value, _ in trace])
    return time, cost


def sample_right_continuous(time: np.ndarray, cost: np.ndarray, grid: np.ndarray) -> np.ndarray:
    index = np.searchsorted(time, grid, side='right') - 1
    index = np.clip(index, 0, len(cost) - 1)
    return cost[index]


def percentage_above_target(cost: np.ndarray) -> np.ndarray:
    return 100.0 * (cost / TARGET - 1.0)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    grid = np.r_[TMIN, np.geomspace(TMIN, TMAX, 800)]
    figure, axes = plt.subplots(2, 1, sharex=True, figsize=(10.4, 8.0), layout='constrained')
    for label, kind, prefix, color in SERIES:
        reader = prism_trace if kind == 'prism' else caspar_trace
        traces = [reader(f'{prefix}-{rep}') for rep in range(1, 4)]
        samples = np.vstack([sample_right_continuous(time, cost, grid) for time, cost in traces])
        median = np.median(samples, axis=0)
        for time, cost in traces:
            plot_time = np.maximum(time, TMIN)
            for axis in axes:
                axis.plot(plot_time, percentage_above_target(cost), color=color, alpha=0.20, linewidth=1.0)
        for axis in axes:
            axis.plot(grid, percentage_above_target(median), color=color, linewidth=2.35, label=label)

    for axis, ylim, title in (
        (axes[0], (-0.18, 26.0), 'Full convergence'),
        (axes[1], (-0.18, 4.0), 'Endgame detail'),
    ):
        axis.axhline(0.0, color='#222222', linewidth=1.0, linestyle=(0, (5, 3)), label='Frozen target')
        axis.set_xscale('log')
        axis.set_xlim(TMIN, TMAX)
        axis.set_ylim(*ylim)
        axis.set_ylabel('Objective above target (%)')
        axis.set_title(title, loc='left', fontsize=11, fontweight='bold')
        axis.grid(True, which='both', color='#D9D9D9', linewidth=0.7)

    axes[0].legend(loc='upper right', frameon=True, framealpha=0.96, fontsize=9)
    axes[1].set_xlabel('Native solver time (seconds, log scale)')
    figure.suptitle('Muell GBA146: convergence to one frozen quality target', fontsize=15, fontweight='bold')
    axes[0].text(
        0.02, 0.04,
        'Solid: N=3 pointwise median; translucent: individual runs.\n'
        'Caspar traces are native; all endpoints are independently FP64-audited.',
        transform=axes[0].transAxes, fontsize=8.5, va='bottom', color='#333333',
    )
    png = OUT / 'muell_gba146_prism_caspar_convergence.png'
    svg = OUT / 'muell_gba146_prism_caspar_convergence.svg'
    figure.savefig(png, dpi=220, bbox_inches='tight')
    figure.savefig(svg, bbox_inches='tight')
    metadata = {
        'target': TARGET, 'initial_cost': INITIAL,
        'series': [item[0] for item in SERIES],
        'statistic': 'pointwise median of N=3 right-continuous native traces',
        'caspar_note': 'native traces; independent original-observation FP64 endpoint audits in results.json',
        'files': [str(png), str(svg)],
    }
    (OUT / 'muell_gba146_prism_caspar_convergence.json').write_text(json.dumps(metadata, indent=2) + '\n')


if __name__ == '__main__':
    main()
