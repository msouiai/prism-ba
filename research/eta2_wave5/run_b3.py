#!/usr/bin/env python3
"""Registered Schur-Jacobi scheduler measurements."""
from pathlib import Path
import argparse,json,math,re,statistics,subprocess
import native_light as N

P=Path(__file__).resolve().parent; BINARY=P/"build"/"prism-b3";PARENT=Path(N.CHAMPION["binary"])
ARMS={"off":{},"schur_lam1e3":{"OCA_W5_PCG_SCHUR_LAM":"1e-3"}}

def register():
    subprocess.run(["python3",str(N.FROZEN/"build.py"),"--check-only"],check=True)
    build=json.loads((P/"b3-build-manifest.json").read_text());assert N.sha(BINARY)==build["binary_sha256"]
    assert all(N.sha(path)==digest for path,digest in build["sources"].items())
    old=json.loads((P.parent/"eta2_wave4"/"aside-registration.json").read_text())
    muell={"scene":"muell-gba146","path":"/workspace/bal/muell-gba146.txt",
      "input_sha256":N.sha("/workspace/bal/muell-gba146.txt"),"target":1946488.746262194,"cap":12}
    reg={"arms":ARMS,"practical":old["practical"],"tails":{k:old["cells"][k] for k in ("venice-52","final-3068")},
      "muell":muell,"panel_repetitions":3,"tail_repetitions":5,"binary":str(BINARY),
      "binary_sha256":N.sha(BINARY),"parent_binary":str(PARENT),"parent_binary_sha256":N.sha(PARENT),
      "build_manifest":build,"protocol_sha256":N.sha(P/"B3_PROTOCOL.md"),
      "cohort_rule":"Fresh paired rows; alternating arms and reversed cells on odd repetitions"}
    path=P/"b3-registration.json"
    if path.exists():assert json.loads(path.read_text())==reg
    else:N.write(path,reg)
    return reg

def enrich(row):
    log=(P/row["source"]/"stdout.log").read_text();m=re.search(r"W5_PCG_SCHUR switch outer=(\d+)",log)
    row["preconditioner_switch_outer"]=int(m[1]) if m else None
    N.write(P/row["source"]/"result.json",row);return row

def execute(reg,stage,cells,arms,reps):
    rows=[]
    for rep in range(reps):
      cs=list(cells);aa=list(arms)
      if rep%2:cs.reverse();aa.reverse()
      for cell in cs:
       for arm in aa:
        binary=PARENT if arm=="parent-off" else BINARY;flags={} if arm=="parent-off" else ARMS[arm]
        folder=P/"evidence"/stage/f"{cell.get('cell',cell['scene'])}-{arm}-{rep}"
        rows.append(enrich(N.run(folder,cell,arm,rep,binary,flags,P/"B3_PROTOCOL.md",reg["build_manifest"])))
        N.write(P/f"{stage}-results.json",rows)
    return rows

def summary(rows):
    cells=[]
    for cid in sorted({r["cell"] for r in rows}):
      rec={"cell":cid}
      for arm in ARMS:
       g=[r for r in rows if r["cell"]==cid and r["arm"]==arm];times=[r["target_seconds"] for r in g if r["target_seconds"] is not None]
       rec[arm]={"n":len(g),"hits":sum(r["hit"] for r in g),"median_target_seconds":statistics.median(times) if times else None,
        "target_range":[min(times),max(times)] if times else None,
        "median_native_seconds":statistics.median(r["native_seconds"] for r in g),
        "native_range":[min(r["native_seconds"] for r in g),max(r["native_seconds"] for r in g)],
        "median_products":statistics.median(r["matvecs"] for r in g),"product_range":[min(r["matvecs"] for r in g),max(r["matvecs"] for r in g)],
        "median_endpoint":statistics.median(r["cost"] for r in g),"median_outers":statistics.median(r["outers"] for r in g),
        "median_rejects":statistics.median(r["rejects"] for r in g),
        "switch_outers":[r["preconditioner_switch_outer"] for r in g]}
      if rec["off"]["median_target_seconds"] and rec["schur_lam1e3"]["median_target_seconds"]:
       rec["time_ratio"]=rec["schur_lam1e3"]["median_target_seconds"]/rec["off"]["median_target_seconds"]
       rec["product_ratio"]=rec["schur_lam1e3"]["median_products"]/rec["off"]["median_products"]
      cells.append(rec)
    usable=[c["time_ratio"] for c in cells if "time_ratio" in c]
    return {"rows":len(rows),"geometric_mean_time_ratio":math.exp(sum(map(math.log,usable))/len(usable)) if usable else None,"cells":cells}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("stage",choices=["compatibility","smoke","panel","muell","tails"]);a=ap.parse_args();reg=register()
    calm=next(x for x in reg["practical"] if x["cell"]=="ladybug-539-1.01")
    if a.stage=="compatibility":
      rows=execute(reg,"b3v2-compatibility",[calm],["off","parent-off"],3);med={x:statistics.median(r["cost"] for r in rows if r["arm"]==x) for x in ("off","parent-off")}
      result={"rows":len(rows),"medians":med,"relative_delta":med["off"]/med["parent-off"]-1};result["passed"]=abs(result["relative_delta"])<.0015
      N.write(P/"b3-compatibility-summary.json",result);assert result["passed"],result
    elif a.stage=="smoke":
      assert json.loads((P/"b3-compatibility-summary.json").read_text())["passed"]
      rows=execute(reg,"b3v2-smoke",[calm],["schur_lam1e3"],1)
      result={"passed":rows[0]["preconditioner_switch_outer"] is not None,"row":rows[0]};assert result["passed"]
    elif a.stage=="panel":result=summary(execute(reg,"b3v2-panel",reg["practical"],list(ARMS),3));N.write(P/"b3-panel-summary.json",result)
    elif a.stage=="muell":result=summary(execute(reg,"b3v2-muell",[reg["muell"]],list(ARMS),3));N.write(P/"b3-muell-summary.json",result)
    else:result=summary(execute(reg,"b3v2-tails",list(reg["tails"].values()),list(ARMS),5));N.write(P/"b3-tails-summary.json",result)
    print(json.dumps(result,indent=2),flush=True)

if __name__=="__main__":main()
