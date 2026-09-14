#!/usr/bin/env python3
"""Serial exact-compatibility validation for per-solve cost workspace."""
from pathlib import Path
import json,sys
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P));from run_lightweight import one
B=P/"build/prism-workspace";problem=Path("/workspace/bal/ladybug-49.txt")
base={"OCA_W6_DETERMINISTIC":"1","OCA_AUDIT_LINEAR_EDGES":"1"}
off=one(B,problem,"workspace-off",0,base)
on=one(B,problem,"workspace-on",0,dict(base,OCA_AUDIT_WORKSPACE="1"))
fields=("accepted_cost_hash","decision_hash","state_sha256","iterations","final_cost","accepts","rejects","matvecs","negcurv")
result={"off":off,"on":on,"exact_fields":{k:off[k]==on[k] for k in fields}}
result["passed"]=all(result["exact_fields"].values())
(P/"WORKSPACE_RESULTS.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps({"passed":result["passed"],"exact_fields":result["exact_fields"]},indent=2))
if not result["passed"]:raise SystemExit(2)
