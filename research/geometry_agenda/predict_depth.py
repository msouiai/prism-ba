#!/usr/bin/env python3
"""Scene-held-out diagnostic comparison; future-cost features are excluded."""
import json
import pathlib
import numpy as np

def auc(y, score):
    a = score[y == 1]; b = score[y == 0]
    if not len(a) or not len(b):
        return None
    return float(np.mean((a[:, None] > b).astype(float)+.5*(a[:, None] == b)))

def fit_predict(X, y, test):
    mean = X.mean(axis=0); sd = np.maximum(X.std(axis=0), 1e-8)
    X = np.c_[np.ones(len(X)), (X-mean)/sd]
    test = np.c_[np.ones(len(test)), (test-mean)/sd]
    w = np.zeros(X.shape[1]); reg = np.ones(len(w)); reg[0] = 1e-6
    for _ in range(30):
        p = 1/(1+np.exp(-np.clip(X@w, -35, 35)))
        H = X.T@((p*(1-p))[:, None]*X)+np.diag(reg)
        dw = np.linalg.solve(H, X.T@(p-y)+reg*w)
        w -= dw
        if np.linalg.norm(dw) < 1e-8:
            break
    return test@w

def evaluate(rows, key='scene'):
    y = np.array([int(r['failed_strict_model']) for r in rows])
    groups = np.array([r[key] for r in rows])
    base = np.array([[np.log10(max(r['lambda'], 1e-300)),
                      np.log10(max(r['step_euclidean_norm'], 1e-300)),
                      np.log10(max(r['raw_reduced_true_residual'], 1e-16))] for r in rows])
    depth = np.array([[np.log1p(r['prospective_abs_quantiles'][j]) for j in [2, 3, 4]] for r in rows])
    models = {'damping_step_residual': base, 'plus_depth': np.c_[base, depth]}
    records = []
    pooled = {name: np.zeros(len(rows)) for name in models}
    for group in sorted(set(groups)):
        test = groups == group; train = ~test
        record = {'held_out': str(group), 'test_count': int(test.sum()), 'test_failures': int(y[test].sum())}
        for name, X in models.items():
            pred = fit_predict(X[train], y[train], X[test])
            pooled[name][test] = pred
            record[name+'_auc'] = auc(y[test], pred)
        record['depth_only_auc'] = auc(y[test], depth[test, -1])
        records.append(record)
    return {'folds': records, 'pooled_auc': {name: auc(y, pred) for name, pred in pooled.items()},
            'note': 'Exploratory leave-scene-out prediction, not a deployed controller or an intervention speed result. Uses the prospective depth change of an already constructed candidate.'}

if __name__ == '__main__':
    root = pathlib.Path(__file__).resolve().parent
    rows = json.loads((root/'t1_capture_diagnostics.json').read_text())
    result = evaluate(rows)
    (root/'t1_real_prediction.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
