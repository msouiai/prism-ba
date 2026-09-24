#!/usr/bin/env python3
"""Fresh N=3 current-Prism/Caspar convergence traces across a fixed ten-scene BAL panel."""
import datetime
import json
import pathlib
import shutil
import socket

from schur_recovery_study import BINS, BAL, FLAGS, run_one, sha, summarize, write
from audit_prism_state import observations

ROOT = pathlib.Path('/workspace/prism-expanded10-convergence')
ARMS = ['rayleigh', 'caspar32', 'caspar64']
# Targets and caps were frozen before this collection. Recent primary-study
# targets take precedence where available; the four remaining targets are 1%
# above the archived expanded-panel calibration anchor.
SCENES = {
    'dubrovnik-88': dict(anchor=357217.822019276, target=360790.00023946876, cap=4,
        target_source='/workspace/prism-caspar-expanded/measurement-plan.json (archived calibration anchor ×1.01)'),
    'dubrovnik-356': dict(anchor=716838.8857508276, target=724007.2746083359, cap=8,
        target_source='/workspace/prism-schur-recovery/extension/protocol.json'),
    'final-871': dict(anchor=1933873.0493919943, target=1953211.7798859142, cap=8,
        target_source='/workspace/prism-caspar-expanded/measurement-plan.json (archived calibration anchor ×1.01)'),
    'final-1936': dict(anchor=5074937.9725361075, target=5125687.352261469, cap=8,
        target_source='/workspace/prism-model-followup/final-caspar-pairs/protocol.json'),
    'final-3068': dict(anchor=1801421.7523974394, target=1819435.9699214138, cap=12,
        target_source='/workspace/prism-schur-recovery/extension/protocol.json'),
    'ladybug-49': dict(anchor=13568.634109445311, target=13704.320450539765, cap=4,
        target_source='/workspace/prism-caspar-expanded/measurement-plan.json (archived calibration anchor ×1.01)'),
    'trafalgar-126': dict(anchor=104534.24152926281, target=105579.58394455544, cap=4,
        target_source='/workspace/prism-model-followup/final-caspar-pairs/protocol.json'),
    'venice-951': dict(anchor=1999370.246783932, target=2019363.9492517712, cap=12,
        target_source='/workspace/prism-schur-recovery/extension/protocol.json'),
    'venice-1672': dict(anchor=2546133.54252996, target=2571594.8779552598, cap=12,
        target_source='/workspace/prism-caspar-expanded/measurement-plan.json (archived calibration anchor ×1.01)'),
    'venice-1778': dict(anchor=2078600.58293618, target=2099386.5887655416, cap=12,
        target_source='/workspace/prism-caspar-expanded/measurement-plan.json (archived calibration anchor ×1.01)'),
}


def main():
    ROOT.mkdir(exist_ok=True)
    specs = {}
    for scene, spec in SCENES.items():
        assert abs(spec['target']/spec['anchor'] - 1.01) < 2e-14
        specs[scene] = dict(spec, input_sha256=sha(BAL/(scene+'.txt')))
    proto = dict(
        phase='expanded10-convergence', host=socket.gethostname(), scenes=specs,
        arms=ARMS, reps=3, multiplier=1.01,
        binaries={arm: sha(BINS[arm]) for arm in ARMS}, flags=FLAGS,
        audit_relative_tolerance=1e-6, csv_logging=True,
        purpose='Predeclared mixed-size ten-scene panel. This is a complete fixed panel, not a post-hoc winner selection. All endpoint misses are plotted and reported.',
        clocks='Native solver clocks. Prism CSV begins after solver-local setup and is aligned to the same-run TARGET event. Caspar graph setup is excluded. Parsing, export and independent CPU audit are excluded.',
        order='Scene-major; rotate arms within each repeat; GPU serialized by flock.',
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
    for name in ['run_expanded10_convergence.py', 'schur_recovery_study.py', 'audit_prism_state.py']:
        shutil.copy2(pathlib.Path(__file__).parent/name, scripts/name)
    rows = []
    for scene, spec in specs.items():
        folder = ROOT/scene
        folder.mkdir(exist_ok=True)
        pending = any(not (folder/f'{scene}-{arm}-{rep}.result.json').exists()
                      for arm in ARMS for rep in range(1, proto['reps']+1))
        dims, obs = observations(BAL/(scene+'.txt')) if pending else (None, None)
        for rep in range(1, proto['reps']+1):
            shift = (rep-1) % len(ARMS)
            for arm in ARMS[shift:]+ARMS[:shift]:
                row = run_one(folder, scene, arm, rep, spec['target'], spec['cap'], dims, obs, proto,
                              trace_csv=True)
                rows.append(row)
                write(ROOT/'results.json', rows)
                write(ROOT/'summary.json', summarize(rows))
        del obs
    assert len(rows) == len(SCENES)*len(ARMS)*proto['reps']
    assert all(row['valid'] for row in rows), 'No unaudited or inconsistent endpoint can enter a curve.'
    print('COMPLETE', json.dumps(summarize(rows)), flush=True)


if __name__ == '__main__':
    main()
