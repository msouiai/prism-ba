#!/usr/bin/env python3
import gzip
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


rows = json.loads((P / 'all-results.json').read_text())
conf = json.loads((P.parent / 'eta2_champion/champion.json').read_text())
source_manifest = json.loads((P.parent / 'eta2_champion/source_manifest.json').read_text())
source = P.parent / 'eta2_champion/source'
assert sha(source / 'prism_eta2.cu') == source_manifest['source_sha256']
for name, expected in source_manifest['headers_sha256'].items():
    assert sha(source / 'headers' / name) == expected, name
for name, expected in json.loads((P / 'runner_hashes.json').read_text()).items():
    assert sha(P.parents[1] / name) == expected, name
assert sha('/tmp/prism-rl-actor/build/prism-tr') == conf['binary_sha256']
assert sha('/workspace/prism-novelty/ceres-frozen') == '6543c8e6f9baa69c421eeda61aef5d1115ca0d825931b71905904f1f53d74837'
input_hashes = {scene:sha(Path('/workspace/bal') / (scene + '.txt'))
                for scene in ['venice-52', 'final-3068', 'final-4585']}
counts = {stage:sum(r['stage'] == stage for r in rows) for stage in ['venice', 'storm', 'ceres-storm']}
assert counts == {'venice': 20, 'storm': 20, 'ceres-storm': 12}, counts
probe_count = sum(r['stage'] == 'venice-probes' for r in rows)
assert probe_count == 6, probe_count
keys = [(r['stage'], r['scene'], r['arm'], r['rep']) for r in rows]
assert len(set(keys)) == len(keys), 'Duplicate measurement rows'
assert all(r['valid'] for r in rows), [(r['source'], r.get('error')) for r in rows if not r['valid']]
state_count = 0
for r in rows:
    if r['solver'] != 'eta2':
        continue
    folder = P / r['source']
    manifest = json.loads((folder / 'manifest.json').read_text())
    assert manifest['binary_sha256'] == conf['binary_sha256']
    assert manifest['input_sha256'] == input_hashes[r['scene']]
    assert manifest['protocol_sha256'] == sha(P / 'PROTOCOL.md')
    expected = dict(conf['flags'])
    if r['arm'] == 'stop_disabled':
        expected['OCA_FTOL'] = '0'
    elif r['arm'] == 'probe_relaxed_ftol':
        expected['OCA_FTOL'] = '1e-7'
    elif r['arm'] == 'probe_tighter_forcing':
        expected.update(OCA_FTOL='0', OCA_RLA_FIXED_ETA='0.1')
    assert manifest['flags'].items() >= expected.items()
    assert r['target'] == manifest['target']
    assert manifest['flags']['OCA_TARGET_COST'] == str(r['target'])
    assert manifest['flags']['OCA_MAX_SECONDS'] == '60'
    assert manifest['max_iter'] == (10000 if r['arm'] == 'stop_disabled' else 600)
    assert r['audit_relative_error'] < 1e-6
    if r['hit']:
        assert r['cost'] <= r['target'] and r['target_seconds'] <= 60
    with gzip.open(folder / 'endpoint.state.gz', 'rb') as f:
        assert hashlib.file_digest(f, 'sha256').hexdigest() == r['state_sha256']
    assert sha(folder / 'endpoint.state.gz') == r['compressed_state_sha256']
    state_count += 1
targets = json.loads((P / 'storm-targets.json').read_text())
early_targets = json.loads((P / 'early-storm-targets.json').read_text())
for scene, t in early_targets.items():
    assert targets[scene]['target'] == t['target']
for scene, t in targets.items():
    assert t['target'] == 1.01 * min(v['median'] for v in t['groups'].values())
    assert all(r['target'] == t['target'] for r in rows if r['scene'] == scene)
report = dict(runs=len(rows), by_stage=counts, all_valid=True,
              exploratory_probe_runs=probe_count,
              independent_eta2_endpoints=state_count, lossless_states_verified=state_count,
              frozen_champion_flags_preserved_except_declared_diagnostic_arms=True,
              frozen_source_and_headers_verified=1 + len(source_manifest['headers_sha256']),
              frozen_native_binaries_verified=2,
              original_input_hashes_verified=input_hashes,
              ceres_rejected_trials_excluded_from_targets=True)
(P / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(report)
