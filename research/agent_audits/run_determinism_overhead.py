#!/usr/bin/env python3
"""Measure paired complete fixed-reduction overhead."""
from pathlib import Path
import csv, hashlib, json, statistics, sys
P=Path(__file__).resolve().parent;R=P.parent.parent;W5=R/"research/eta2_wave5"
sys.path.insert(0,str(W5));import native_light as native
native.HERE=P
PROTOCOL=P/"DETERMINISM_OVERHEAD_PROTOCOL.md";BINARY=P/"build/prism-code"
OPT=json.loads((W5/"optimized_candidate.json").read_text())
SCENES=[
 {"scene":"final-3068","cell":"final-3068-overhead","path":"/workspace/bal/final-3068.txt","target":1744796.9841897595,"cap":45.0},
 {"scene":"final-4585","cell":"final-4585-overhead","path":"/workspace/bal/final-4585.txt","target":7075838.613048037,"cap":60.0}]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canon(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+"\n")
def registration():
 x={"protocol_sha256":sha(PROTOCOL),"runner_sha256":sha(__file__),"binary":str(BINARY),"binary_sha256":sha(BINARY),
   "repetitions":3,"arm_order":"unordered first on even repetition, fixed first on odd repetition",
   "scenes":[dict(s,input_sha256=sha(s["path"])) for s in SCENES],"base_flags":OPT["flags_overlay"]}
 p=P/"determinism-overhead-registration.json"
 if p.exists():assert json.loads(p.read_text())==x
 else:write(p,x)
 return x
def enrich(row):
 folder=P/row["source"]
 costs=[x["cost"] for x in csv.DictReader(y for y in (folder/"curve.csv").read_text().splitlines() if not y.startswith("#"))]
 lines=[x for x in (folder/"stdout.log").read_text().splitlines() if x.startswith(("PCG_PREP ","ATTR_RADIUS ","CLASSICAL_LM ","POINT_SAFE o=","NUMERIC_REPAIR "))]
 row["accepted_cost_hash"]=canon(costs);row["decision_hash"]=canon(lines);write(folder/"result.json",row);return row
def execute(reg):
 rows=[]
 for cell in SCENES:
  cell=dict(cell,input_sha256=sha(cell["path"]))
  for rep in range(3):
   arms=["unordered","fixed"] if rep%2==0 else ["fixed","unordered"]
   for arm in arms:
    flags=dict(OPT["flags_overlay"])
    if arm=="fixed":flags["OCA_W6_DETERMINISTIC"]="1"
    folder=P/"evidence/determinism-overhead"/f'{cell["scene"]}-{rep}-{arm}'
    rows.append(enrich(native.run(folder,cell,arm,rep,BINARY,flags,PROTOCOL,reg)));write(P/"DETERMINISM_OVERHEAD_RESULTS.json",rows)
 return rows
def summarize(rows):
 out={}
 for scene in [s["scene"] for s in SCENES]:
  g=[r for r in rows if r["scene"]==scene];pairs=[]
  for rep in range(3):
   u=next(r for r in g if r["rep"]==rep and r["arm"]=="unordered");f=next(r for r in g if r["rep"]==rep and r["arm"]=="fixed")
   pairs.append({"rep":rep,"unordered_hit":u["hit"],"fixed_hit":f["hit"],"native_ratio":f["native_seconds"]/u["native_seconds"],
     "target_ratio":f["target_seconds"]/u["target_seconds"] if f["hit"] and u["hit"] else None})
  fixed=[r for r in g if r["arm"]=="fixed"];tr=[p["target_ratio"] for p in pairs if p["target_ratio"] is not None]
  out[scene]={"pairs":pairs,"native_ratio_median":statistics.median(p["native_ratio"] for p in pairs),
    "target_ratio_median":statistics.median(tr) if tr else None,"double_hits":len(tr),
    "fixed_unique_counts":{k:len({r[k] for r in fixed}) for k in ("accepted_cost_hash","decision_hash","state_sha256","cost","matvecs","rejects")},
    "max_audit_relative_error":max(r["audit_relative_error"] for r in g)}
 passed=all(v["double_hits"]>0 and v["target_ratio_median"]<=1.01 for v in out.values())
 value={"scenes":out,"production_speed_gate_passed":passed};write(P/"DETERMINISM_OVERHEAD_SUMMARY.json",value);return value
def main():
 reg=registration();print(json.dumps(summarize(execute(reg)),indent=2))
if __name__=="__main__":main()
