#!/usr/bin/env python3
from pathlib import Path
import csv,hashlib,json,os,re,subprocess,tempfile,sys
P=Path(__file__).resolve().parent;R=P.parent.parent;A=Path("/tmp/prism-ba-agent-integration");problem=Path("/workspace/bal/ladybug-49.txt")
champ=json.loads((R/"research/eta2_champion/champion.json").read_text());overlay=json.loads((A/"research/eta2_wave5/optimized_candidate.json").read_text())["flags_overlay"]
sys.path.insert(0,str(R/"research/eta2_champion/bench"));from audit_prism_state import observations,audit
baseenv={k:v for k,v in os.environ.items() if not k.startswith(("OCA_","CASPAR_","COLMAP_MFREE","MF_DEBUG"))};baseenv.update(champ["flags"]);baseenv.update(overlay);baseenv["OCA_W6_DETERMINISTIC"]="1"
cli=list(champ["cli"]);cli[cli.index("--max_iter")+1]="40";obs=observations(problem)
def run(binary,label,edge):
  env=dict(baseenv)
  if edge:env["OCA_AUDIT_LINEAR_EDGES"]="1"
  state=Path(tempfile.mktemp(dir="/dev/shm"));curve=P/"build"/(label+".csv");cmd=[str(binary),"--problem",str(problem),*cli,"--csv",str(curve),"--state_out",str(state)]
  p=subprocess.run(cmd,env=env,text=True,capture_output=True,timeout=300);assert p.returncode==0,p.stderr[-1000:]
  costs=[r["cost"] for r in csv.DictReader(x for x in curve.read_text().splitlines() if not x.startswith("#"))];dec=[x for x in p.stdout.splitlines() if x.startswith(("PCG_PREP ","ATTR_RADIUS ","CLASSICAL_LM ","POINT_SAFE o=","NUMERIC_REPAIR "))]
  m=re.search(r"MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+).*?negcurv=(\d+)",p.stdout);rr=re.search(r"RESULT .*?iters=(\d+) final_cost=(\S+)",p.stdout);assert m and rr
  ac=float(audit(state,*obs));row={"costs":costs,"decisions":dec,"endpoint_sha256":hashlib.sha256(state.read_bytes()).hexdigest(),"iters":int(rr[1]),"final_cost":float(rr[2]),"audit_cost":ac,"accepts":int(m[1]),"rejects":int(m[2]),"matvecs":int(m[3]),"negcurv":int(m[4])};state.unlink();return row
rows={"baseline":run(P/"build/fixed-baseline","baseline",False),"current_off":run(P/"build/fixed-linear-edges","current-off",False),"current_on":run(P/"build/fixed-linear-edges","current-on",True)}
if (P/"build/prism-owned-workspace").exists(): rows["owned_workspace"]=run(P/"build/prism-owned-workspace","owned-workspace",False)
fields=("costs","decisions","endpoint_sha256","iters","final_cost","accepts","rejects","matvecs","negcurv")
result={"rows":rows,"off_exact":all(rows["baseline"][x]==rows["current_off"][x] for x in fields),"ordinary_on_exact":all(rows["baseline"][x]==rows["current_on"][x] for x in fields),"fields":list(fields)}
result["workspace_exact"]= "owned_workspace" not in rows or all(rows["current_off"][x]==rows["owned_workspace"][x] for x in fields);result["passed"]=result["off_exact"] and result["ordinary_on_exact"] and result["workspace_exact"]
(P/"FIXED_PARITY_RESULTS.json").write_text(json.dumps(result,indent=2)+"\n");print(json.dumps({k:v for k,v in result.items() if k!="rows"},indent=2));raise SystemExit(0 if result["passed"] else 2)
