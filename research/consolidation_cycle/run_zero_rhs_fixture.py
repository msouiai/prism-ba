#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,math,os,re,subprocess,tempfile,sys
P=Path(__file__).resolve().parent;R=P.parent.parent
champ=json.loads((R/"research/eta2_champion/champion.json").read_text())
binary=P/"build/prism-linear-edges-fixture";problem=Path("/workspace/bal/ladybug-49.txt")
state=Path(tempfile.mktemp(prefix="linear-edge-",suffix=".state",dir="/dev/shm"));curve=P/"build/zero-rhs.csv"
env={k:v for k,v in os.environ.items() if not k.startswith(("OCA_","CASPAR_","COLMAP_MFREE","MF_DEBUG"))};effective=dict(champ["flags"]);effective.update({"OCA_AUDIT_LINEAR_EDGES":"1","OCA_AUDIT_ZERO_RHS_FIXTURE":"1"});env.update(effective)
cli=list(champ["cli"]);cli[cli.index("--max_iter")+1]="40"
cmd=[str(binary),"--problem",str(problem),*cli,"--csv",str(curve),"--state_out",str(state)]
p=subprocess.run(cmd,env=env,text=True,capture_output=True,timeout=300);(P/"build/zero-rhs.stdout").write_text(p.stdout);(P/"build/zero-rhs.stderr").write_text(p.stderr)
if p.returncode:raise SystemExit(p.returncode)
m=re.search(r"MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+).*?negcurv=(\d+)",p.stdout);r=re.search(r"RESULT .*?final_cost=(\S+)",p.stdout);assert m and r
fires=p.stdout.count("[linear-edge] exact zero reduced RHS: converged at depth 0")
sys.path.insert(0,str(R/"research/eta2_champion/bench"));from audit_prism_state import observations,audit
audit_cost=float(audit(state,*observations(problem)))
result={"binary_sha256":hashlib.sha256(binary.read_bytes()).hexdigest(),"input_sha256":hashlib.sha256(problem.read_bytes()).hexdigest(),"endpoint_sha256":hashlib.sha256(state.read_bytes()).hexdigest(),"command":cmd,"effective_flags":effective,"fires":fires,"accepts":int(m[1]),"rejects":int(m[2]),"matvecs":int(m[3]),"negcurv":int(m[4]),"native_final_cost":float(r[1]),"audit_final_cost":audit_cost,"audit_relative_error":abs(audit_cost-float(r[1]))/max(1.0,audit_cost),"initial_cost":850912.46064130263}
result["passed"]=fires>0 and result["accepts"]>0 and result["matvecs"]==0 and result["negcurv"]==0 and math.isfinite(audit_cost) and audit_cost<result["initial_cost"]-1.0
(P/"ZERO_RHS_FIXTURE_RESULTS.json").write_text(json.dumps(result,indent=2)+"\n");state.unlink(missing_ok=True);print(json.dumps(result,indent=2))
if not result["passed"]:raise SystemExit(2)
