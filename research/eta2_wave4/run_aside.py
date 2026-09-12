"""Fresh acceptance-ablation cohorts on the frozen objective and targets."""
from pathlib import Path
import argparse, json, re, shutil, subprocess, sys

P = Path(__file__).resolve().parent
W = P.parent / 'eta2_wave3'
sys.path.insert(0, str(W))
import run_native as N

N.P = P
N.G.P = P
ARMS = {'off': {}, 'rho001': {'OCA_W4_RHO_MIN': '0.001'},
        'rho01': {'OCA_W4_RHO_MIN': '0.01'},
        'nonmonotone5': {'OCA_W4_RHO_MIN': '0.001', 'OCA_W4_NONMONOTONE': '5'}}
N.ARMS = ARMS


def register():
    subprocess.run(['python3', str(N.G.F / 'build.py'), '--check-only'], check=True)
    bm = json.loads((P / 'aside_build_manifest.json').read_text())
    assert N.G.sha(P / 'build/prism-aside') == bm['binary_sha256']
    assert all(N.G.sha(p) == h for p, h in bm['sources'].items())
    old = json.loads((W / 'registration.json').read_text())
    reg = dict(build_manifest=bm, arms=ARMS, cells=old['cells'], practical=old['practical'],
               states=str(P / 'durable_states'), native_binary=str(P / 'build/prism-aside'),
               protocol_sha256=N.G.sha(P / 'PROTOCOL.md'),
               native_protocol_sha256=N.G.sha(P / 'NATIVE_PROTOCOL.md'))
    path = P / 'aside-registration.json'
    if path.exists():
        assert json.loads(path.read_text()) == reg
    else:
        N.G.write(path, reg)
    return reg


def run(reg, stage, cell, arm, rep):
    # Reserve one large Final3068 export plus metadata, before native work.
    if shutil.disk_usage(P).free < 50_000_000:
        raise RuntimeError('Durable export reserve exhausted; no native run launched')
    row = N.run(reg, stage, cell, arm, rep)
    folder = P / row['source']
    events = []
    for line in (folder / 'stdout.log').read_text().splitlines():
        if line.startswith(('W4_ACCEPT ', 'W4_FINAL ', 'W4_SUMMARY ')):
            events.append(dict(kind=line.split()[0], **dict(re.findall(r'(\w+)=(\S+)', line))))
    row['acceptance_events'] = events
    N.G.write(folder / 'result.json', row)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['compatibility', 'smoke', 'tails', 'practical'])
    args = ap.parse_args()
    reg = register()
    rows = []
    stage = 'aside-' + args.stage
    if args.stage == 'compatibility':
        arms, cells, count = ['original', 'off'], [reg['cells']['dubrovnik-88']], 3
    elif args.stage == 'smoke':
        # Correctness/instrumentation observations, not a tail or speed claim.
        arms, cells, count = ['rho001', 'rho01', 'nonmonotone5'], [reg['cells']['dubrovnik-88']], 1
    elif args.stage == 'tails':
        assert len(json.loads((P / 'aside-compatibility-results.json').read_text())) == 6
        assert json.loads((P / 'aside-validation.json').read_text())['passed']
        arms, cells, count = list(ARMS), [reg['cells'][s] for s in ['venice-52', 'final-3068']], 5
    else:
        old = json.loads((P / 'aside-tails-results.json').read_text())
        def hits(arm, scene):
            return sum(r['hit'] for r in old if r['arm'] == arm and r['scene'] == scene)
        scenes = ['venice-52', 'final-3068']
        arms = ['off'] + [a for a in ARMS if a != 'off' and
                         all(hits(a, s) >= hits('off', s) for s in scenes) and
                         any(hits(a, s) > hits('off', s) for s in scenes)]
        N.G.write(P / 'aside-practical-selection.json', dict(arms=arms, rule='Observed tail gain with no opposite-tail hit-count loss'))
        if arms == ['off']:
            N.G.write(P / (stage + '-results.json'), [])
            print('No aside survivor for practical panel')
            return
        cells, count = reg['practical'], 3
    for rep in range(count):
        for cell in cells:
            for arm in (arms if rep % 2 == 0 else list(reversed(arms))):
                rows.append(run(reg, stage, cell, arm, rep))
                N.G.write(P / (stage + '-results.json'), rows)
    print('COMPLETE', stage, len(rows), flush=True)


if __name__ == '__main__':
    main()
