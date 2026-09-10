#!/usr/bin/env python3
"""Build the isolated, checksum-verified eta2 research solver."""
import argparse
import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arch', default='sm_89', help='CUDA architecture for the destination GPU')
    ap.add_argument('--nvcc', default='nvcc')
    ap.add_argument('--eigen', default='/usr/include/eigen3')
    ap.add_argument('--check-only', action='store_true')
    args = ap.parse_args()
    manifest = json.loads((ROOT/'source_manifest.json').read_text())
    source = ROOT/'source/prism_eta2.cu'
    headers = ROOT/'source/headers'
    assert sha(source) == manifest['source_sha256'], 'Frozen source changed'
    assert all(sha(headers/name) == h for name,h in manifest['headers_sha256'].items()), 'Frozen header changed'
    print('Verified frozen source and', len(manifest['headers_sha256']), 'headers.', flush=True)
    if args.check_only:
        return
    output = ROOT/'build'
    output.mkdir(exist_ok=True)
    command = [args.nvcc, '-O3', '-DNDEBUG', '-std=c++17', '-arch='+args.arch,
               '-I'+args.eigen, '-I'+str(headers), str(source), '-o', str(output/'prism-eta2'),
               '-lcublas', '-lcusolver']
    with (output/'build.log').open('w') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
    (output/'build_manifest.json').write_text(json.dumps(dict(command=command,
        binary_sha256=sha(output/'prism-eta2'),source_sha256=manifest['source_sha256']),indent=2)+'\n')
    print(output/'prism-eta2')

if __name__ == '__main__':
    main()
