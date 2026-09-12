#!/usr/bin/env python3
"""Build the D10 track-damage diagnostic/filter on deterministic Eta2."""
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

    patch('#include "point_safeguard.cuh"',
          '#include "point_safeguard.cuh"\n#include "track_damage_filter.cuh"')
    patch(
        "  Scalar cost=ComputeCost(p,s,rk,rk_a2);",
        r'''  Scalar cost=ComputeCost(p,s,rk,rk_a2);
  const int w6_damage_mode=[](){const char* e=getenv("OCA_W6_TRACK_DAMAGE");return e?atoi(e):0;}();
  if(w6_damage_mode<0||w6_damage_mode>2||
     (w6_damage_mode&&(!w6_deterministic||!classical_lm||!attr_radius||L!=1||rk!=0)))
    throw std::runtime_error("W6 track damage requires deterministic single-shift plain-L2 Eta2; 1=log, 2=opening filter");
  std::unique_ptr<W6TrackDamage> w6_damage;
  if(w6_damage_mode)w6_damage=std::make_unique<W6TrackDamage>(npt);
  long w6_damage_evals=0,w6_damage_concentrated=0,w6_damage_rejects=0;
  double w6_damage_seconds=0.;''')

    anchor = '''      lm_prediction=model.prediction;lm_rho=have&&lm_prediction>0?(cost-best_cost)/lm_prediction:-1;
      have=have&&std::isfinite(lm_rho)&&lm_prediction>0&&lm_rho>(attr_strict?.1:0);'''
    replacement = r'''      lm_prediction=model.prediction;lm_rho=have&&lm_prediction>0?(cost-best_cost)/lm_prediction:-1;
      const bool w6_damage_decreasing=have&&std::isfinite((double)best_cost)&&best_cost<cost&&
        std::isfinite(lm_rho)&&lm_prediction>0;
      have=w6_damage_decreasing&&lm_rho>(attr_strict?.1:0);
      if(w6_damage_mode&&w6_damage_decreasing){
        const auto damage_start=now();
        DoRetract(d_best,s_new);
        const auto damage=w6_damage->Evaluate(p,s,s_new,(double)(cost-best_cost));
        w6_damage_seconds+=std::chrono::duration<double>(now()-damage_start).count();
        ++w6_damage_evals;
        const bool concentrated=damage.concentration>.05&&damage.burden>.05;
        if(concentrated)++w6_damage_concentrated;
        const bool filtered=w6_damage_mode==2&&n_accept<10&&have&&concentrated;
        if(filtered){have=false;++w6_damage_rejects;}
        std::printf("W6_TRACK_DAMAGE o=%d accepts=%d rho=%.17g gain=%.17g max=%.17g positive=%.17g q=%.17g burden=%.17g point=%d old=%.17g new=%.17g increased=%d concentrated=%d filtered=%d\n",
          k,n_accept,lm_rho,(double)(cost-best_cost),damage.max_increase,damage.positive_sum,
          damage.concentration,damage.burden,damage.max_point,damage.old_track,damage.new_track,
          damage.increased_tracks,(int)concentrated,(int)filtered);
      }'''
    patch(anchor, replacement)
    patch(
        "  int cheir1=CountCheiralityViolations(p,s);",
        r'''  if(w6_damage_mode)std::printf("W6_TRACK_DAMAGE summary evals=%ld concentrated=%ld filtered=%ld seconds=%.17g\n",
    w6_damage_evals,w6_damage_concentrated,w6_damage_rejects,w6_damage_seconds);
  int cheir1=CountCheiralityViolations(p,s);''')

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
    src = build / "track_damage.cu"
    binary = build / "prism-track-damage"
    source, count = derive()
    src.write_text(source)
    cmd = ["nvcc", "-O3", "-DNDEBUG", "-std=c++17", "-arch=sm_89",
           "-I/usr/include/eigen3", "-I" + str(P),
           "-I" + str(F / "source" / "headers"),
           "-I" + str(P.parent / "eta2_wave5"), str(src), "-o", str(binary),
           "-lcublas", "-lcusolver"]
    log_path = build / "track-damage-build.log"
    with log_path.open("w") as log:
        subprocess.run(cmd, env=dict(os.environ, TMPDIR="/dev/shm"),
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    manifest = {
        "command": cmd,
        "source_sha256": sha(src),
        "binary_sha256": sha(binary),
        "champion_sha256": sha(F / "champion.json"),
        "reversible_patch_count": count,
        "sources": {str(path): sha(path) for path in [
            P / "build_track_damage.py", P / "track_damage_filter.cuh",
            P / "build_deterministic.py"]},
        "protocol_sha256": sha(P / "D10_TRACK_DAMAGE_FILTER_PROTOCOL.md"),
    }
    (P / "d10-build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("BUILT", binary, manifest["binary_sha256"], flush=True)


if __name__ == "__main__":
    main()
