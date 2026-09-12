"""Audit observed native acceptance, history, radius and minimum-state export."""
from pathlib import Path
import json, math, re, statistics

P = Path(__file__).resolve().parent


def fields(line):
    return {k: float(v) for k, v in re.findall(r'(\w+)=(\S+)', line)}


def main():
    comp = json.loads((P / 'aside-compatibility-results.json').read_text())
    med = {a: statistics.median(r['cost'] for r in comp if r['arm'] == a)
           for a in ['original', 'off']}
    assert len(comp) == 6 and abs(med['off'] / med['original'] - 1) < .0015
    results = []
    for row in json.loads((P / 'aside-smoke-results.json').read_text()):
        folder = P / row['source']
        threshold = .01 if row['arm'] == 'rho01' else .001
        window = 5 if row['arm'] == 'nonmonotone5' else 0
        history = [row['score_init']]
        current = minimum = row['score_init']
        pending = None
        count = relaxed = uphill = 0
        for line in (folder / 'stdout.log').read_text().splitlines():
            if line.startswith('W4_ACCEPT '):
                pending = fields(line)
                assert math.isclose(pending['current'], current, rel_tol=1e-8)
                reference = max(history[-window:]) if window else current
                assert math.isclose(pending['reference'], reference, rel_tol=1e-8)
                if pending['pre_radius_accept']:
                    assert pending['prediction'] > 0 and pending['test_rho'] > threshold
                    relaxed += not bool(pending['original_accept'])
            elif line.startswith('ATTR_RADIUS ') and pending is not None:
                r = fields(line)
                if r['rho'] < .25:
                    assert math.isclose(r['next_radius'], max(1e-14, .25*r['radius']), rel_tol=1e-8)
                if r['accept']:
                    assert pending['pre_radius_accept'] and r['norm'] <= r['radius']*(1+1e-8)
                    if not window:
                        assert pending['candidate'] < current
                    uphill += pending['candidate'] > current
                    current = pending['candidate']
                    minimum = min(minimum, current)
                    history.append(current)
                count += 1
                pending = None
        assert count > 0
        assert math.isclose(row['cost'], minimum if window else current, rel_tol=1e-6)
        results.append(dict(arm=row['arm'],attempts_audited=count,relaxed_eligible=relaxed,
                            uphill_accepted=uphill,minimum_visited=minimum,exported_cost=row['cost']))
    assert len(results) == 3
    out = dict(passed=True, compatibility_medians=med,
               compatibility_relative_delta=med['off']/med['original']-1,
               observed_native_checks=results,
               scope='Native smoke/compatibility checks, not independent tail reliability or timing evidence')
    (P / 'aside-validation.json').write_text(json.dumps(out, indent=2)+'\n')
    print('ASIDE VALIDATION PASS', results, flush=True)


if __name__ == '__main__':
    main()
