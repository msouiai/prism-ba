#!/usr/bin/env python3
"""Build a reversible monotone soft-rho overlay on deterministic Eta2."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

P = Path(__file__).resolve().parent
F = P.parent / "eta2_champion"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parent_module():
    spec = importlib.util.spec_from_file_location("w6_deterministic", P / "build_deterministic.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derive():
    source, inherited = parent_module().derive()
    original = source
    changes = []

    def patch(before, after):
        nonlocal source
        assert source.count(before) == 1, (before[:160], source.count(before))
        source = source.replace(before, after)
        changes.append((before, after))

    patch(
        "  Scalar cost=ComputeCost(p,s,rk,rk_a2);",
        r'''  Scalar cost=ComputeCost(p,s,rk,rk_a2);
  const double w6_soft_rho=[](){const char* e=getenv("OCA_W6_SOFT_RHO");return e?atof(e):0.;}();
  long w6_soft_trials=0,w6_soft_commits=0;
  double w6_soft_alpha_sum=0.;
  if(w6_soft_rho<0. || w6_soft_rho>.1 ||
     (w6_soft_rho>0. && (!w6_deterministic||!classical_lm||!attr_radius||L!=1||rk!=0)))
    throw std::runtime_error("W6 soft acceptance requires deterministic single-shift plain-L2 Eta2 and rho<=0.1");''',
    )
    anchor = '''      lm_prediction=model.prediction;lm_rho=have&&lm_prediction>0?(cost-best_cost)/lm_prediction:-1;
      have=have&&std::isfinite(lm_rho)&&lm_prediction>0&&lm_rho>(attr_strict?.1:0);'''
    replacement = r'''      lm_prediction=model.prediction;lm_rho=have&&lm_prediction>0?(cost-best_cost)/lm_prediction:-1;
      bool w6_soft_applied=false;
      if(w6_soft_rho>0. && have && std::isfinite(lm_rho) && lm_prediction>0. &&
         lm_rho>0. && lm_rho<=w6_soft_rho){
        const double old_rho=lm_rho,old_candidate=best_cost;
        const double alpha=old_rho/w6_soft_rho;
        CUBLAS_CHECK(cublasDscal(blas,n,&alpha,d_best,1));
        DoRetract(d_best,s_new);
        best_cost=ComputeCost(p,s_new,rk,rk_a2);
        auto soft_model=full_model->Evaluate(p,s,d_best,k2mask);++full_model_calls;
        lm_prediction=soft_model.prediction;
        lm_rho=lm_prediction>0.?(cost-best_cost)/lm_prediction:-1.;
        have=std::isfinite((double)best_cost)&&best_cost<cost&&
             std::isfinite(lm_rho)&&lm_prediction>0.;
        w6_soft_applied=true;++w6_soft_trials;w6_soft_alpha_sum+=alpha;
        if(have)++w6_soft_commits;
        std::printf("W6_SOFT_RHO o=%d alpha=%.17g old_rho=%.17g scaled_rho=%.17g current=%.17g old_candidate=%.17g scaled_candidate=%.17g prediction=%.17g commit=%d\n",
          k,alpha,old_rho,lm_rho,(double)cost,old_candidate,(double)best_cost,lm_prediction,(int)have);
      }
      if(!w6_soft_applied)
        have=have&&std::isfinite(lm_rho)&&lm_prediction>0&&lm_rho>(attr_strict?.1:0);'''
    patch(anchor, replacement)
    patch(
        "  int cheir1=CountCheiralityViolations(p,s);",
        r'''  if(w6_soft_rho>0.)std::printf("W6_SOFT_RHO summary trials=%ld commits=%ld mean_alpha=%.17g\n",
    w6_soft_trials,w6_soft_commits,w6_soft_trials?w6_soft_alpha_sum/w6_soft_trials:0.);
  int cheir1=CountCheiralityViolations(p,s);''',
    )

    restored = source
    for before, after in reversed(changes):
        assert restored.count(after) == 1
        restored = restored.replace(after, before)
    assert restored == original
    return source, inherited + len(changes)


def main():
    subprocess.run(["python3", str(F / "build.py"), "--check-only"], check=True)
    build = P / "build"
    build.mkdir(exist_ok=True)
    src = build / "soft_accept.cu"
    binary = build / "prism-soft-accept"
    source, count = derive()
    src.write_text(source)
    cmd = ["nvcc", "-O3", "-DNDEBUG", "-std=c++17", "-arch=sm_89",
           "-I/usr/include/eigen3", "-I" + str(P),
           "-I" + str(F / "source" / "headers"),
           "-I" + str(P.parent / "eta2_wave5"), str(src), "-o", str(binary),
           "-lcublas", "-lcusolver"]
    with (build / "soft-accept-build.log").open("w") as log:
        subprocess.run(cmd, env=dict(os.environ, TMPDIR="/dev/shm"),
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    manifest = {
        "command": cmd,
        "source_sha256": sha(src),
        "binary_sha256": sha(binary),
        "champion_sha256": sha(F / "champion.json"),
        "reversible_patch_count": count,
        "sources": {
            str(P / "build_soft_accept.py"): sha(P / "build_soft_accept.py"),
            str(P / "build_deterministic.py"): sha(P / "build_deterministic.py"),
        },
        "protocol_sha256": sha(P / "D4_PROTOCOL.md"),
    }
    (P / "d4-build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("BUILT", binary, manifest["binary_sha256"], flush=True)


if __name__ == "__main__":
    main()
