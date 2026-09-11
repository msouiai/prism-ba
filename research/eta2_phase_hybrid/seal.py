#!/usr/bin/env python3
"""Hash the compact research package; native binaries have build manifests."""
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent
files = {}
for f in sorted(P.rglob('*')):
    rel = f.relative_to(P)
    if not f.is_file() or any(part in {'build', 'build_collapse', '__pycache__'} for part in rel.parts):
        continue
    if rel.name == 'artifact_manifest.json' or len(rel.parts) == 1 and f.suffix == '.log':
        continue
    files[str(rel)] = dict(bytes=f.stat().st_size, sha256=hashlib.sha256(f.read_bytes()).hexdigest())
(P / 'artifact_manifest.json').write_text(json.dumps(dict(files=files), indent=2) + '\n')
print(f'Sealed {len(files)} files, {sum(f["bytes"] for f in files.values())} bytes')
