#!/usr/bin/env python3
"""Download the public scenes named in REPRODUCE.md (22 distinct files)."""
import argparse, bz2, concurrent.futures, pathlib, re, urllib.request
BASE='https://grail.cs.washington.edu/projects/bal/'
SCENES={'ladybug':[49,598,810,1197,1469,1723], 'trafalgar':[126,201,257],
        'dubrovnik':[88,135,173,356], 'venice':[52,89,1672,1778],
        'final':[93,1936,3068,4585,13682]}

# Additional public large cases; do not alter the default REPRODUCE download set.
EXTRA_SCENES={'final':[871,961], 'venice':[951]}

def download(scene, dest):
    family,n=scene.rsplit('-',1)
    if family not in SCENES or int(n) not in SCENES[family]+EXTRA_SCENES.get(family,[]):
        raise ValueError(f'Unknown public benchmark scene: {scene}')
    path=dest/(scene+'.txt')
    if path.exists(): return str(path)
    with urllib.request.urlopen(BASE+family+'.html',timeout=60) as f:
        page=f.read().decode()
    match=re.search(r'data/'+family+r'/problem-'+n+r'-\d+-pre.txt.bz2',page)
    if not match: raise RuntimeError(f'No download for {scene}')
    temporary=path.with_suffix('.partial')
    with urllib.request.urlopen(BASE+match[0],timeout=60) as source,temporary.open('wb') as out:
        dec=bz2.BZ2Decompressor()
        for chunk in iter(lambda:source.read(1<<20),b''): out.write(dec.decompress(chunk))
        if not dec.eof: raise RuntimeError('Truncated bzip2 download')
    temporary.replace(path)
    return str(path)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dest',type=pathlib.Path,required=True)
    p.add_argument('--scenes',nargs='+');p.add_argument('--workers',type=int,default=3)
    a=p.parse_args();a.dest.mkdir(parents=True,exist_ok=True)
    scenes=a.scenes or [f'{f}-{n}' for f,ns in SCENES.items() for n in ns]
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        for result in pool.map(lambda scene:download(scene,a.dest),scenes): print(result,flush=True)

if __name__=='__main__':main()
