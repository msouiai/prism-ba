#!/usr/bin/env python3
"""Final3068 terminal-gradient and stop-window audit, with all repeats retained."""
import pathlib,os,json,subprocess,fcntl,time,re,hashlib,shutil
ROOT=pathlib.Path(__file__).resolve().parent
from paths import OUT as BASE_OUT, reference_eta2
OUT=BASE_OUT/'stall';OUT.mkdir(exist_ok=True,parents=True)
base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}
cfg=json.loads((ROOT.parent/'eta2_champion/champion.json').read_text())
v2flags={'OCA_RHO_LAMBDA':'1','OCA_GRID_DOWN':'2','OCA_RHO_SHIFT':'1','OCA_ALPHA_RHO':'1'}
v2cli=['--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','60','--lam0','10.0','--tau_pt','3e-3','--func-tol','1e-6','--max-consec-fail','3']
champcli=cfg['cli'].copy();champcli[champcli.index('--max_iter')+1]='60'
arms={
 'v2':(ROOT/'build/v2/audit-v2',v2cli,v2flags),
 'window8':(ROOT/'build/v2/audit-v2',v2cli,v2flags|{'OCA_STOP_WINDOW':'8'}),
 'eta2':(ROOT/'build/prism-coarse',champcli,cfg['flags']),
}
protocol={'scene':'final-3068','repeats':10,'arms':{k:{'binary':str(v[0]),'cli':v[1],'flags':v[2]} for k,v in arms.items()},'process_cap_seconds':30,'notes':'Diagnostic batches: gradient instrumentation and fresh terminal assembly are charged. Native timings are not used as an uninstrumented speed claim. Window8 is an existing stopping control, not a new solver. No common target is invented from these endpoints.'}
(OUT/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
for source,name in [(ROOT/'build/v2/manifest.json','v2-manifest.json'),(ROOT/'build/solver-manifest.json','eta2-manifest.json')]:shutil.copy2(source,OUT/name)
def run(stem,cmd,flags,timeout=30):
 print(stem,flush=True);t=time.monotonic();path=OUT/(stem+'.log')
 with path.open('w') as f:
  try:rc=subprocess.run(cmd,env=base|flags,stdout=f,stderr=subprocess.STDOUT,timeout=timeout).returncode
  except subprocess.TimeoutExpired:rc=124
 text=path.read_text();match=re.search(r'RESULT algo=\S+ iters=(\d+) final_cost=([\deE.+-]+) solve_seconds=([\deE.+-]+)',text)
 counts=re.search(r'MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)',text)
 grads=[]
 for line in text.splitlines():
  if line.startswith('GRAD_AUDIT '):
   d=dict(x.split('=',1) for x in line.split()[1:]);grads.append(d)
 row={'name':stem,'command':cmd,'flags':flags,'returncode':rc,'process_seconds':time.monotonic()-t,'gradient_rows':grads,'stop_messages':[l.strip() for l in text.splitlines() if 'converged (' in l or 'stop:' in l]}
 if match:row.update(outers=int(match[1]),cost=float(match[2]),seconds=float(match[3]))
 if counts:row.update(accepts=int(counts[1]),rejects=int(counts[2]),matvecs=int(counts[3]))
 (OUT/(stem+'.json')).write_text(json.dumps(row,indent=2)+'\n')
 print(json.dumps({k:v for k,v in row.items() if k in ['name','returncode','cost','outers','seconds','rejects','stop_messages']}),flush=True)
 return row
with open('/tmp/prism_gpu.lock','w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 rows=[]
 for label,binary in [('original','/workspace/multishift_repro/oca_cuda_v2'),('off',str(arms['v2'][0]))]:
  cli=v2cli.copy();cli[cli.index('--max_iter')+1]='4'
  rows.append(run('parity-'+label,[binary,'--problem','/workspace/bal/ladybug-49.txt',*cli],v2flags))
 assert all(r['returncode']==0 for r in rows)
 assert abs(rows[0]['cost']-rows[1]['cost'])/rows[0]['cost']<1e-7
 for arm in ['v2','eta2']:
  binary,cli,flags=arms[arm];cli=cli.copy();cli[cli.index('--max_iter')+1]='4'
  row=run('memcheck-'+arm,['compute-sanitizer','--tool','memcheck','--error-exitcode','9',str(binary),'--problem','/workspace/bal/ladybug-49.txt',*cli],flags|{'OCA_GRAD_AUDIT':'1'},120)
  assert row['returncode']==0 and any(g['phase']=='terminal' for g in row['gradient_rows'])
 names=list(arms)
 for rep in range(10):
  for arm in names[rep%3:]+names[:rep%3]:
   binary,cli,flags=arms[arm]
   run(f'{arm}-{rep:02}',[str(binary),'--problem','/workspace/bal/final-3068.txt',*cli],flags|{'OCA_GRAD_AUDIT':'1'})
print('DONE stall audit',flush=True)
