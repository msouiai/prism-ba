#!/usr/bin/env python3
"""Build the preregistered adaptive-exit O5 arm as a reversible overlay."""
from pathlib import Path
import hashlib, importlib.util, json, os, subprocess

P = Path(__file__).resolve().parent
W4 = P.parent / "eta2_wave4"
F = P.parent / "eta2_champion"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def derive():
    spec = importlib.util.spec_from_file_location("wave4_o5", W4 / "build_o5.py")
    parent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parent)
    parent.headers()
    original, old_count = parent.derive()
    source = original
    changes = []

    def patch(before, after, count=1):
        nonlocal source
        assert source.count(before) == count, (before[:120], source.count(before), count)
        source = source.replace(before, after)
        changes.append((before, after, count))

    robust = str(W4 / "o5_headers" / "robust_stage.cuh")
    patch(f'#include "{robust}"',
          f'#include "{robust}"\n#include "{P / "adaptive_robust_exit.cuh"}"')
    patch("  bool w5_force_l2=false;", r'''  bool w5_force_l2=false;
  const bool w5_adaptive=getenv("OCA_W5_ADAPTIVE_EXIT")&&atoi(getenv("OCA_W5_ADAPTIVE_EXIT"));
  constexpr double w5_exit_fraction=1e-3;
  if(w5_adaptive&&!w5_on)throw std::runtime_error("adaptive robust exit requires OCA_W5_CAUCHY");
  std::unique_ptr<W5AdaptiveExit> w5_exit;
  if(w5_adaptive)w5_exit=std::make_unique<W5AdaptiveExit>();
  long w5_exit_checks=0;''')
    patch('    std::printf("W5_INIT base=%.17g l2=%.17g\\n",w5_base,w5_l2);', r'''    std::printf("W5_INIT base=%.17g l2=%.17g\n",w5_base,w5_l2);
    if(w5_adaptive){unsigned long long down=0;double frac=w5_exit->Fraction(p,s,rk_a2,down);++w5_exit_checks;
      w5_force_l2=frac<w5_exit_fraction;
      std::printf("W5_EXIT_CHECK where=initial stage=%d down=%llu nobs=%d fraction=%.17g exit=%d\n",
        w5_stage,down,nobs,frac,(int)w5_force_l2); }''')
    old = r'''       rk=w5_stage<4?2:0;rk_a2=w5_base*std::pow(4.,std::min(w5_stage,3));W5SetRobust(rk,rk_a2);
       cost=ComputeCost(p,s,rk,rk_a2);w5_l2=rk?ComputeCost(p,s,0,0):cost;'''
    new = r'''       rk=w5_stage<4?2:0;rk_a2=w5_base*std::pow(4.,std::min(w5_stage,3));W5SetRobust(rk,rk_a2);
       if(w5_adaptive&&rk){unsigned long long down=0;double frac=w5_exit->Fraction(p,s,rk_a2,down);++w5_exit_checks;
         const bool exit=frac<w5_exit_fraction;
         std::printf("W5_EXIT_CHECK where=transition stage=%d down=%llu nobs=%d fraction=%.17g exit=%d\n",
           w5_stage,down,nobs,frac,(int)exit);
         if(exit){w5_stage=4;rk=0;W5SetRobust(0,0);} }
       cost=ComputeCost(p,s,rk,rk_a2);w5_l2=rk?ComputeCost(p,s,0,0):cost;'''
    patch(old, new)
    old = r'''    w5_l2=(w5_on&&rk)?ComputeCost(p,s,0,0):(double)cost;
    log.iters.push_back(k+1); log.costs.push_back(w5_l2);'''
    new = r'''    w5_l2=(w5_on&&rk)?ComputeCost(p,s,0,0):(double)cost;
    if(w5_adaptive&&rk){unsigned long long down=0;double frac=w5_exit->Fraction(p,s,rk_a2,down);++w5_exit_checks;
      const bool exit=frac<w5_exit_fraction;w5_force_l2=w5_force_l2||exit;
      std::printf("W5_EXIT_CHECK where=accepted stage=%d down=%llu nobs=%d fraction=%.17g exit=%d\n",
        w5_stage,down,nobs,frac,(int)exit); }
    log.iters.push_back(k+1); log.costs.push_back(w5_l2);'''
    patch(old, new)
    patch('    std::printf("W5_FINAL stage=%d l2=%.17g incomplete=%d\\n",w5_stage,w5_l2,(int)(w5_stage<4));',
          '    std::printf("W5_FINAL stage=%d l2=%.17g incomplete=%d exit_checks=%ld\\n",w5_stage,w5_l2,(int)(w5_stage<4),w5_exit_checks);')

    restored = source
    for before, after, count in reversed(changes):
        assert restored.count(after) == count
        restored = restored.replace(after, before)
    assert restored == original
    return source, old_count + len(changes)


def main():
    subprocess.run(["python3", str(F / "build.py"), "--check-only"], check=True)
    wave4_manifest = json.loads((W4 / "o5_build_manifest.json").read_text())
    assert sha(W4 / "build" / "prism-o5") == wave4_manifest["binary_sha256"]
    source, count = derive()
    build = P / "build"
    build.mkdir(exist_ok=True)
    src = build / "a2.cu"
    binary = build / "prism-a2"
    src.write_text(source)
    command = wave4_manifest["command"].copy()
    command[command.index(str(W4 / "build" / "o5.cu"))] = str(src)
    command[command.index("-o") + 1] = str(binary)
    with (build / "a2-build.log").open("w") as log:
        subprocess.run(command, env=dict(os.environ, TMPDIR="/dev/shm"),
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    manifest = {
        "command": command, "source_sha256": sha(src), "binary_sha256": sha(binary),
        "frozen_source_sha256": sha(F / "source" / "prism_eta2.cu"),
        "champion_sha256": sha(F / "champion.json"),
        "parent_o5_binary_sha256": wave4_manifest["binary_sha256"],
        "reversible_patch_count": count,
        "sources": {
            **wave4_manifest["sources"], str(W4 / "build_o5.py"): sha(W4 / "build_o5.py"),
            str(P / "build_a2.py"): sha(P / "build_a2.py"),
            str(P / "adaptive_robust_exit.cuh"): sha(P / "adaptive_robust_exit.cuh"),
        },
        "protocol_sha256": sha(P / "A2_A4_PROTOCOL.md"),
    }
    (P / "a2-build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("BUILT A2", manifest["binary_sha256"], flush=True)


if __name__ == "__main__":
    main()
