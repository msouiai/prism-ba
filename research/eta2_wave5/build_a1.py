#!/usr/bin/env python3
"""Build wave-5 A1 as a reversible overlay on the frozen Eta2 source."""
from pathlib import Path
import hashlib, json, os, subprocess

P = Path(__file__).resolve().parent
F = P.parent / "eta2_champion"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def derive():
    source_path = F / "source" / "prism_eta2.cu"
    source = original = source_path.read_text()
    changes = []

    def patch(before, after, count=1):
        nonlocal source
        assert source.count(before) == count, (before[:120], source.count(before), count)
        source = source.replace(before, after)
        changes.append((before, after, count))

    patch('#include "point_safeguard.cuh"',
          '#include "point_safeguard.cuh"\n#include "' + str(P / 'targeted_triangulation.cuh') + '"')
    patch('  unsigned long long point_safeguard_frozen=0;double point_safeguard_seconds=0;', r'''  unsigned long long point_safeguard_frozen=0;double point_safeguard_seconds=0;
  const bool w5_a1_on=getenv("OCA_W5_TARGET_TRIANGULATION")&&atoi(getenv("OCA_W5_TARGET_TRIANGULATION"));
  std::unique_ptr<Eta2W5TargetedTriangulation> w5_a1;
  if(w5_a1_on)w5_a1=std::make_unique<Eta2W5TargetedTriangulation>(nobs);
  long w5_a1_calls=0;unsigned long long w5_a1_flagged=0,w5_a1_eligible=0,w5_a1_margin=0,w5_a1_algebra=0,w5_a1_wins=0;
  double w5_a1_improvement=0,w5_a1_seconds=0;''')
    patch('  if((point_safeguard_mode || repair_damping_mode) && score_stride_env!=1)throw std::runtime_error("point safeguard requires full observation scoring");', r'''  if((point_safeguard_mode || repair_damping_mode) && score_stride_env!=1)throw std::runtime_error("point safeguard requires full observation scoring");
  if(w5_a1_on && (!classical_lm || !attr_rescue || !backtrack_on || point_safeguard_mode!=1 ||
      L!=1 || CD!=9 || shared_intr || mf_fp32 || rk || score_stride_env!=1 || batch_cost || batch_check))
    throw std::runtime_error("wave5 targeted triangulation requires the frozen L2 single-shift Eta2 champion path");''')
    patch('      _ps(ts_retract,[&]{ DoRetract(dfull,s_new); });\n      _ps(ts_cost,[&]{ c = score_stride>1 ?', r'''      _ps(ts_retract,[&]{ DoRetract(dfull,s_new); });
      if(w5_a1_on){const auto started=now();
        const auto result=w5_a1->Apply(p,s,s_new,dfull,k2mask,2.0*(double)cost/std::max(1,nobs));
        ++w5_a1_calls;w5_a1_flagged+=result.flagged;w5_a1_eligible+=result.eligible;
        w5_a1_margin+=result.margin_rejects;w5_a1_algebra+=result.algebra_failures;w5_a1_wins+=result.wins;
        w5_a1_improvement+=result.improvement;w5_a1_seconds+=std::chrono::duration<double>(now()-started).count();
        if(result.eligible)std::printf("W5_A1 o=%d retry=%d sh=%d ck=%d flagged=%llu eligible=%llu wins=%llu margin=%llu algebra=%llu track_decrease=%.17g\n",
          k,retries,sh,ck,result.flagged,result.eligible,result.wins,result.margin_rejects,result.algebra_failures,result.improvement);
      }
      _ps(ts_cost,[&]{ c = score_stride>1 ?''')
    patch('  if(point_safeguard_mode)std::printf("POINT_SAFE summary calls=%ld evals=%ld wins=%ld frozen=%llu seconds=%.9g\\n",\n    point_safeguard_calls,point_safeguard_evals,point_safeguard_wins,point_safeguard_frozen,point_safeguard_seconds);', r'''  if(point_safeguard_mode)std::printf("POINT_SAFE summary calls=%ld evals=%ld wins=%ld frozen=%llu seconds=%.9g\n",
    point_safeguard_calls,point_safeguard_evals,point_safeguard_wins,point_safeguard_frozen,point_safeguard_seconds);
  if(w5_a1_on)std::printf("W5_A1 summary calls=%ld flagged=%llu eligible=%llu wins=%llu margin=%llu algebra=%llu track_decrease=%.17g seconds=%.9g\n",
    w5_a1_calls,w5_a1_flagged,w5_a1_eligible,w5_a1_wins,w5_a1_margin,w5_a1_algebra,w5_a1_improvement,w5_a1_seconds);''')

    restored = source
    for before, after, count in reversed(changes):
        assert restored.count(after) == count
        restored = restored.replace(after, before)
    assert restored == original
    return source, len(changes)


def main():
    subprocess.run(["python3", str(F / "build.py"), "--check-only"], check=True)
    source, count = derive()
    build = P / "build"; build.mkdir(exist_ok=True)
    src = build / "a1.cu"; binary = build / "prism-a1"; src.write_text(source)
    command = ["nvcc", "-O3", "-DNDEBUG", "-std=c++17", "-arch=sm_89",
               "-I/usr/include/eigen3", "-I" + str(F / "source" / "headers"),
               str(src), "-o", str(binary), "-lcublas", "-lcusolver"]
    with (build / "a1-build.log").open("w") as log:
        subprocess.run(command, env=dict(os.environ, TMPDIR="/dev/shm"),
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    manifest = {
        "command": command, "source_sha256": sha(src), "binary_sha256": sha(binary),
        "frozen_source_sha256": sha(F / "source" / "prism_eta2.cu"),
        "champion_sha256": sha(F / "champion.json"), "reversible_patch_count": count,
        "sources": {str(P / "build_a1.py"): sha(P / "build_a1.py"),
                    str(P / "targeted_triangulation.cuh"): sha(P / "targeted_triangulation.cuh")},
        "protocol_sha256": sha(P / "A1_REPLAY_PROTOCOL.md"),
    }
    (P / "a1-build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("BUILT A1", manifest["binary_sha256"], flush=True)


if __name__ == "__main__":
    main()
