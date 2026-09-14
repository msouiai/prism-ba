#!/usr/bin/env python3
from pathlib import Path
import csv,hashlib,json,os,re,subprocess,tempfile,time,sys
P=Path(__file__).resolve().parent;R=P.parent.parent;W5=Path('/tmp/prism-ba-coarse/research/eta2_wave5');F=R/'research/eta2_champion'
PROFILE=P/'build/native-timing';BASE=W5/'build/prism-b6v7'
sys.path.insert(0,str(F/'bench'));from audit_prism_state import observations,audit
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
champ=json.loads((F/'champion.json').read_text());overlay=json.loads((W5/'optimized_candidate.json').read_text())['flags_overlay']
problems=[Path('/workspace/bal/muell-gba146.txt'),Path('/workspace/bal/final-13682.txt')]
def one(problem,arm,rep):
 out=P/'evidence'/'native-timing-v2'/problem.stem/arm/f'rep-{rep}';out.mkdir(parents=True,exist_ok=True)
 state=out/'state.bin';curve=out/'curve.csv';binary=PROFILE if arm=='profile' else BASE
 env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};env.update(champ['flags']);env.update(overlay)
 if arm=='profile':
  env['OCA_NATIVE_PHASE_PROFILE']='1'
  env['OCA_SETUP_PHASE_PROFILE']='1'
 cli=list(champ['cli']);cli[cli.index('--max_iter')+1]='3';cmd=[str(binary),'--problem',str(problem),*cli,'--csv',str(curve),'--state_out',str(state)]
 t=time.monotonic();q=subprocess.run(cmd,env=env,text=True,capture_output=True,timeout=600);wall=time.monotonic()-t
 (out/'stdout.log').write_text(q.stdout);(out/'stderr.log').write_text(q.stderr)
 if q.returncode:raise RuntimeError(q.stderr[-3000:])
 m=re.search(r'RESULT .*?iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)',q.stdout);counts=re.search(r'MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+).*?negcurv=(\d+)',q.stdout);phase=re.search(r'^NATIVE_PHASE .*$',q.stdout,re.M);assert m and counts and (arm!='profile' or phase)
 obs=observations(problem);aud=float(audit(state,*obs));native=float(m[2]);rel=abs(aud-native)/max(1.,abs(aud));assert rel<1e-6
 calls=int(re.search(r'calls=(\d+)',phase.group(0))[1]) if phase else None
 setup=re.findall(r'^SETUP_PHASE .*$',q.stdout,re.M)
 row={'problem':str(problem),'input_sha256':sha(problem),'arm':arm,'rep':rep,'command':cmd,'effective_flags':{**champ['flags'],**overlay,**({'OCA_NATIVE_PHASE_PROFILE':'1','OCA_SETUP_PHASE_PROFILE':'1'} if arm=='profile' else {})},'binary_sha256':sha(binary),'wall_seconds':wall,'solve_seconds':float(m[3]),'iterations':int(m[1]),'final_cost':native,'audit_cost':aud,'audit_relative_error':rel,'state_sha256':sha(state),'accepts':int(counts[1]),'rejects':int(counts[2]),'products':int(counts[3]),'negcurv':int(counts[4]),'native_phase_calls':calls,'phase_line':phase.group(0) if phase else None,'setup_phase_lines':setup,'retry_factor_time_complete':int(counts[2])==0}
 (out/'result.json').write_text(json.dumps(row,indent=2)+'\n');return row
def main():
 rows=[]
 for p in problems:
  rows.append(one(p,'profile',0))
  for rep in range(3):rows.append(one(p,'control',rep))
 result={'protocol':'attributed profile plus N=3 uninstrumented controls; fixed three outers','build_manifest_sha256':sha(P/'NATIVE_TIMING_BUILD.json'),'rows':rows}
 (P/'NATIVE_TIMING_RESULTS_V2.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
