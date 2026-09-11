import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'; os.environ['OMP_NUM_THREADS'] = '1'
import argparse
import hashlib
import json
import pathlib
import time
import numpy as np
from geometry import State
from reference_ba import synthetic, valid_cost
from collective import clustered
from experiment import Work, solve_t2
from allocation import ACTIONS, FEATURES, prepare, features, perform, fit_tree, predict, rule

ROOT = pathlib.Path(__file__).resolve().parent

def cases(split):
    seeds = range(10) if split == 'development' else range(100, 110)
    families = ['depth', 'cluster'] if split == 'development' else ['depth', 'cluster', 'rotation']
    for family in families:
        for seed in seeds:
            if family == 'cluster': truth, state, obs, *_ = clustered(seed, bridges=4)
            else: truth, state, obs = synthetic(seed, family)
            ref = valid_cost(truth, obs); F0 = valid_cost(state, obs)
            yield family, seed, truth, state, obs, ref, ref+1e-4*(F0-ref)
    if split == 'held_out':
        for info in json.loads((ROOT/'t4_real_targets.json').read_text()):
            packed = np.load(ROOT/info['input'])
            s = State(*[packed[k].copy() for k in ['R', 't', 'X', 'intr']])
            yield info['scene'], 0, None, s, packed['observations'], info['reference']['cost'], info['target']

def utility(parent, cost, ref, target, seconds):
    gap = max(target-ref, parent-ref, 1e-12)
    after = max(target-ref, cost-ref, 1e-12)
    return max(0., float(np.log(gap/after)))/max(1e-9, seconds)

def main():
    p = argparse.ArgumentParser(); p.add_argument('--split', choices=['development', 'held_out'], required=True); args = p.parse_args()
    start = time.perf_counter(); rows = []
    for family, seed, truth, initial, obs, ref, target in cases(args.split):
        later, _ = solve_t2(initial, obs, 'lm', -1., max_attempts=3)
        for snapshot, state in enumerate([initial, later]):
            # Both are independently frozen decisions at registered lambda .1.
            filename = ROOT/'evidence'/f't8-{family}-{seed}-{snapshot}.npz'
            np.savez_compressed(filename, R=state.R, t=state.t, X=state.X, intr=state.intr,
                                observations=obs, lam=.1)
            parent_hash = hashlib.sha256(filename.read_bytes()).hexdigest()
            outputs = []
            for rep in range(3):
                order = ACTIONS[rep:]+ACTIONS[:rep]
                for action in order:
                    w = Work(); t0 = time.perf_counter()
                    cache = prepare(state, obs, .1, w)
                    x = w.call('features', features, cache)
                    winner, detail = perform(cache, action, w, target)
                    seconds = time.perf_counter()-t0
                    cost = winner['cost'] if winner else cache['F']
                    outputs.append({'rep': rep, 'action': action, 'seconds': seconds,
                                    'cost': cost, 'winner': winner['kind'] if winner else None,
                                    'utility': utility(cache['F'], cost, ref, target, seconds),
                                    'counts': w.counts, 'work_seconds': w.seconds, **detail})
            rates = np.array([np.median([r['utility'] for r in outputs if r['action'] == a]) for a in ACTIONS])
            rows.append({'family': family, 'seed': seed, 'snapshot': snapshot, 'parent_sha256': parent_hash,
                         'parent': str(filename.relative_to(ROOT)), 'parent_cost': valid_cost(state, obs),
                         'lambda': .1, 'reference': ref, 'target': target, 'features': x.tolist(),
                         'rates': rates.tolist(), 'oracle_action': ACTIONS[int(np.argmax(rates))], 'outcomes': outputs})
        print(family, seed, 'replayed', flush=True)
    if args.split == 'development':
        X = np.array([r['features'] for r in rows]); U = np.array([r['rates'] for r in rows])
        U /= np.maximum(1e-12, U.max(axis=1))[:, None]
        tree = fit_tree(X, U)
        (ROOT/'t8_frozen_policy.json').write_text(json.dumps({'features': FEATURES, 'actions': ACTIONS, 'tree': tree,
                                                            'training_families': ['depth', 'cluster']}, indent=2)+'\n')
    else: tree = json.loads((ROOT/'t8_frozen_policy.json').read_text())['tree']
    summary = {}
    for family in sorted(set(r['family'] for r in rows)):
        subset = [r for r in rows if r['family'] == family and max(r['rates']) > 0]
        def score(kind):
            values = []
            for r in subset:
                action = rule(r['features']) if kind == 'rule' else predict(tree, r['features']) if kind == 'tree' else kind
                values.append(r['rates'][ACTIONS.index(action)]/max(r['rates']))
            return float(np.mean(values)) if values else None
        summary[family] = {'useful_parents': len(subset), 'parents': sum(r['family'] == family for r in rows),
                           'fraction_of_local_oracle': {k: score(k) for k in ACTIONS+['rule', 'tree']},
                           'oracle_actions': {a: sum(r['oracle_action'] == a for r in subset) for a in ACTIONS}}
    (ROOT/f't8_replay_{args.split}.json').write_text(json.dumps({'collection_seconds': time.perf_counter()-start,
         'cache_contract': 'Independent parent/J/weights/lambda. Reuse factors only for OCA/geo RHS; new lambda refactors. Accepted whole state invalidates numeric cache.',
         'rows': rows}, indent=2, allow_nan=False)+'\n')
    (ROOT/f't8_replay_{args.split}_summary.json').write_text(json.dumps(summary, indent=2)+'\n'); print(json.dumps(summary, indent=2))

if __name__ == '__main__': main()
