#!/usr/bin/env python3
"""Fresh N=3 convergence traces for two pre-existing Prism showcase cases."""
import datetime
import json
import pathlib
import shutil
import socket

from schur_recovery_study import BINS, BAL, FLAGS, run_one, sha, summarize, write
from audit_prism_state import observations

ROOT = pathlib.Path('/workspace/prism-showcase-convergence')
ARMS = ['rayleigh', 'caspar32', 'caspar64']
SCENES = {
    'ladybug-1469': {
        'anchor': 425487.49498630536,
        'target': 429742.3699361684,
        'cap': 8,
        'reference_protocol': '/workspace/prism-schur-recovery/extension/protocol.json',
        'role': 'FP32-specific failure: the prior FP64 Caspar arm reaches the fixed target.',
    },
    'final-4585': {
        'anchor': 7488277.5282109585,
        'target': 7563160.303493069,
        'cap': 12,
        'reference_protocol': '/workspace/prism-model-followup/final-caspar-pairs/protocol.json',
        'role': 'Large-scene failure: both prior Caspar precisions missed the fixed target.',
    },
}


def main():
    ROOT.mkdir(exist_ok=True)
    specs = {}
    for scene, spec in SCENES.items():
        source = pathlib.Path(spec['reference_protocol'])
        historical = json.loads(source.read_text())['scenes'][scene]
        assert historical['target'] == spec['target'] and historical['cap'] == spec['cap']
        assert sha(BAL/(scene+'.txt')) == historical['input_sha256']
        specs[scene] = dict(spec, input_sha256=historical['input_sha256'])
    proto = dict(
        phase='showcase-convergence',
        host=socket.gethostname(),
        scenes=specs,
        arms=ARMS,
        reps=3,
        multiplier=1.01,
        binaries={arm: sha(BINS[arm]) for arm in ARMS},
        flags=FLAGS,
        audit_relative_tolerance=1e-6,
        csv_logging=True,
        purpose='Fresh curves for two pre-specified illustrative cases, not an additional selection panel. Each arm uses the fixed historical target and cap.',
        clocks='Native solver clocks. Prism CSV begins after solver-local setup and is aligned to the same-run TARGET event. Caspar graph setup is excluded. Parsing, state export and independent CPU audit are excluded.',
        order='Scene-major; rotate three arms by repeat; GPU serialized by flock.',
    )
    assert proto['binaries'] == {
        'rayleigh': '117773562d33949cdbfdc27905d1f23a2cc1faedb7f77c3e619c17caa50a86dc',
        'caspar32': 'de038488e929a8fad674d1096c5f61619f3039e6409a81670dab0df7dffe0919',
        'caspar64': '6ca81c85112005b024df4972b0ec16c3819838999a876513e148c58ed8f35eb2',
    }
    path = ROOT/'protocol.json'
    if path.exists():
        assert json.loads(path.read_text()) == proto
    else:
        write(path, proto)
        write(ROOT/'created.json', {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()})
    scripts = ROOT/'scripts'
    scripts.mkdir(exist_ok=True)
    for name in ['run_showcase_convergence.py', 'schur_recovery_study.py', 'audit_prism_state.py']:
        shutil.copy2(pathlib.Path(__file__).parent/name, scripts/name)
    rows = []
    for scene, spec in specs.items():
        folder = ROOT/scene
        folder.mkdir(exist_ok=True)
        pending = any(not (folder/f'{scene}-{arm}-{rep}.result.json').exists()
                      for arm in ARMS for rep in range(1, proto['reps']+1))
        dims, obs = observations(BAL/(scene+'.txt')) if pending else (None, None)
        for rep in range(1, proto['reps']+1):
            offset = (rep-1) % len(ARMS)
            for arm in ARMS[offset:]+ARMS[:offset]:
                row = run_one(folder, scene, arm, rep, spec['target'], spec['cap'], dims, obs, proto,
                              trace_csv=True)
                rows.append(row)
                write(ROOT/'results.json', rows)
                write(ROOT/'summary.json', summarize(rows))
        del obs
    assert len(rows) == len(SCENES)*len(ARMS)*proto['reps']
    assert all(row['valid'] for row in rows), 'Do not plot an unaudited endpoint'
    print('COMPLETE', json.dumps(summarize(rows)), flush=True)


if __name__ == '__main__':
    main()
