"""Collect the bounded internal solver ablation; never omit misses."""
import hashlib
import json
from pathlib import Path

ROOT = Path('/workspace/prism-tr-novelty-ablation')
GROUPS = ['small', 'large', 'lm-sensitivity', 'lm-sensitivity-large-complete']


def main():
    rows = []
    for group in GROUPS:
        for row in json.loads((ROOT / group / 'results.json').read_text()):
            assert row['returncode'] == 0
            assert row['audit_error'] < 1e-7
            rows.append(dict(group=group, **row))
    assert len(rows) == 49
    manifest = json.loads((ROOT / 'build/manifest.json').read_text())
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha(ROOT / 'build/prism-tr') == manifest['binary_sha256']
    assert sha(ROOT / 'build/source.cu') == manifest['source_sha256']
    for name, expected in manifest['headers_sha256'].items():
        assert sha(ROOT / 'build/headers' / name) == expected
    production = sha(Path('/workspace/prism-ba/gpu/oca_cuda.cu'))
    assert production == '0b7aac9b70523ce08d791e1a75c6c18a672cdfb29f28c6a3ab21c0bf5e786569'
    paused = json.loads(Path('/workspace/prism-block-error/paused-verified.json').read_text())
    for job in paused:
        stat = Path(f'/proc/{job["pid"]}/stat').read_text().split()
        assert stat[2] == 'T' and stat[21] == str(job['start_ticks'])
    report = dict(
        runs=len(rows), hits=sum(r['hit'] for r in rows),
        accepted_checks=sum(r['accepted_checks'] for r in rows),
        maximum_endpoint_audit_error=max(r['audit_error'] for r in rows),
        native_seconds=sum(r['seconds'] for r in rows),
        production_sha256=production, paused_jobs_verified=len(paused),
        binary_sha256=manifest['binary_sha256'], rows=rows,
    )
    (ROOT / 'verification.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != 'rows'}, indent=2))


if __name__ == '__main__':
    main()
