"""Fresh, fixed confirmation of the sole ordinary-opening survivor."""
import argparse
import json
import run_native as N

P = N.P
ARM = 'open-e0.05-w3-f3'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stage', choices=['practical', 'tails'])
    args = ap.parse_args()
    reg = N.register()
    registration = dict(parent=reg, arms=['off', ARM],
                        protocol_sha256=N.G.sha(P / 'CONFIRMATION_PROTOCOL.md'),
                        n_practical=3, n_tail=5)
    path = P / 'confirmation-registration.json'
    if path.exists():
        assert json.loads(path.read_text()) == registration
    else:
        N.G.write(path, registration)
    stage = 'confirmation-' + args.stage
    cells = (reg['practical'] if args.stage == 'practical' else
             [reg['cells'][s] for s in ['venice-52', 'final-3068']])
    rows = []
    for rep in range(3 if args.stage == 'practical' else 5):
        for cell in cells:
            for arm in (['off', ARM] if rep % 2 == 0 else [ARM, 'off']):
                rows.append(N.run(reg, stage, cell, arm, rep))
                N.G.write(P / (stage + '-results.json'), rows)
    print('COMPLETE', stage, len(rows), flush=True)


if __name__ == '__main__':
    main()
