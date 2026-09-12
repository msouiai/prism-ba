"""Fresh complete first-three-accept snapshots for E1; separate diagnostic cohort."""
from pathlib import Path
import json,os,sys,tempfile
import run_native as N
import forensics as F
sys.path.insert(0,str(N.W));import lossless_float_archive as FA
P=N.P
reg=N.register()
for rep in range(3):
 out=P/'opening-captures'/str(rep);out.mkdir(parents=True,exist_ok=True)
 if (out/'result.json').exists():continue
 with tempfile.TemporaryDirectory(prefix='e1-opening-',dir='/dev/shm') as tmp:
  tmp=Path(tmp);row=N.run(reg,'opening-diagnostic',reg['cells']['venice-52'],'opening',rep,dict(OCA_E1_CAPTURE=str(tmp)))
  folder=P/row['source'];waves=json.loads((folder/'wave.json').read_text());selected=[]
  for p in sorted(tmp.iterdir(),key=lambda p:int(p.name)):
   w=waves[int(p.name)]
   if not w['accepted'] or (w['raw_radius_ratio'] or 0)>1:
    label=f'venice-opening-{rep}-attempt{p.name}';ans=F.audit(p,'venice-52',label,cap_screen=False);ans['native_attempt']=w
    F.write(out/(label+'.json'),ans);selected.append(label)
  archive=Path(reg['states'])/f'opening-capture-{rep}.xor.tar.xz'
  files={str(p.relative_to(tmp)):p for p in tmp.rglob('*') if p.is_file()}
  hashes=FA.pack(archive,files);FA.verify(archive,hashes)
  F.write(out/'result.json',dict(diagnostic_run=row['source'],archive=str(archive),sha256=F.sha(archive),member_hashes=hashes,
    selected=selected,policy='All first-three-accept attempt snapshots retained; no scored timings from this instrumented capture'))
  print('OPENING CAPTURE',rep,'selected',selected,flush=True)
