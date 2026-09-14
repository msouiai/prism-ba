#!/usr/bin/env python3
from pathlib import Path
import csv,hashlib,json,os,re,subprocess,tempfile
P=Path(__file__).resolve().parent;R=P.parent.parent;problem=Path("/workspace/bal/ladybug-49.txt")
champ=json.loads((R/"research/eta2_champion/champion.json").read_text());env={k:v for k,v in os.environ.items() if not k.startswith(("OCA_","CASPAR_","COLMAP_MFREE","MF_DEBUG"))};env.update(champ["flags"])
cli=list(champ["cli"]);cli[cli.index("--max_iter")+1]="40"
def run(binary,label):
  state=Path(tempfile.mktemp(dir="/dev/shm"));curve=P/"build"/(label+".csv");cmd=[str(binary),"--problem",str(problem),*cli,"--csv",str(curve),"--state_out",str(state)]
  p=subprocess.run(cmd,env=env,text=True,capture_output=True,timeout=300);assert p.returncode==0,p.stderr[-1000:]
  costs=[r["cost"] for r in csv.DictReader(x for x in curve.read_text().splitlines() if not x.startswith("#"))]
  decisions=[x for x in p.stdout.splitlines() if x.startswith(("PCG_PREP ","ATTR_RADIUS ","CLASSICAL_LM ","POINT_SAFE o=","NUMERIC_REPAIR "))]
  out={"binary_sha256":hashlib.sha256(binary.read_bytes()).hexdigest(),"costs":costs,"decisions":decisions,"state_sha256":hashlib.sha256(state.read_bytes()).hexdigest()};state.unlink();return out
a=run(R/"research/eta2_champion/build/prism-eta2","frozen");b=run(P/"build/prism-linear-edges","derived-off")
result={"frozen":a,"derived_off":b,"exact_costs":a["costs"]==b["costs"],"exact_decisions":a["decisions"]==b["decisions"],"exact_endpoint":a["state_sha256"]==b["state_sha256"]};result["passed"]=all(result[k] for k in ("exact_costs","exact_decisions","exact_endpoint"))
(P/"FLAG_OFF_RESULTS.json").write_text(json.dumps(result,indent=2)+"\n");print(json.dumps({k:v for k,v in result.items() if k not in ("frozen","derived_off")},indent=2));raise SystemExit(0 if result["passed"] else 2)
