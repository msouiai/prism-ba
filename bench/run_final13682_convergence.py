#!/usr/bin/env python3
"""Collect N=3 timed curves with the existing frozen solvers; no solver edits."""
import datetime
import json
import pathlib
import shutil
import socket

from schur_recovery_study import BINS, BAL, run_one, sha, summarize, write
from audit_prism_state import observations

ROOT = pathlib.Path('/workspace/prism-final13682-convergence')
SCENE = 'final-13682'


def main():
    ROOT.mkdir(exist_ok=True)
    prior = pathlib.Path('/workspace/prism-schur-recovery/extension/protocol.json')
    proto = json.loads(prior.read_text())
    proto.update(phase='convergence', host=socket.gethostname(),
                 scenes={SCENE: proto['scenes'][SCENE]},
                 source_protocol=str(prior), source_protocol_sha256=sha(prior),
                 csv_logging=True,
                 purpose='All four primary arms, fresh N3, same fixed target; stop at target, not a deep convergence run.',
                 clocks='Native solve clocks. Prism CSV begins after solver setup: align to the adjacent same-run final TARGET event, retaining final CSV flush delay. Caspar graph setup excluded; Prism solver-local setup included. Parsing, export and CPU audit excluded.',
                 order='Rotate the four arms each repeat; GPU serialized by flock.')
    for arm in proto['arms']:
        assert sha(BINS[arm]) == proto['binaries'][arm], arm
    assert sha(BAL/(SCENE+'.txt')) == proto['scenes'][SCENE]['input_sha256']
    pp = ROOT/'protocol.json'
    if pp.exists():
        assert json.loads(pp.read_text()) == proto
    else:
        write(pp, proto)
        write(ROOT/'created.json', {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()})
    scripts = ROOT/'scripts'
    scripts.mkdir(exist_ok=True)
    for name in ['run_final13682_convergence.py', 'schur_recovery_study.py', 'audit_prism_state.py']:
        shutil.copy2(pathlib.Path(__file__).parent/name, scripts/name)
    arms = proto['arms']
    pending = any(not (ROOT/f'{SCENE}-{arm}-{rep}.result.json').exists()
                  for arm in arms for rep in range(1, proto['reps']+1))
    dims, obs = observations(BAL/(SCENE+'.txt')) if pending else (None, None)
    rows = []
    spec = proto['scenes'][SCENE]
    for rep in range(1, proto['reps']+1):
        offset = (rep-1) % len(arms)
        for arm in arms[offset:]+arms[:offset]:
            row = run_one(ROOT, SCENE, arm, rep, spec['target'], spec['cap'], dims, obs, proto,
                          trace_csv=True)
            rows.append(row)
            write(ROOT/'results.json', rows)
            write(ROOT/'summary.json', summarize(rows))
    assert len(rows) == 12 and all(r['valid'] and r['hit'] for r in rows), 'Inspect all trials before plotting'
    print('COMPLETE', json.dumps(summarize(rows)), flush=True)


if __name__ == '__main__':
    main()
