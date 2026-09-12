"""Registered O2 experiment: original-L2 stage eligibility and full native clock."""
import argparse,json,re,shutil,subprocess
import run_aside as A
P,N=A.P,A.N
ARMS={'off':{},'homotopy':{'OCA_O2':'1'}}
N.ARMS=ARMS
def register():
 subprocess.run(['python3',str(N.G.F/'build.py'),'--check-only'],check=True)
 root=P/'o2';bm=json.loads((root/'build_manifest.json').read_text())
 assert N.G.sha(root/'build/prism-o2')==bm['binary_sha256']
 for name,h in bm['derived'].items():assert N.G.sha(root/'build'/name)==h
 for name,h in bm['local_headers'].items():assert N.G.sha(root/('build' if name=='attempt_trace.h' else '')/name)==h
 assert N.G.sha(root/'validation_manifest.json')==bm['validation_manifest_sha256']
 old=json.loads((A.W/'registration.json').read_text())
 reg=dict(build_manifest=bm,arms=ARMS,cells=old['cells'],practical=old['practical'],states=str(P/'durable_states'),native_binary=str(root/'build/prism-o2'),protocol_sha256=bm['protocol_sha256'],native_protocol_sha256=N.G.sha(P/'NATIVE_PROTOCOL.md'),runner_sha256=N.G.sha(__file__))
 f=P/'o2-registration.json'
 if f.exists():assert json.loads(f.read_text())==reg
 else:N.G.write(f,reg)
 return reg
def run(reg,stage,cell,arm,rep):
 if shutil.disk_usage(P).free<50_000_000:raise RuntimeError('Durable export reserve exhausted')
 r=N.run(reg,stage,cell,arm,rep);folder=P/r['source'];text=(folder/'stdout.log').read_text()
 events=[dict(kind=l.split()[0],**dict(re.findall(r'(\w+)=(\S+)',l))) for l in text.splitlines() if l.startswith(('O2_INIT ','O2_STAGE ','O2_TRACE ','O2_SUMMARY '))]
 r['opening_events']=events
 summary=next((e for e in events if e['kind']=='O2_SUMMARY'),{})
 r['full_objective_entered']=arm=='off' or summary.get('full_objective_entered')=='1'
 r['opening_completed']=arm=='off' or summary.get('schedule_complete')=='1'
 r['hit']=bool(r['hit'] and r['full_objective_entered'] and 'TARGET reached ' in text)
 r['charged_target_seconds']=r['native_seconds'] if r['hit'] else None
 r['original_l2_target_crossings']=[e for e in events if e['kind']=='O2_TRACE' and e['crossing'] in ['down','up']]
 N.G.write(folder/'result.json',r);return r
def main():
 ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['tails','practical']);a=ap.parse_args();reg=register();rows=[]
 if a.stage=='tails':cells=[reg['cells'][s] for s in ['venice-52','final-3068']];count=5
 else:
  old=json.loads((P/'o2-tails-results.json').read_text());scenes=['venice-52','final-3068']
  h=lambda arm,scene:sum(r['hit'] for r in old if r['arm']==arm and r['scene']==scene)
  passed=all(h('homotopy',s)>=h('off',s) for s in scenes) and any(h('homotopy',s)>h('off',s) for s in scenes)
  N.G.write(P/'o2-practical-selection.json',dict(passed=passed,rule='One tail gain, no opposite-tail loss'))
  if not passed:N.G.write(P/'o2-practical-results.json',[]);print('O2 no practical survivor');return
  cells=reg['practical'];count=3
 for rep in range(count):
  for cell in cells:
   for arm in list(ARMS) if rep%2==0 else list(reversed(ARMS)):
    rows.append(run(reg,'o2-final-'+a.stage,cell,arm,rep));N.G.write(P/('o2-'+a.stage+'-results.json'),rows)
 print('COMPLETE O2',a.stage,len(rows),flush=True)
if __name__=='__main__':main()
