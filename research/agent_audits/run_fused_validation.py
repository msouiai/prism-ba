#!/usr/bin/env python3
"""Dynamic operator-equivalence smoke for the fused point-owned product."""
from pathlib import Path
import json,statistics,sys
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P));from run_lightweight import one
B=P/"build/prism-fused";problem=Path("/workspace/bal/ladybug-49.txt")
base={"OCA_W6_DETERMINISTIC":"1"};rows=[]
for rep in range(3):
  arms=["off","on"] if rep%2==0 else ["on","off"]
  for arm in arms:
    flags=dict(base)
    if arm=="on":flags["OCA_AUDIT_FUSED_PASS1"]="1"
    rows.append(one(B,problem,f"fused-{arm}",rep,flags))
fields=("accepted_cost_hash","decision_hash","state_sha256","iterations","final_cost","accepts","rejects","matvecs","negcurv")
pairs=[]
for rep in range(3):
  a=next(r for r in rows if r["rep"]==rep and r["label"]=="fused-off")
  b=next(r for r in rows if r["rep"]==rep and r["label"]=="fused-on")
  pairs.append({"rep":rep,"exact":{k:a[k]==b[k] for k in fields},"solve_ratio":b["solve_seconds"]/a["solve_seconds"]})
result={"rows":rows,"pairs":pairs,"all_exact":all(all(p["exact"].values()) for p in pairs),
 "solve_ratio_median":statistics.median(p["solve_ratio"] for p in pairs),
 "fixed_capture_product_timing_measured":False}
result["promotion_gate_passed"]=False
(P/"FUSED_PASS1_RESULTS.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps({k:v for k,v in result.items() if k!="rows"},indent=2))
if not result["all_exact"]:raise SystemExit(2)
