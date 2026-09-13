#!/usr/bin/env python3
"""Freeze the retrospective D21 development calculation."""
from __future__ import annotations
import hashlib,json,math,pathlib,statistics

HERE=pathlib.Path(__file__).resolve().parent;W6=HERE.parent;W5=W6.parent/'eta2_wave5'
SOURCE=W5/'b6v7-extension-results.json'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

def summarize(k,rows):
 groups=[rows[i:i+k] for i in range(0,len(rows)-k+1,k)];walls=[];hits=[];used=[]
 for group in groups:
  wall=0.;ok=False
  for j,row in enumerate(group,1):
   wall+=row['target_seconds'] if row['hit'] else row['native_seconds']
   if row['hit']:ok=True;used.append(j);break
  if not ok:used.append(k)
  hits.append(ok);walls.append(wall)
 return {'attempt_cap':k,'groups':len(groups),'hits':sum(hits),'hit_rate':sum(hits)/len(hits),
         'native_time_median':statistics.median(walls),'native_time_mean':statistics.fmean(walls),
         'native_time_p90':sorted(walls)[math.ceil(.9*len(walls))-1],
         'attempts_median':statistics.median(used)}

def main():
 rows=sorted([r for r in json.loads(SOURCE.read_text()) if r['arm']=='gated'],key=lambda r:r['rep'])
 assert len(rows)==130 and [r['rep'] for r in rows]==list(range(20,150))
 x=[int(r['hit']) for r in rows];mean=statistics.fmean(x)
 covariance=sum((x[i]-mean)*(x[i-1]-mean) for i in range(1,len(x)))/(len(x)-1)
 variance=sum((v-mean)**2 for v in x)/len(x)
 result={'source':str(SOURCE),'source_sha256':sha(SOURCE),'rows':len(rows),
         'hit_lag1_correlation':covariance/variance,
         'summaries':[summarize(k,rows) for k in (1,2,3)],
         'selection':'three attempts: first cap with 100% grouped development hits and mean < historical MFREE cascade mean',
         'scope':'retrospective development only; fresh sequential cohort is confirmatory'}
 out=W6/'d21-development.json';out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()

