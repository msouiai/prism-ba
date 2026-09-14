#!/usr/bin/env python3
"""Exercise the integrated zero-reduced-RHS control flow on CUDA."""
from pathlib import Path
import json,sys
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P));from run_lightweight import one
row=one(P/"build/prism-math",Path("/workspace/bal/ladybug-49.txt"),"zero-rhs-fixture",0,
        {"OCA_AUDIT_LINEAR_EDGES":"1","OCA_AUDIT_ZERO_RHS_FIXTURE":"1"})
log=(P/"evidence/zero-rhs-fixture/rep-0/stdout.log").read_text()
fires=log.count("[linear-edge] exact zero reduced RHS: converged at depth 0")
result={"row":row,"zero_depth_diagnostic_count":fires,"negcurv_zero":row["negcurv"]==0,
        "zero_schur_products":row["matvecs"]==0,"point_updates_accepted":row["accepts"]>0,
        "cost_decreased":row["audit_cost"] < 850912.46064130263 - 1.0}
result["passed"]=fires>0 and row["negcurv"]==0 and row["matvecs"]==0 and row["accepts"]>0 and result["cost_decreased"]
(P/"ZERO_RHS_GPU_RESULTS.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps({"passed":result["passed"],"fires":fires,"negcurv":row["negcurv"]},indent=2))
if not result["passed"]:raise SystemExit(2)
