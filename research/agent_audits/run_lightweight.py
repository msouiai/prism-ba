#!/usr/bin/env python3
"""Run the preregistered small repeatability and flag-compatibility gates."""
from pathlib import Path
import csv, hashlib, json, os, re, subprocess, sys, tempfile, time

P=Path(__file__).resolve().parent
R=P.parent.parent
F=R/"research/eta2_champion"
W5=R/"research/eta2_wave5"
CHAMP=json.loads((F/"champion.json").read_text())
OVER=json.loads((W5/"optimized_candidate.json").read_text())["flags_overlay"]
sys.path.insert(0,str(F/"bench"))
from audit_prism_state import observations, audit
OBS={}

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(x): return hashlib.sha256(json.dumps(x,separators=(",",":"),sort_keys=True).encode()).hexdigest()

def one(binary,problem,label,rep,flags):
    outdir=P/"evidence"/label/f"rep-{rep}"
    outdir.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix="agent-audit-",suffix=".state",dir="/dev/shm")
    os.close(fd);state=Path(name)
    curve=outdir/"curve.csv"
    env={k:v for k,v in os.environ.items() if not k.startswith(("OCA_","CASPAR_","COLMAP_MFREE","MF_DEBUG"))}
    env.update(CHAMP["flags"]);env.update(OVER);env.update(flags)
    cli=CHAMP["cli"].copy();cli[cli.index("--max_iter")+1]="40"
    cmd=[str(binary),"--problem",str(problem),*cli,"--csv",str(curve),"--state_out",str(state)]
    t=time.monotonic();p=subprocess.run(cmd,env=env,text=True,capture_output=True,timeout=180)
    (outdir/"stdout.log").write_text(p.stdout);(outdir/"stderr.log").write_text(p.stderr)
    assert p.returncode==0,p.stderr[-2000:]
    costs=[row["cost"] for row in csv.DictReader(x for x in curve.read_text().splitlines() if not x.startswith("#"))]
    decisions=[x for x in p.stdout.splitlines() if x.startswith(("PCG_PREP ","ATTR_RADIUS ","CLASSICAL_LM ","POINT_SAFE o=","NUMERIC_REPAIR "))]
    result=re.search(r"RESULT .*?iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)",p.stdout)
    count=re.search(r"MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+).*?negcurv=(\d+)",p.stdout)
    assert result and count
    key=str(problem)
    if key not in OBS: OBS[key]=observations(problem)
    audit_cost=float(audit(state,*OBS[key]));native_cost=float(result[2])
    audit_rel=abs(audit_cost-native_cost)/max(1.0,audit_cost)
    assert audit_rel < 1e-6,audit_rel
    row={"label":label,"rep":rep,"problem":str(problem),"input_sha256":sha(problem),
      "binary_sha256":sha(binary),"flags":flags,"accepted_cost_hash":canonical(costs),
      "decision_hash":canonical(decisions),"state_sha256":sha(state),"state_bytes":state.stat().st_size,
      "iterations":int(result[1]),"final_cost":native_cost,"audit_cost":audit_cost,
      "audit_relative_error":audit_rel,"solve_seconds":float(result[3]),
      "accepts":int(count[1]),"rejects":int(count[2]),"matvecs":int(count[3]),"negcurv":int(count[4])}
    state.unlink();(outdir/"result.json").write_text(json.dumps(row,indent=2)+"\n");return row

def main():
    problem=Path("/workspace/bal/ladybug-49.txt")
    code=P/"build/prism-code";math=P/"build/prism-math";combined=P/"build/prism-combined"
    rows=[]
    # Record the legacy nondeterministic math-only path in both modes, but use
    # fixed reductions below for the exact flag-compatibility assertion.
    rows += [one(math,problem,"math-off",0,{})]
    rows += [one(math,problem,"math-on",0,{"OCA_AUDIT_LINEAR_EDGES":"1"})]
    # Five independent complete-fixed-reduction executions.
    for rep in range(5): rows.append(one(code,problem,"code-fixed",rep,{"OCA_W6_DETERMINISTIC":"1"}))
    # Fixed-order off/on comparison isolates the math branch from reduction noise.
    rows.append(one(combined,problem,"combined-math-off",0,{"OCA_W6_DETERMINISTIC":"1"}))
    rows.append(one(combined,problem,"combined",0,{"OCA_W6_DETERMINISTIC":"1","OCA_AUDIT_LINEAR_EDGES":"1"}))
    fixed=[r for r in rows if r["label"]=="code-fixed"]
    fields=("accepted_cost_hash","decision_hash","state_sha256","iterations","final_cost","accepts","rejects","matvecs","negcurv")
    unique={f:len({r[f] for r in fixed}) for f in fields}
    compatible=all(rows[-2][f]==rows[-1][f] for f in fields)
    combined_ok=all(rows[-1][f]==fixed[0][f] for f in fields)
    summary={"rows":rows,"fixed_unique_counts":unique,"fixed_repeatable":all(v==1 for v in unique.values()),
      "math_ordinary_flag_compatible":compatible,"combined_matches_code_fixed":combined_ok}
    summary["passed"]=summary["fixed_repeatable"] and compatible and combined_ok
    (P/"LIGHTWEIGHT_RESULTS.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({k:v for k,v in summary.items() if k!="rows"},indent=2))
    if not summary["passed"]: raise SystemExit(2)
if __name__=="__main__":main()
