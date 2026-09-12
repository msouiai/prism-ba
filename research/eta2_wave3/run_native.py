"""Serial, registered wave-3 native cohorts; compact records plus durable states."""
from pathlib import Path
import argparse,hashlib,json,os,re,statistics,subprocess,sys,tempfile
P=Path(__file__).resolve().parent;C=P.parent/'eta2_research_20260912';W=P.parent/'eta2_wave2'
sys.path.insert(0,str(C));import grid_common as G
G.P=P
ARMS={'off':{},'cap30':{'OCA_E2_CAP':'30'},'intrinsic':{'OCA_E3_GATE':'1'},
      'opening':{'OCA_W3_FORCE':'1','OCA_W3_UNCLIP':'1'}}
for eta in [.05,.1,.2]:
 for window in [1,2,3]:
  for forcing in sorted({1,window}):
   name=f'open-e{eta}-w{window}-f{forcing}'
   ARMS[name]=dict(OCA_W3_FORCE='1',OCA_W3_UNCLIP='1',OCA_E3_ETA=str(eta),OCA_E3_WINDOW=str(window),OCA_E3_FORCE_WINDOW=str(forcing))

def register():
 subprocess.run(['python3',str(G.F/'build.py'),'--check-only'],check=True)
 bm=json.loads((P/'build_manifest.json').read_text())
 assert G.sha(P/'build/prism-wave3')==bm['binary_sha256']
 assert all(G.sha(p)==h for p,h in bm['sources'].items())
 cells={}
 for scene,target in [('venice-52',243740.27),('final-3068',1744796.9841897595),('dubrovnik-88',0)]:
  path=Path('/workspace/bal')/(scene+'.txt');cells[scene]=dict(scene=scene,path=str(path),input_sha256=G.sha(path),target=target,cap=60)
 reg=dict(build_manifest=bm,arms=ARMS,cells=cells,practical=json.loads((C/'native-panel.json').read_text())['practical'],
          protocol_sha256=G.sha(P/'NATIVE_PROTOCOL.md'),witness_selection=json.loads((P/'witness_selection.json').read_text()),
          states='/workspace/eta2-wave3-evidence',native_binary=str(P/'build/prism-wave3'),n_tail=5,n_practical=3)
 f=P/'registration.json'
 if f.exists():assert json.loads(f.read_text())==reg
 else:G.write(f,reg)
 return reg

def run(reg,stage,cell,arm,rep,extra=None):
 cid=cell.get('cell',cell['scene']);folder=P/'evidence'/stage/f'{cid}-{arm}-{rep}'
 if (folder/'result.json').exists():
  row=json.loads((folder/'result.json').read_text());assert row['valid'] and 'state' in row,row;return row
 folder.mkdir(parents=True,exist_ok=True)
 assert G.sha(cell['path'])==cell['input_sha256']
 fd,raw=tempfile.mkstemp(prefix='eta2-wave3-',suffix='.state',dir='/dev/shm');os.close(fd);temporary=Path(raw)
 (folder/'endpoint.state').symlink_to(temporary)
 # Capacity-only placement; exact content/hash and scoring protocol unchanged.
 # Keep the last workspace headroom for diagnostic archives. Both are durable.
 existing_bytes=sum(p.stat().st_size for p in Path(reg['states']).rglob('*') if p.is_file()) if Path(reg['states']).exists() else 0
 state_root=P/'durable_states' if existing_bytes>270_000_000 else Path(reg['states'])
 durable=state_root/stage/f'{cid}-{arm}-{rep}.state.gz';durable.parent.mkdir(parents=True,exist_ok=True)
 assert not durable.exists();(folder/'endpoint.state.gz').symlink_to(durable)
 G.write(folder/'staging.json',dict(raw=str(temporary),compressed=str(durable),policy='raw RAM copy retained until durable hash verification'))
 flags=dict(ARMS.get(arm,{}));flags.update(extra or {})
 binary=G.ORIGINAL if arm=='original' else Path(reg['native_binary'])
 if arm!='original':flags.update(OCA_WAVE_TRACE=str(folder/'wave.json'),OCA_STCG_ATTEMPTS=str(folder/'attempts.json'))
 row=G.run(folder,cell['scene'],arm,rep,binary,flags,P/'NATIVE_PROTOCOL.md',cell['target'],cell['cap'],cell['path'],None,reg['build_manifest'])
 if 'state' not in row:row['valid']=False;G.write(folder/'result.json',row);raise RuntimeError('Missing durable export; raw retained '+str(temporary))
 assert G.sha(temporary)==row['state']['sha256'];temporary.unlink()
 row.update(stage=stage,cell=cid)
 log=(folder/'stdout.log').read_text()
 row['local_events']=[]
 for line in log.splitlines():
  if line.startswith(('E2_CAP ','E3_GATE ')):
   values=dict(re.findall(r'(\w+)=(\S+)',line));row['local_events'].append(dict(kind=line.split()[0],**values))
 row['max_touched_fraction']=max((int(x['touched'])/int(x['ncam']) for x in row['local_events']),default=0)
 row['stop_reason']='target' if row['hit'] else ('outer_cap' if row['outers']>=600 else ('ftol' if row['stop_ftol'] else 'other'))
 if arm!='original':
  tr=json.loads((folder/'attempts.json').read_text());wv=json.loads((folder/'wave.json').read_text());tot=tr['totals']
  assert len(wv)==len(tr['rows']) and sum(x['accepted'] for x in wv)==row['accepts']
  assert tot['matvecs']==row['matvecs']
  row['attempts']=tot;row['pcg_per_outer']=tot['pcg_iterations']/max(1,row['outers'])
  row['retry_fraction_native']=tot['retry_entry_seconds']/row['native_seconds']
  row['max_raw_radius_ratio']=max((x['raw_radius_ratio'] for x in wv if x['raw_radius_ratio'] is not None),default=None)
 G.write(folder/'result.json',row);return row

def main():
 ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['register','compatibility','locality','tails','opening','practical']);a=ap.parse_args();reg=register();rows=[]
 if a.stage=='register':return
 def add(cell,arm,rep,stage=None):
  row=run(reg,stage or a.stage,cell,arm,rep);rows.append(row);G.write(P/(a.stage+'-results.json'),rows);return row
 if a.stage=='compatibility':
  for rep in range(3):
   for arm in (['original','off'] if rep%2==0 else ['off','original']):add(reg['cells']['dubrovnik-88'],arm,rep)
  med={a:statistics.median(r['cost'] for r in rows if r['arm']==a) for a in ['original','off']}
  assert abs(med['off']/med['original']-1)<.0015,med
 elif a.stage=='locality':
  assert len(json.loads((P/'compatibility-results.json').read_text()))==6
  cell=next(c for c in reg['practical'] if c['scene']=='ladybug-539' and c['cell'].endswith('1.01'))
  for rep in range(3):
   for arm in (['off','cap30','intrinsic'] if rep%2==0 else ['intrinsic','cap30','off']):add(cell,arm,rep)
  decision={arm:dict(max_touched=max(r['max_touched_fraction'] for r in rows if r['arm']==arm),
     survives=all(r['max_touched_fraction']<=.05 for r in rows if r['arm']==arm)) for arm in ['cap30','intrinsic']}
  G.write(P/'locality-decision.json',decision);print('LOCALITY DECISION',decision,flush=True)
 elif a.stage=='tails':
  decision=json.loads((P/'locality-decision.json').read_text());arms=['off','opening']+[a for a,d in decision.items() if d['survives']]
  for rep in range(5):
   for scene in ['venice-52','final-3068']:
    for arm in (arms if rep%2==0 else list(reversed(arms))):add(reg['cells'][scene],arm,rep)
 elif a.stage=='opening':
  assert (P/'compatibility-results.json').exists()
  arms=['off']+[a for a in ARMS if a.startswith('open-')]
  for rep in range(5):
   for arm in (arms if rep%2==0 else list(reversed(arms))):add(reg['cells']['venice-52'],arm,rep)
 elif a.stage=='practical':
  old=json.loads((P/'opening-results.json').read_text());arms=['off']+[a for a in ARMS if a.startswith('open-') and sum(r['hit'] for r in old if r['arm']==a)>=4]
  tail=json.loads((P/'tails-results.json').read_text())
  arms+=[a for a in ['cap30','intrinsic'] if sum(r['hit'] for r in tail if r['arm']==a and r['scene']=='venice-52')>=3]
  G.write(P/'practical-selection.json',dict(arms=arms,rule='registered Venice thresholds'))
  for rep in range(3):
   for cell in reg['practical']:
    for arm in (arms if rep%2==0 else list(reversed(arms))):add(cell,arm,rep)
 print('COMPLETE',a.stage,len(rows),flush=True)
if __name__=='__main__':main()
