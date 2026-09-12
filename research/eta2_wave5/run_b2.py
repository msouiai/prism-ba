#!/usr/bin/env python3
"""Registered B2 FP32-inner/FP64-residual iterative-refinement measurements."""
from pathlib import Path
import argparse, json, re, statistics, subprocess

import native_light as N
import run_b1 as B

P=Path(__file__).resolve().parent
BINARY=P/"build"/"prism-b2"
PARENT=Path(N.CHAMPION["binary"])
PROTOCOL=P/"B2_PROTOCOL.md"
ARMS={"off":{},"ir":{"OCA_W5_IR":"1"}}


def register():
    subprocess.run(["python3",str(N.FROZEN/"build.py"),"--check-only"],check=True)
    build=json.loads((P/"b2-build-manifest.json").read_text());assert N.sha(BINARY)==build["binary_sha256"]
    assert all(N.sha(path)==digest for path,digest in build["sources"].items())
    old=json.loads((P/"b1-registration.json").read_text())
    reg={"arms":ARMS,"audit":old["audit"],"practical":old["practical"],"tails":old["tails"],"muell":old["muell"],
      "panel_repetitions":3,"tail_repetitions":5,"binary":str(BINARY),"binary_sha256":N.sha(BINARY),
      "parent_binary":str(PARENT),"parent_binary_sha256":N.sha(PARENT),"build_manifest":build,
      "protocol_sha256":N.sha(PROTOCOL),"cohort_rule":"Fresh paired rows; alternating arms and reversed cells on odd repetitions",
      "registered_arm":"At most two consistent-FP32 correction PCGs; frozen FP64 operator residual gate and fallback"}
    path=P/"b2-registration.json"
    if path.exists():assert json.loads(path.read_text())==reg
    else:N.write(path,reg)
    return reg


def enrich(row):
    log=(P/row["source"]/"stdout.log").read_text()
    active=re.search(r"\[w5-ir\] active low_jacobian_values=(\d+) low_arithmetic=(\S+) residual=(\S+) max_sweeps=(\d+)",log)
    attempts=[]
    for m in re.finditer(r"W5_IR_ATTEMPT outer=(\d+) retry=(\d+) sweeps=(\d+) low_iters=(\d+) high_rel=(\S+) eta=(\S+) fallback=(\d+)",log):
      attempts.append({"outer":int(m[1]),"retry":int(m[2]),"sweeps":int(m[3]),"low_iters":int(m[4]),
                       "high_relative_residual":float(m[5]),"eta":float(m[6]),"fallback":bool(int(m[7]))})
    summary=re.search(r"W5_IR_SUMMARY attempts=(\d+) sweeps=(\d+) fallbacks=(\d+) nonmonotone=(\d+) low_iters=(\d+)",log)
    profile=re.search(r"\[PROFILE\] assembly=(\S+)s pointfactor\+rhs=(\S+)s krylov=(\S+)s candidates=(\S+)s",log)
    row["ir_active"]=bool(active);row["ir_attempt_records"]=attempts
    if active:row["ir_configuration"]={"jacobian_values":int(active[1]),"low_arithmetic":active[2],"residual":active[3],"max_sweeps":int(active[4])}
    if summary:row["ir_summary"]={"attempts":int(summary[1]),"sweeps":int(summary[2]),"fallbacks":int(summary[3]),
                                  "nonmonotone":int(summary[4]),"low_iters":int(summary[5])}
    if profile:row["profile_seconds"]={"assembly":float(profile[1]),"pointfactor_rhs":float(profile[2]),
                                       "krylov":float(profile[3]),"candidates":float(profile[4])}
    N.write(P/row["source"]/"result.json",row);return row


def execute(reg,stage,cells,arms,reps,extra=None):
    rows=[];extra=extra or {}
    for rep in range(reps):
      oc,oa=list(cells),list(arms)
      if rep%2:oc.reverse();oa.reverse()
      for cell in oc:
        for arm in oa:
          binary=PARENT if arm=="parent-off" else BINARY;flags={} if arm=="parent-off" else dict(ARMS[arm],**extra)
          folder=P/"evidence"/stage/f"{cell.get('cell',cell['scene'])}-{arm}-{rep}"
          rows.append(enrich(N.run(folder,cell,arm,rep,binary,flags,PROTOCOL,reg["build_manifest"])))
          N.write(P/f"{stage}-results.json",rows)
    return rows


def main():
    ap=argparse.ArgumentParser();ap.add_argument("stage",choices=["compatibility","audit","panel","profile","muell","tails"]);args=ap.parse_args();reg=register()
    calm=next(c for c in reg["practical"] if c["cell"]=="ladybug-539-1.01")
    if args.stage=="compatibility":
      rows=execute(reg,"b2-compatibility",[calm],["off","parent-off"],3);med={a:statistics.median(r["cost"] for r in rows if r["arm"]==a) for a in ("off","parent-off")}
      result={"rows":len(rows),"medians":med,"relative_delta":med["off"]/med["parent-off"]-1};result["passed"]=abs(result["relative_delta"])<1e-10
      N.write(P/"b2-compatibility-summary.json",result);assert result["passed"],result
    elif args.stage=="audit":
      rows=execute(reg,"b2-audit",[reg["audit"]],["ir"],1);row=rows[0];s=row.get("ir_summary",{});ats=row.get("ir_attempt_records",[])
      # A linear-only check once let an integration bug pass: the refined
      # vector met the residual gate but bypassed candidate scoring entirely.
      # Require the calm audit scene to take a real descent step as well.
      result={"row":row};result["passed"]=bool(s) and row["accepts"]>0 and row["cost"]<row["score_init"] and s["nonmonotone"]==0 and s["fallbacks"]==0 and all(a["sweeps"]<=2 for a in ats) and all(a["high_relative_residual"]<=1.011*a["eta"] for a in ats)
      N.write(P/"b2-audit-summary.json",result);assert result["passed"],result
    elif args.stage=="panel":
      result=B.summarize(execute(reg,"b2-panel",reg["practical"],list(ARMS),3),("off","ir"));N.write(P/"b2-panel-summary.json",result)
    elif args.stage=="profile":
      traf=next(c for c in reg["practical"] if c["cell"]=="trafalgar-138-1.005")
      rows=execute(reg,"b2-profile",[traf,reg["muell"]],list(ARMS),3,{"OCA_PROFILE":"1"});result=B.summarize(rows,("off","ir"))
      for cell in result["cells"]:
        for arm in ARMS:
          group=[r for r in rows if r["cell"]==cell["cell"] and r["arm"]==arm]
          cell[arm]["median_profile_seconds"]={p:statistics.median(r["profile_seconds"][p] for r in group) for p in ("assembly","pointfactor_rhs","krylov","candidates")}
      N.write(P/"b2-profile-summary.json",result)
    elif args.stage=="muell":
      result=B.summarize(execute(reg,"b2-muell",[reg["muell"]],list(ARMS),3),("off","ir"));N.write(P/"b2-muell-summary.json",result)
    else:
      result=B.summarize(execute(reg,"b2-tails",list(reg["tails"].values()),list(ARMS),5),("off","ir"));N.write(P/"b2-tails-summary.json",result)
    print(json.dumps(result,indent=2),flush=True)
if __name__=="__main__":main()
