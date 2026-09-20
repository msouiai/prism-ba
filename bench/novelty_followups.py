#!/usr/bin/env python3
"""Select global profiles from declared development cells, then freeze evaluation."""
import json,pathlib,statistics,math,subprocess,time,sys
ROOT=pathlib.Path('/workspace/prism-novelty');REPO=pathlib.Path('/workspace/prism-ba')
def choose(kind):
 folder=ROOT/('ceres-tuning' if kind=='ceres' else 'caspar32-development')
 profiles=['lm-10000','lm-1','dogleg-10000','dogleg-1'] if kind=='ceres' else ['default','paper']
 budgets=[600] if kind=='ceres' else [2000]
 records={}
 for profile in profiles:
  rr=[]
  for scene in ['venice-52','ladybug-1197']:
   for rep in [1,2,3]:
    f=folder/f'{scene}-{kind}-{profile}-{budgets[0]}-{rep}.json'
    if not f.exists():return None
    rr.append(json.loads(f.read_text()))
  bad=sum(r.get('status')!='ok' for r in rr);ok=[r for r in rr if r.get('status')=='ok']
  records[profile]=dict(failures=bad,geomean_cost=math.exp(statistics.mean(math.log(r['cost']) for r in ok)) if ok else 1e300,geomean_wall=math.exp(statistics.mean(math.log(r['seconds']) for r in ok)) if ok else 1e300)
 groups=[['lm-10000','lm-1'],['dogleg-10000','dogleg-1']] if kind=='ceres' else [['default','paper']]
 selected=[]
 for group in groups:
  candidates=[p for p in group if records[p]['failures']==min(records[q]['failures'] for q in group)]
  best=min(records[p]['geomean_cost'] for p in candidates);eligible=[p for p in candidates if records[p]['geomean_cost']<=best*1.0015]
  selected.append(min(eligible,key=lambda p:records[p]['geomean_wall']))
 return dict(kind=kind,profiles=selected,development=['venice-52','ladybug-1197'],rule='fewest failures, cost GM within 0.15% of minimum, then wall GM',metrics=records)
def run(kind,selection):
 path=ROOT/f'{kind}-selection.json'
 if path.exists():assert json.loads(path.read_text())==selection
 else:path.write_text(json.dumps(selection,indent=2)+'\n')
 print('FROZEN',kind,selection['profiles'],flush=True)
 profiles=selection['profiles']
 # Stock Caspar remains visible alongside the globally selected profile.
 if kind=='caspar32':profiles=list(dict.fromkeys(['default']+profiles))
 for phase,data,scenes in [
   ('evaluation','/workspace/bal',['ladybug-598','trafalgar-126','dubrovnik-173','venice-1672','final-3068','final-4585']),
   ('perturbed',str(ROOT/'perturbed'),[f'{s}-seed{k}' for s in ['venice-52','final-3068'] for k in [17,29,43]])]:
  command=[sys.executable,str(REPO/'bench/novelty_external.py'),'--kind',kind,'--binary',str(ROOT/('ceres-frozen' if kind=='ceres' else 'caspar32-frozen')),'--out',str(ROOT/f'{kind}-{phase}'),'--data',data,'--scenes',*scenes,'--profiles',*profiles]
  with (ROOT/f'{kind}-{phase}-progress.log').open('a') as f:subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,check=True)
if __name__=='__main__':
 kind=sys.argv[1]
 while True:
  selected=choose(kind)
  if selected is not None:break
  time.sleep(10)
 run(kind,selected)
