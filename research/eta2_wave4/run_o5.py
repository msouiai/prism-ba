"""O5 off/robust-opening experiment with the shared full-L2 scorer."""
from pathlib import Path
import argparse,json,re,shutil,statistics,subprocess
import run_aside as A
P,N=A.P,A.N
ARMS={'off':{},'cauchy':{'OCA_W5_CAUCHY':'1'}}
N.ARMS=ARMS
def register():
 subprocess.run(['python3',str(N.G.F/'build.py'),'--check-only'],check=True)
 bm=json.loads((P/'o5_build_manifest.json').read_text());b=P/'build/prism-o5'
 assert N.G.sha(b)==bm['binary_sha256']
 assert all(N.G.sha(p)==h for p,h in bm['sources'].items())
 old=json.loads((A.W/'registration.json').read_text())
 reg=dict(build_manifest=bm,arms=ARMS,cells=old['cells'],practical=old['practical'],states=str(P/'durable_states'),native_binary=str(b),protocol_sha256=N.G.sha(P/'O5_PROTOCOL.md'),native_protocol_sha256=N.G.sha(P/'NATIVE_PROTOCOL.md'))
 dest=P/'o5-registration.json'
 if dest.exists():assert json.loads(dest.read_text())==reg
 else:N.G.write(dest,reg)
 return reg
def run(reg,stage,cell,arm,rep):
 if shutil.disk_usage(P).free<50_000_000:raise RuntimeError('Durable export reserve exhausted')
 r=N.run(reg,stage,cell,arm,rep);folder=P/r['source'];text=(folder/'stdout.log').read_text()
 r['opening_events']=[dict(kind=l.split()[0],**dict(re.findall(r'(\w+)=(\S+)',l))) for l in text.splitlines() if l.startswith(('W5_INIT ','W5_STAGE ','W5_L2 ','W5_FINAL '))]
 events=r['opening_events']
 r['full_objective_entered']=arm!='cauchy' or any(e['kind']=='W5_FINAL' and e['stage']=='4' for e in events)
 transitions=[e for e in events if e['kind']=='W5_STAGE']
 r['opening_completed']=arm!='cauchy' or ([int(e['stage']) for e in transitions]==[1,2,3,4] and all(e['capped']=='0' and e['stop']=='0' for e in transitions))
 r['scored_target_eligible']=r['full_objective_entered']
 r['hit']=bool(r['hit'] and r['scored_target_eligible'])
 r['charged_target_seconds']=r['native_seconds'] if r['hit'] else None
 series=[dict(outer=int(e['o']),stage=int(e['stage']),cost=float(e['l2'])) for e in events if e['kind']=='W5_L2']
 crossings=[];previous=r['score_init']
 for e in series:
  if (previous>cell['target']) != (e['cost']>cell['target']):crossings.append(dict(e,direction='down' if e['cost']<=cell['target'] else 'up',scored_eligible=e['stage']==4))
  previous=e['cost']
 r['original_l2_target_crossings']=crossings
 N.G.write(folder/'result.json',r);return r
def main():
 ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['compatibility','smoke','tails','practical']);a=ap.parse_args();reg=register();rows=[]
 if a.stage=='compatibility':arms=['original','off'];cells=[reg['cells']['dubrovnik-88']];count=3
 elif a.stage=='smoke':
  assert json.loads((P/'o5-kernel-validation.json').read_text())['passed']
  arms=['cauchy'];cells=[reg['cells']['dubrovnik-88']];count=1
 elif a.stage=='tails':
  assert json.loads((P/'o5-native-validation.json').read_text())['passed']
  arms=list(ARMS);cells=[reg['cells'][s] for s in ['venice-52','final-3068']];count=5
 else:
  old=json.loads((P/'o5-tails-results.json').read_text());scenes=['venice-52','final-3068']
  h=lambda arm,scene:sum(r['hit'] for r in old if r['arm']==arm and r['scene']==scene)
  passed=all(h('cauchy',s)>=h('off',s) for s in scenes) and any(h('cauchy',s)>h('off',s) for s in scenes)
  N.G.write(P/'o5-practical-selection.json',dict(passed=passed,rule='One tail gain, no opposite-tail loss'))
  if not passed:N.G.write(P/'o5-practical-results.json',[]);print('O5 no practical survivor');return
  arms=list(ARMS);cells=reg['practical'];count=3
 for rep in range(count):
  for cell in cells:
   for arm in arms if rep%2==0 else reversed(arms):
    rows.append(run(reg,'o5-v2-'+a.stage,cell,arm,rep));N.G.write(P/('o5-'+a.stage+'-results.json'),rows)
 print('COMPLETE O5',a.stage,len(rows),flush=True)
if __name__=='__main__':main()
