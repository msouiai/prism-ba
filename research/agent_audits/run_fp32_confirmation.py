#!/usr/bin/env python3
"""Run preregistered paired FP32/FP64 compact-fragment confirmation."""
from pathlib import Path
import hashlib, json, statistics, sys

P=Path(__file__).resolve().parent;R=P.parent.parent;W6=R/"research/eta2_wave6";W5=R/"research/eta2_wave5"
sys.path[:0]=[str(W6),str(W5)]
from bal_perturb import load_bal,perturb,residual_distance,sha256,state_from_bal,write_state
import native_light as native
native.HERE=P

PROTOCOL=P/"FP32_CONFIRMATION_PROTOCOL.md"
FP32=P/"build/prism-code"
FP64=W6/"build/prism-deterministic-fp64-fragments"
OPT=json.loads((W5/"optimized_candidate.json").read_text())
SCENES=[
 {"scene":"ladybug-49","path":"/workspace/bal/ladybug-49.txt","target":13591.568354279514,"cap":5.0},
 {"scene":"final-3068","path":"/workspace/bal/final-3068.txt","target":1744796.9841897595,"cap":45.0},
 {"scene":"final-4585","path":"/workspace/bal/final-4585.txt","target":7075838.613048037,"cap":60.0},]

def canon(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def write(path,x):Path(path).write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+"\n")

def registration():
  x={"protocol_sha256":sha256(PROTOCOL),"epsilon":1e-10,"pairs_per_scene":3,
    "arm_order":"fp32 first on even repetition, fp64 first on odd repetition","rig_excluded":True,
    "scenes":[dict(s,input_sha256=sha256(s["path"]),seed_base=910000+100*i) for i,s in enumerate(SCENES)],
    "arms":{"fp32":{"binary":str(FP32),"sha256":sha256(FP32)},"fp64":{"binary":str(FP64),"sha256":sha256(FP64)}},
    "flags":dict(OPT["flags_overlay"],OCA_W6_DETERMINISTIC="1")}
  path=P/"fp32-confirmation-registration.json"
  if path.exists():
    assert json.loads(path.read_text())==x,"frozen registration differs"
  else: write(path,x)
  return x

def execute(reg):
  rows=[]
  for si,base in enumerate(SCENES):
    original=load_bal(base["path"])
    for rep in range(3):
      seed=910000+100*si+rep;cameras,points,scales=perturb(original,seed,1e-10)
      paired=Path("/dev/shm")/f"agent-fp32-{si}-{rep}.txt";write_state(original,paired,cameras,points)
      cell=dict(base,path=str(paired),cell=f'{base["scene"]}-pair-{rep}',input_sha256=sha256(paired))
      meta={"seed":seed,"paired_input_sha256":cell["input_sha256"],"field_scales":scales,
        "initial_residual_distance":residual_distance(original,state_from_bal(original),state_from_bal(original,cameras,points))}
      arms=["fp32","fp64"] if rep%2==0 else ["fp64","fp32"]
      try:
        for arm in arms:
          binary=FP32 if arm=="fp32" else FP64
          folder=P/"evidence/fp32-confirmation"/f'{base["scene"]}-{rep}-{arm}'
          row=native.run(folder,cell,arm,rep,binary,reg["flags"],PROTOCOL,reg)
          row.update(meta);rows.append(row);write(P/"FP32_CONFIRMATION_RESULTS.json",rows)
      finally: paired.unlink(missing_ok=True)
  return rows

def summarize(rows):
  out={}
  for scene in [s["scene"] for s in SCENES]:
    g=[r for r in rows if r["scene"]==scene];arms={a:[r for r in g if r["arm"]==a] for a in ("fp32","fp64")}
    pairs=[]
    for rep in range(3):
      a=next(r for r in arms["fp32"] if r["rep"]==rep);b=next(r for r in arms["fp64"] if r["rep"]==rep)
      pairs.append({"rep":rep,"fp32_hit":a["hit"],"fp64_hit":b["hit"],"fp32_target_s":a["target_seconds"],"fp64_target_s":b["target_seconds"],
        "ratio":b["target_seconds"]/a["target_seconds"] if a["hit"] and b["hit"] else None})
    ratios=[p["ratio"] for p in pairs if p["ratio"] is not None]
    out[scene]={"pairs":pairs,"hits":{a:sum(r["hit"] for r in arms[a]) for a in arms},
      "target_range":{a:[min([r["target_seconds"] for r in arms[a] if r["hit"]],default=None),max([r["target_seconds"] for r in arms[a] if r["hit"]],default=None)] for a in arms},
      "fp64_over_fp32_median":statistics.median(ratios) if ratios else None,
      "max_audit_relative_error":max(r["audit_relative_error"] for r in g)}
  evaluable=all(v["fp64_over_fp32_median"] is not None for v in out.values())
  passed=evaluable and all(v["hits"]["fp32"]>=v["hits"]["fp64"]-1 and v["fp64_over_fp32_median"]>=1/1.02 for v in out.values())
  value={"scenes":out,"timing_evaluable":evaluable,"passed":passed};write(P/"FP32_CONFIRMATION_SUMMARY.json",value);return value

def main():
  reg=registration();rows=execute(reg);print(json.dumps(summarize(rows),indent=2))
if __name__=="__main__":main()
