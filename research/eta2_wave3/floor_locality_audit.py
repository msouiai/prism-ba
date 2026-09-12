"""Confirm the spectral-floor locality gate on an actual practical-panel scene."""
from pathlib import Path
import json,tempfile
import run_native as N
import forensics as F
P=N.P;reg=N.register();cell=next(c for c in reg['practical'] if c['scene']=='ladybug-539' and c['cell'].endswith('1.01'))
out=P/'floor-locality';out.mkdir(exist_ok=True);allrows=[]
for rep in range(3):
 marker=out/f'{rep}.json'
 if marker.exists():allrows.append(json.loads(marker.read_text()));continue
 with tempfile.TemporaryDirectory(prefix='e2-floor-locality-',dir='/dev/shm') as tmp:
  tmp=Path(tmp);run=N.run(reg,'floor-locality-diagnostic',cell,'off',rep,dict(OCA_E1_CAPTURE=str(tmp)))
  records=[]
  for p in sorted(tmp.iterdir(),key=lambda p:int(p.name)):
   r=F.audit(p,'ladybug-539',f'ladybug-539-{rep}-attempt{p.name}',cap_screen=False,problem=cell['path'])
   records.append(r)
  archive=P/'durable_states'/f'floor-locality-{rep}.xor.tar.xz';archive.parent.mkdir(exist_ok=True)
  hashes=F.FA.pack(archive,{str(p.relative_to(tmp)):p for p in tmp.rglob('*') if p.is_file()});F.FA.verify(archive,hashes)
  result=dict(rep=rep,records=records,archive=str(archive),sha256=F.sha(archive),member_sha256=hashes)
  F.write(marker,result);allrows.append(result)
F.write(out/'summary.json',dict(rows=[dict(rep=r['rep'],attempt=x['label'],floors=x['floor_locality_screen']) for r in allrows for x in r['records']]))
print('FLOOR LOCALITY COMPLETE',flush=True)
