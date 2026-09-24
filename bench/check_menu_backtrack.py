#!/usr/bin/env python3
"""Check the full-cost Armijo trace of a menu-backtracking diagnostic run."""
import argparse
import json
import math
import re
from collections import defaultdict


def check(path, preserve_center=False, warmup_accepts=0):
    attempts = {}
    candidates = defaultdict(list)
    probes = defaultdict(list)
    disabled_after = float("inf")
    with open(path) as stream:
        for line in stream:
            # Existing C++ diagnostic prints lowercase nonfinite literals.
            line = re.sub(r"(?<=[: ,\[])nan(?=[,}\]])", "NaN", line)
            line = re.sub(r"(?<=[: ,\[])inf(?=[,}\]])", "Infinity", line)
            line = line.replace(":-inf", ":-Infinity")
            row = json.loads(line)
            if row['t'] == 'a':
                attempts[row['a']] = row
            elif row['t'] == 'c':
                candidates[row['a']].append(row)
            elif row['t'] == 'bt_off':
                assert disabled_after == float('inf'), 'Confirmation rearmed'
                disabled_after = row['next_a']
            elif row['t'] == 'bt':
                probes[row['a']].append(row)
    assert attempts and probes, 'Diagnostic did not exercise backtracking'
    centres = {}
    centre = None
    accepted_before = {}
    accepted_count = 0
    for aid, attempt in sorted(attempts.items()):
        accepted_before[aid] = accepted_count
        accepted_count += attempt['acc']
        if attempt['streak'] == 0:
            centre = attempt['lam']
        centres[aid] = centre
    rescues = 0
    for aid, trials in probes.items():
        attempt = attempts[aid]
        assert aid < disabled_after, 'Backtracking continued during convergence confirmation'
        assert accepted_before[aid] >= warmup_accepts, 'Backtracked during the protected opening'
        f0 = attempt['cost0']
        # The diagnostic writes 11 significant digits; allow only its rounding.
        eps = 2e-10 * max(1.0, abs(f0))
        assert all(c['cost'] >= f0-eps for c in candidates[aid]), 'Backtracked a successful menu'
        for i, trial in enumerate(trials):
            assert trial['alpha'] == 0.5**(i+1)
            assert math.isfinite(trial['slope']) and trial['slope'] < 0
            bound = f0 + 1e-4*trial['alpha']*trial['slope']
            assert abs(trial['bound']-bound) <= eps
            if i < len(trials)-1:
                assert not (trial['cost'] < f0-eps and trial['cost'] < bound-eps), 'Continued after acceptable probe'
        last = trials[-1]
        if attempt['acc']:
            rescues += 1
            if preserve_center:
                expected = min(centres[aid], 1e8)
                assert abs(attempt['lam1']-expected) <= 2e-6*max(abs(expected), 1e-300), 'Rescue banked camera damping'

            assert last['cost'] <= last['bound']+eps
            assert last['cost'] < f0
            assert abs(last['cost']-attempt['bcost']) <= eps
        else:
            assert not (last['cost'] < f0-eps and last['cost'] < last['bound']-eps)
    assert rescues, 'Diagnostic had no rescued attempt'
    print(f'PASS {len(attempts)} attempts, {len(probes)} failed menus, {rescues} Armijo rescues, confirmation={disabled_after < float("inf")}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('learn_log')
    parser.add_argument('--preserve-center', action='store_true')
    parser.add_argument('--warmup-accepts', type=int, default=0)
    args = parser.parse_args()
    check(args.learn_log, args.preserve_center, args.warmup_accepts)
