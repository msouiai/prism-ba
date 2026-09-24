#!/usr/bin/env python3
import pathlib,json,statistics,re
ROOT=pathlib.Path('/workspace/prism-adaptive-radius')
def main():
 for root,phase in [(ROOT,'adaptive'),(ROOT,'ray'),(pathlib.Path('/workspace/prism-early-radius'),'early'),(pathlib.Path('/workspace/prism-separate-tau'),'separate')]:
  p=root/phase/'results.json'
  if not p.exists():continue
  rows=json.loads(p.read_text());print('\nPHASE',phase,'runs',len(rows),'native',sum(r['native'] for r in rows),'maxaudit',max(r['audit_error'] for r in rows))
  for scene in ['trafalgar-126','dubrovnik-88']:
   for mode in sorted(set(r['mode'] for r in rows)):
    rr=[r for r in rows if r['scene']==scene and r['mode']==mode and r['rep']>0]
    if not rr:continue
    tt=[r['crossing'] for r in rr if r['hit']]
    print(scene,'mode',mode,'hit',len(tt),'/',len(rr),'median',statistics.median(tt) if len(tt)==len(rr) else None,'times',tt,'cost',[r['cost'] for r in rr],'mv',statistics.median(r['matvecs'] for r in rr),'rej',[r['rejects'] for r in rr])
if __name__=='__main__':main()
