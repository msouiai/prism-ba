#!/usr/bin/env python3
"""Build D23 terminal block Gauss--Seidel audit from deterministic B6v7."""
from __future__ import annotations
import hashlib, importlib.util, json, os, pathlib, subprocess

HERE = pathlib.Path(__file__).resolve().parent
W6 = HERE.parent
FROZEN = W6.parent / "eta2_champion"
OUT = pathlib.Path("/tmp/prism-wave6-d23")
OUT.mkdir(parents=True, exist_ok=True)


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


spec = importlib.util.spec_from_file_location("deterministic", W6 / "build_deterministic.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
source, inherited = module.derive()
assert hashlib.sha256(source.encode()).hexdigest() == json.loads(
    (W6 / "deterministic-build-manifest.json").read_text())["source_sha256"]

s = source
patches = []


def patch(before, after):
    global s
    assert s.count(before) == 1, (before[:160], s.count(before))
    s = s.replace(before, after)
    patches.append((before, after))


patch(
    '''  static const int ri_at = [](){ const char* e=getenv("OCA_RI_AT");
    return e? std::atoi(e) : -1; }();''',
    '''  static const int ri_at = [](){ const char* e=getenv("OCA_RI_AT");
    return e? std::atoi(e) : -1; }();
  static const int d23_terminal_ri = [](){ const char* e=getenv("OCA_D23_TERMINAL_RI");
    return e ? std::atoi(e) : 0; }();
  if(d23_terminal_ri<0 || d23_terminal_ri>32)
    throw std::runtime_error("OCA_D23_TERMINAL_RI must be in [0,32]");
  if(d23_terminal_ri && (ri_open>0 || ri_at>=0))
    throw std::runtime_error("D23 terminal RI cannot be combined with historical RI flags");''')

patch(
    '''    if(converged){ ++k; break; }
    if(verbose)''',
    '''    if(converged){
      if(d23_terminal_ri){
        const Scalar d23_before=cost;const size_t d23_log_before=log.costs.size();
        const auto d23_t0=now();const int d23_done=RunRIPhase(d23_terminal_ri);
        const double d23_seconds=std::chrono::duration<double>(now()-d23_t0).count();
        const bool d23_target=TargetReached(cost,k+1);
        std::printf("D23_TERMINAL outer=%d before=%.17g after=%.17g decrease=%.17g sweeps=%d states=%zu seconds=%.9g target=%d\\n",
          k+1,(double)d23_before,(double)cost,(double)(d23_before-cost),d23_done,
          log.costs.size()-d23_log_before,d23_seconds,(int)d23_target);
      }
      ++k; break;
    }
    if(verbose)''')

restored = s
for before, after in reversed(patches):
    assert restored.count(after) == 1
    restored = restored.replace(after, before)
assert restored == source

src = OUT / "prism_d23.cu"
binary = OUT / "prism-d23"
src.write_text(s)
command = ["nvcc", "-O3", "-DNDEBUG", "-std=c++17", "-arch=sm_89",
           "-I/usr/include/eigen3", f"-I{W6}", f"-I{FROZEN/'source/headers'}",
           f"-I{W6.parent/'eta2_wave5'}", str(src), "-o", str(binary),
           "-lcublas", "-lcusolver"]
with (OUT / "build.log").open("w") as log:
    subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True,
                   env={**os.environ, "TMPDIR": "/dev/shm"})
record = {
    "command": command,
    "parent_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
    "derived_source_sha256": sha(src), "binary_sha256": sha(binary),
    "inherited_patch_count": inherited, "d23_patch_count": len(patches),
    "sources": {str(path): sha(path) for path in [HERE / "build.py", W6 / "build_deterministic.py"]},
    "protocol_sha256": sha(W6 / "D23_TERMINAL_BLOCK_GS_PROTOCOL.md"),
}
(HERE / "build-manifest.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2))
