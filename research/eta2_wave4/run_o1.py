"""O1 full-clock opening evaluation; failed QPs are labeled, never called optima."""
import argparse,json,re,shutil,subprocess
import run_aside as A
P,N=A.P,A.N
ARMS={'off':{},**{f'oi{k}':{'OCA_O1_SWEEPS':str(k)} for k in [3,5,10]}}
N.ARMS=ARMS
def register():
 subprocess.run(['python3',str(N.G.F/'build.py'),'--check-only'],check=True)
 bm=json.loads((P/'o1_build_manifest.json').read_text());b=P/'build/prism-o1'
 assert N.G.sha(b)==bm['binary_sha256'];assert all(N.G.sha(p)==h for p,h in bm['sources'].items())
 old=json.loads((A.W/'registration.json').read_text());reg=dict(build_manifest=bm,arms=ARMS,cells=old['cells'],practical=old['practical'],states=str(P/'durable_states'),native_binary=str(b),protocol_sha256=N.G.sha(P/'O1_PROTOCOL.md'),native_protocol_sha256=N.G.sha(P/'NATIVE_PROTOCOL.md'))
 dest=P/'o1-registration.json'
 if dest.exists():assert json.loads(dest.read_text())==reg
 else:N.G.write(dest,reg)
 return reg
def run(reg,stage,cell,arm,rep):
 if shutil.disk_usage(P).free<50_000_000:raise RuntimeError('Durable export reserve exhausted')
 r=N.run(reg,stage,cell,arm,rep);folder=P/r['source'];text=(folder/'stdout.log').read_text()
 events=[dict(kind=l.split()[0],**dict(re.findall(r'(\w+)=(\S+)',l))) for l in text.splitlines() if l.startswith(('O1_INIT ','O1_SWEEP ','O1_QP ','O1_FINAL '))]
 r['opening_events']=events;end=next((e for e in events if e['kind']=='O1_FINAL'),{})
 r['opening_completed']=arm in ['off','original'] or end.get('complete')=='1'
 r['opening_accepted_sweeps']=int(end.get('accepted',0));r['opening_seconds']=float(end.get('seconds',0));r['opening_stop']=end.get('reason','disabled')
 r['charged_target_seconds']=r['native_seconds'] if r['hit'] else None
 N.G.write(folder/'result.json',r);return r
def main():
 ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['compatibility','smoke','tails','practical']);a=ap.parse_args();reg=register();rows=[]
 if a.stage=='compatibility':arms=['original','off'];cells=[reg['cells']['dubrovnik-88']];count=3
 elif a.stage=='smoke':
  assert json.loads((P/'o1-kernel-validation.json').read_text())['passed']
  arms=['oi3'];cells=[reg['cells']['dubrovnik-88']];count=1
 elif a.stage=='tails':
  assert json.loads((P/'o1-native-validation.json').read_text())['passed']
  arms=list(ARMS);cells=[reg['cells'][s] for s in ['venice-52','final-3068']];count=5
 else:
  old=json.loads((P/'o1-tails-results.json').read_text())
  h=lambda arm:sum(r['hit'] for r in old if r['arm']==arm and r['scene']=='final-3068')
  arms=['off']+[arm for arm in ARMS if arm!='off' and h(arm)>h('off') and any(r['opening_accepted_sweeps']>0 for r in old if r['arm']==arm and r['scene']=='final-3068')]
  N.G.write(P/'o1-practical-selection.json',dict(arms=arms,rule='Final3068 observed hit-count gain with at least one accepted valid QP sweep'))
  if arms==['off']:N.G.write(P/'o1-practical-results.json',[]);print('O1 no practical survivor');return
  cells=reg['practical'];count=3
 for rep in range(count):
  for cell in cells:
   for arm in arms if rep%2==0 else list(reversed(arms)):
    rows.append(run(reg,'o1-v1-'+a.stage,cell,arm,rep));N.G.write(P/('o1-'+a.stage+'-results.json'),rows)
 print('COMPLETE O1',a.stage,len(rows),flush=True)
if __name__=='__main__':main()
