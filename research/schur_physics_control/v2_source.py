"""Locate the delivered source, or restore the small checksummed source archive."""
import pathlib,os,json,hashlib,tarfile
ROOT=pathlib.Path(__file__).resolve().parent
def locate():
    manifest=json.loads((ROOT/'evidence/v2-source-manifest.json').read_text())
    vendor=pathlib.Path(os.environ.get('PRISM_V2_SOURCE','/workspace/multishift_repro'))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    if not (vendor/'oca_cuda_v2.cu').exists():
        vendor=ROOT/'build/v2-source';vendor.mkdir(parents=True,exist_ok=True)
        archive=ROOT/'evidence/v2-source.tar.xz'
        assert sha(archive)==manifest['archive_sha256']
        with tarfile.open(archive) as t:t.extractall(vendor,filter='data')
    assert all(sha(vendor/name)==h for name,h in manifest['files'].items()),'v2 source/header hash mismatch'
    binary=vendor/'oca_cuda_v2'
    if binary.exists():assert sha(binary)==manifest['delivered_binary_sha256']
    return vendor,manifest
