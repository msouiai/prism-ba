#!/usr/bin/env python3
"""Read-only evidence audit; no solver execution or endpoint removal."""
from collections import Counter, defaultdict
from pathlib import Path
import csv, hashlib, json, math, subprocess

P = Path(__file__).resolve().parent
F = P.parent / 'eta2_champion'
NAMES = ('stcg', 'pi', 'coarse', 'frontload', 'opening_unclip', 'passenger', 'soft_kick')

def read(p):
    return json.loads(Path(p).read_text())

def digest(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def main():
    subprocess.run(['python3', str(F / 'build.py'), '--check-only'], check=True)
    champion = read(F / 'champion.json')
    champion_hash = digest(F / 'champion.json')
    assert digest('/tmp/prism-rl-actor/build/prism-tr') == champion['binary_sha256']
    archives, archived = [], {}
    for path in sorted((P / 'evidence_archives').glob('*-endpoint-contents.json')):
        m = read(path)
        assert digest(P / m['archive']) == m['archive_sha256'], path
        assert (P / m['archive']).stat().st_size == m['archive_bytes'], path
        for x in m['rows']:
            assert x['source'] not in archived, x['source']
            archived[x['source']] = x
        archives.append(dict(manifest=str(path.relative_to(P)), members=len(m['rows']),
                             archive_sha256=m['archive_sha256']))
    predictor_archived = [k for k in archived if k.startswith('evidence/predictor/')]
    assert len(predictor_archived) == 40
    totals, sources, inputs, binaries, initial, max_audit = {}, set(), {}, {}, defaultdict(list), 0.0
    primary = []
    for name in NAMES:
        practical = read(P / f'{name}-practical-results.json')
        tail = read(P / f'{name}-tail-results.json')
        assert len(practical) == 54
        assert len(tail) == (30 if name in ('frontload', 'opening_unclip') else 20)
        for stage, rows, n in [('practical', practical, 3), ('tail', tail, 5)]:
            counts = Counter((r['cell'], r['arm']) for r in rows)
            assert set(counts.values()) == {n}, (name, stage, counts)
        primary += practical + tail
        totals[name] = dict(practical=len(practical), tail=len(tail),
                           tail_hits={sc: {a: sum(r['hit'] for r in tail if r['scene']==sc and r['arm']==a)
                                           for a in ('off', 'on')}
                                      for sc in sorted({r['scene'] for r in tail})})
    assert len(primary) == 538
    confirmation = read(P / 'frontload-confirmation-results.json')
    assert len(confirmation) == 10
    assert Counter(r['arm'] for r in confirmation) == {'off': 5, 'on': 5}
    for r in primary + confirmation:
        folder = P / r['source']
        assert r['source'] not in sources
        sources.add(r['source'])
        assert read(folder / 'result.json') == r, folder
        assert r['valid'] and r['returncode'] == 0 and r['audit_relative_error'] < 1e-6, folder
        max_audit = max(max_audit, r['audit_relative_error'])
        m = read(folder / 'manifest.json')
        assert m['champion_sha256'] == champion_hash
        assert m['target'] == r['target'] and m['cap'] == r['cap']
        assert float(m['flags']['OCA_TARGET_COST']) == r['target']
        for flag, value in champion['flags'].items():
            assert m['flags'][flag] == value, (folder, flag)
        command = m['command']
        problem = command[command.index('--problem') + 1]
        if problem not in inputs:
            inputs[problem] = digest(problem)
        assert inputs[problem] == m['input_sha256']
        if command[0] not in binaries:
            binaries[command[0]] = digest(command[0])
        assert binaries[command[0]] == m['binary_sha256'] == m['build_manifest']['binary_sha256']
        curves = list(csv.DictReader(line for line in (folder / 'curve.csv').read_text().splitlines()
                                    if not line.startswith('#')))
        assert float(curves[0]['cost']) == r['score_init']
        initial[problem].append(r['score_init'])
        crossing = next((float(x['wall_s']) for x in curves if float(x['cost']) <= r['target']), None)
        hit = r['cost'] <= r['target'] and crossing is not None and crossing <= r['cap']
        assert hit == r['hit'] and r['target_seconds'] == (crossing if hit else None)
        assert r['attempts']['accepted'] == r['accepts']
        assert r['attempts']['matvecs'] == r['matvecs']
        assert math.isfinite(r['native_seconds']) and r['native_seconds'] > 0
        state = folder / 'endpoint.state.gz'
        if state.exists():
            assert digest(state) == r['state']['compressed_sha256']
        else:
            a = archived[str(state.relative_to(P))]
            assert a['raw_sha256'] == r['state']['sha256'] and a['bytes'] == r['state']['bytes']
    for problem, values in initial.items():
        assert max(values) - min(values) <= 1e-9 * max(1, max(values)), problem
    # Earlier archival verified each decompressed member before removing its gzip.
    # This audit rechecks the durable archive bytes, not every decompressed member.
    result = dict(status='PASS', native_primary_runs=len(primary), confirmation_runs=len(confirmation),
                  total_native_runs=len(sources), predictor_states_archived=len(predictor_archived),
                  per_candidate=totals, max_endpoint_audit_relative_error=max_audit,
                  score_init_ranges={p: [min(x), max(x)] for p, x in initial.items()},
                  verified_binary_hashes=binaries, input_hashes=inputs, archives=archives,
                  notes=['All reported rows equal their individual result files.',
                         'Legacy stop_ftol means marker presence, not a final stop reason after interception.',
                         'Endpoint gzip hashes or previously member-verified durable archive hashes checked.'])
    (P / 'FINAL_VERIFICATION.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print('PASS:', len(sources), 'native rows;', len(archives), 'durable archives; frozen baseline unchanged.')

if __name__ == '__main__':
    main()
