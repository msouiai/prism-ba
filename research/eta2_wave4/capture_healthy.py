"""Capture actual joint healthy directions for denominator/locality checks."""
from pathlib import Path
import json, tempfile, sys
import run_aside as A

P, N = A.P, A.N
sys.path.insert(0, str(P.parent / 'eta2_wave2'))
import lossless_float_archive as FA


def main():
    reg = A.register()
    bm = json.loads((A.W / 'e4_build_manifest.json').read_text())
    binary = A.W / 'build/prism-e4'
    assert N.G.sha(binary) == bm['binary_sha256']
    reg = dict(reg, native_binary=str(binary), build_manifest=bm)
    cell = next(c for c in reg['practical'] if c['cell'] == 'ladybug-539-1.005')
    out = P / 'healthy-captures'
    out.mkdir(exist_ok=True)
    records = []
    for rep in range(3):
        dest = out / f'{rep}.json'
        if dest.exists():
            records.append(json.loads(dest.read_text()))
            continue
        with tempfile.TemporaryDirectory(prefix='wave4-healthy-', dir='/dev/shm') as temp:
            root = Path(temp)
            row = N.run(reg, 'o3-healthy-diagnostic', cell, 'off', rep,
                        dict(OCA_E4_CAPTURE=str(root)))
            dirs = sorted((p for p in root.iterdir() if (p/'accepted.step').exists()),
                          key=lambda p: int(p.name))
            assert dirs
            selected = dirs[:3]
            files = {str(f.relative_to(root)):f for p in selected for f in p.iterdir() if f.is_file()}
            files.update({str(f.relative_to(root)):f for f in root.rglob('*.txt')})
            hashes = {str(f.relative_to(root)):N.G.sha(f) for f in root.rglob('*') if f.is_file()}
            archive = P / 'durable_states' / f'o3-healthy-{rep}.xor.tar.xz'
            retained = FA.pack(archive, files)
            FA.verify(archive, retained)
            record = dict(rep=rep, result=row, archive=str(archive), sha256=N.G.sha(archive),
                          selected_attempts=[int(x.name) for x in selected],
                          retained_member_sha256=retained, all_new_capture_hashes=hashes,
                          protocol_sha256=N.G.sha(P/'O3_CAPTURE_PROTOCOL.md'),
                          omitted='Unselected newly captured intermediate arrays omitted; hashes cannot restore them')
            N.G.write(dest, record)
            records.append(record)
    N.G.write(out/'index.json', records)
    print('HEALTHY CAPTURES COMPLETE', len(records), flush=True)


if __name__ == '__main__':
    main()
