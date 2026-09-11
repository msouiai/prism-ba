"""Preserve native diagnostic evidence without adding generated binaries."""
import hashlib
import json
import pathlib
import tarfile
ROOT = pathlib.Path(__file__).resolve().parent
data = pathlib.Path('/tmp/prism-geometry-agenda'); out = ROOT/'evidence'; out.mkdir(exist_ok=True)
archives = []
for scene in ['ladybug-49', 'dubrovnik-88', 'venice-52']:
    dest = out/f't1-{scene}.tar.xz'; files = []
    with tarfile.open(dest, 'w:xz', preset=3) as archive:
        for folder in sorted(data.glob(f't1-{scene}-*')):
            for path in sorted(folder.rglob('*')):
                if path.is_file():
                    archive.add(path, arcname=str(path.relative_to(data)))
                    files.append({'path': str(path.relative_to(data)), 'bytes': path.stat().st_size,
                                  'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    archives.append({'archive': dest.name, 'bytes': dest.stat().st_size,
                     'sha256': hashlib.sha256(dest.read_bytes()).hexdigest(), 'files': files})
    print(dest.name, dest.stat().st_size, flush=True)
(out/'manifest.json').write_text(json.dumps(archives, indent=2)+'\n')
