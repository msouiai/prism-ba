"""Losslessly pack idle historical exports; verify bytes before unlinking raw copy.

Paths and hashes are retained here so historical consumers can restore raw files.
No existing gzip or source/input evidence is overwritten.
"""
from pathlib import Path
import gzip, hashlib, json, shutil

HERE = Path(__file__).resolve().parent

def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()

def main():
    manifest = HERE / 'storage_compression.json'
    rows = json.loads(manifest.read_text()) if manifest.exists() else []
    candidates = sorted(Path('/tmp/prism-cg-value-noise/inputs').glob('*.txt'))
    candidates += sorted(Path('/tmp/prism-rl-actor/runs').rglob('endpoint.state'))
    candidates += sorted(Path('/tmp/prism-rl-curvature/runs').rglob('endpoint.state'))
    for p in candidates:
        if shutil.disk_usage('/').free > 2_000_000_000: break
        if p.is_symlink() or not p.is_file(): continue
        dest = Path(str(p) + '.gz')
        if dest.exists(): continue
        rawhash, size = sha(p), p.stat().st_size
        with p.open('rb') as src, gzip.open(dest, 'wb', compresslevel=6) as dst:
            shutil.copyfileobj(src, dst)
        with gzip.open(dest, 'rb') as f:
            assert hashlib.file_digest(f, 'sha256').hexdigest() == rawhash
        assert sha(p) == rawhash
        rows.append(dict(path=str(p), gzip=str(dest), raw_sha256=rawhash,
                         gzip_sha256=sha(dest), raw_bytes=size,
                         gzip_bytes=dest.stat().st_size, verified=True))
        manifest.write_text(json.dumps(rows, indent=2) + '\n')
        p.unlink()  # Exact bytes already retained and verified in durable gzip.
        print('PACKED', p, 'saved', size-dest.stat().st_size,
              'free', shutil.disk_usage('/').free, flush=True)

if __name__ == '__main__': main()
