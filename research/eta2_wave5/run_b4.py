#!/usr/bin/env python3
"""Registered B4 dense-Schur dispatch measurements."""
from pathlib import Path
import argparse,json,math,re,statistics,subprocess
import native_light as N

P=Path(__file__).resolve().parent;BINARY=P/"build"/"prism-b4";PARENT=Path(N.CHAMPION["binary"])
PROTOCOL=P/"B4_PROTOCOL.md";ARMS={"off":{},"direct1536":{"OCA_W5_DIRECT_MAX":"1536"}}

def register():
  subprocess.run(["python3",str(N.FROZEN/"build.py"),"--check-only"],check=True)
  build=json.loads((P/"b4-build-manifest.json").read_text());assert N.sha(BINARY)==build["binary_sha256"]
  assert all(N.sha(path)==digest for path,digest in build["sources"].items())
  old=json.loads((P/"b1-registration.json").read_text())
  reg={"arms":ARMS,"audit":old["audit"],"practical":old["practical"],"tails":old["tails"],
    "panel_repetitions":3,"tail_repetitions":5,"threshold_camera_dimension":1536,
    "binary":str(BINARY),"binary_sha256":N.sha(BINARY),"parent_binary":str(PARENT),
    "parent_binary_sha256":N.sha(PARENT),"build_manifest":build,"protocol_sha256":N.sha(PROTOCOL),
    "cohort_rule":"Fresh paired rows; alternating arms and reversed cells on odd repetitions",
    "registered_arm":"FP64 explicit equilibrated Schur plus cuSOLVER when 9*ncam <= 1536"}
  path=P/"b4v5-registration.json"
  if path.exists():assert json.loads(path.read_text())==reg
  else:N.write(path,reg)
  return reg

def enrich(row):
  log=(P/row["source"]/"stdout.log").read_text()
  active=re.search(r"W5_DIRECT active n_c=(\d+) threshold=(\d+) dense_mib=(\S+)",log)
  summary=re.search(r"W5_DIRECT summary solves=(\d+) fallbacks=(\d+) form_seconds=(\S+) factor_solve_seconds=(\S+)",log)
  audit=re.search(r"W5_DIRECT_AUDIT relative_l2=(\S+) absolute_l2=(\S+) reference_l2=(\S+)",log)
  row["direct_active"]=bool(active)
  if active:row["direct_dimensions"]={"n_c":int(active[1]),"threshold":int(active[2]),"dense_mib":float(active[3])}
  if summary:row["direct_summary"]={"solves":int(summary[1]),"fallbacks":int(summary[2]),"form_seconds":float(summary[3]),"factor_solve_seconds":float(summary[4])}
  if audit:row["operator_audit"]={"relative_l2":float(audit[1]),"absolute_l2":float(audit[2]),"reference_l2":float(audit[3])}
  N.write(P/row["source"]/"result.json",row);return row

def execute(reg,stage,cells,arms,reps,extra=None):
  rows=[];extra=extra or {}
  for rep in range(reps):
    cs=list(cells);aa=list(arms)
    if rep%2:cs.reverse();aa.reverse()
    for cell in cs:
      for arm in aa:
        binary=PARENT if arm=="parent-off" else BINARY
        flags={} if arm=="parent-off" else dict(ARMS[arm],**extra)
        folder=P/"evidence"/stage/f"{cell.get('cell',cell['scene'])}-{arm}-{rep}"
        rows.append(enrich(N.run(folder,cell,arm,rep,binary,flags,PROTOCOL,reg["build_manifest"])))
        N.write(P/f"{stage}-results.json",rows)
  return rows

def summarize(rows,arms=("off","direct1536")):
  cells=[]
  for cid in sorted({r["cell"] for r in rows}):
    rec={"cell":cid}
    for arm in arms:
      g=[r for r in rows if r["cell"]==cid and r["arm"]==arm]
      times=[r["target_seconds"] for r in g if r["target_seconds"] is not None]
      rec[arm]={"n":len(g),"hits":sum(r["hit"] for r in g),
        "median_target_seconds":statistics.median(times) if times else None,
        "target_range":[min(times),max(times)] if times else None,
        "median_native_seconds":statistics.median(r["native_seconds"] for r in g),
        "native_range":[min(r["native_seconds"] for r in g),max(r["native_seconds"] for r in g)],
        "median_products":statistics.median(r["matvecs"] for r in g),
        "median_endpoint":statistics.median(r["cost"] for r in g),
        "endpoint_range":[min(r["cost"] for r in g),max(r["cost"] for r in g)],
        "median_outers":statistics.median(r["outers"] for r in g),
        "median_rejects":statistics.median(r["rejects"] for r in g),
        "direct_active":sum(r.get("direct_active",False) for r in g)}
      ds=[r["direct_summary"] for r in g if "direct_summary" in r]
      if ds:rec[arm]["median_direct"]={k:statistics.median(x[k] for x in ds) for k in ds[0]}
    a,b=rec[arms[0]],rec[arms[1]]
    if a["median_target_seconds"] and b["median_target_seconds"]:rec["time_ratio"]=b["median_target_seconds"]/a["median_target_seconds"]
    rec["endpoint_delta"]=b["median_endpoint"]/a["median_endpoint"]-1
    cells.append(rec)
  ratios=[x["time_ratio"] for x in cells if "time_ratio" in x]
  return {"rows":len(rows),"geometric_mean_time_ratio":math.exp(sum(map(math.log,ratios))/len(ratios)) if ratios else None,"cells":cells}

def main():
  ap=argparse.ArgumentParser();ap.add_argument("stage",choices=["compatibility","audit","panel","profile","tails"]);a=ap.parse_args();reg=register()
  calm=next(x for x in reg["practical"] if x["cell"]=="ladybug-539-1.01")
  if a.stage=="compatibility":
    rows=execute(reg,"b4v5-compatibility",[calm],["off","parent-off"],3)
    med={x:statistics.median(r["cost"] for r in rows if r["arm"]==x) for x in ("off","parent-off")}
    result={"rows":len(rows),"medians":med,"relative_delta":med["off"]/med["parent-off"]-1};result["passed"]=abs(result["relative_delta"])<.0015
    N.write(P/"b4v5-compatibility-summary.json",result);assert result["passed"],result
  elif a.stage=="audit":
    assert json.loads((P/"b4v5-compatibility-summary.json").read_text())["passed"]
    rows=execute(reg,"b4v5-audit",[reg["audit"]],["direct1536"],1,{"OCA_W5_DIRECT_AUDIT":"1"})
    audit=rows[0].get("operator_audit",{});result={"row":rows[0],"passed":audit.get("relative_l2",1)>=0 and audit.get("relative_l2",1)<1e-5}
    N.write(P/"b4v5-audit-summary.json",result);assert result["passed"],result
  elif a.stage=="panel":result=summarize(execute(reg,"b4-panel",reg["practical"],list(ARMS),3));N.write(P/"b4-panel-summary.json",result)
  elif a.stage=="profile":
    traf=next(x for x in reg["practical"] if x["cell"]=="trafalgar-138-1.005")
    result=summarize(execute(reg,"b4-profile",[traf,reg["tails"]["venice-52"]],list(ARMS),3,{"OCA_PROFILE":"1"}));N.write(P/"b4-profile-summary.json",result)
  else:result=summarize(execute(reg,"b4-tails",list(reg["tails"].values()),list(ARMS),5));N.write(P/"b4-tails-summary.json",result)
  print(json.dumps(result,indent=2),flush=True)
if __name__=="__main__":main()
