#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,os,re,subprocess,tempfile,time,sys
P=Path(__file__).resolve().parent;R=P.parent.parent;A=Path('/tmp/prism-ba-agent-integration')
binary=A/'research/eta2_wave5/build/prism-b6v7';champ=json.loads((R/'research/eta2_champion/champion.json').read_text());overlay=json.loads((A/'research/eta2_wave5/optimized_candidate.json').read_text())['flags_overlay']
sys.path.insert(0,str(R/'research/eta2_champion/bench'));from audit_prism_state import observations,audit
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows=[]
for scene in ('muell-gba146','final-13682'):
 problem=Path('/workspace/bal')/(scene+'.txt');obs=observations(problem)
 for rep in range(4):
  profile=rep==0;state=Path(tempfile.mktemp(prefix=scene+'-',suffix='.state',dir='/dev/shm'));curve=P/(f'PROFILE_{scene}_{rep}.csv');log=P/(f'PROFILE_{scene}_{rep}.log')
  env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};effective=dict(champ['flags']);effective.update(overlay)
  if profile:effective['OCA_PROFILE']='1'
  env.update(effective);cli=list(champ['cli']);cli[cli.index('--max_iter')+1]='3';cmd=[str(binary),'--problem',str(problem),*cli,'--csv',str(curve),'--state_out',str(state)]
  t=time.monotonic();q=subprocess.run(cmd,env=env,text=True,capture_output=True,timeout=600);wall=time.monotonic()-t;log.write_text(q.stdout+'\nSTDERR\n'+q.stderr);assert q.returncode==0,q.stderr[-1000:]
  m=re.search(r'RESULT .*?final_cost=(\S+) solve_seconds=(\S+)',q.stdout);phase=re.search(r'\[PROFILE\] assembly=(\S+)s pointfactor\+rhs=(\S+)s krylov=(\S+)s candidates=(\S+)s',q.stdout)
  audited=float(audit(state,*obs));row={'scene':scene,'rep':rep,'profile':profile,'input_sha256':sha(problem),'binary_sha256':sha(binary),'command':cmd,'effective_flags':effective,'process_wall_s':wall,'native_solve_s':float(m[2]),'native_cost':float(m[1]),'audit_cost':audited,'audit_rel':abs(audited-float(m[1]))/max(1,audited),'endpoint_sha256':sha(state)}
  if phase:row['phase_s']={'assembly':float(phase[1]),'pointfactor_rhs':float(phase[2]),'krylov':float(phase[3]),'candidates':float(phase[4])}
  rows.append(row);state.unlink();print(scene,rep,wall,flush=True)
(P/'PROFILE_RESULTS.json').write_text(json.dumps(rows,indent=2)+'\n')
