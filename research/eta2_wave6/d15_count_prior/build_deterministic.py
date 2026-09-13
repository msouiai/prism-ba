#!/usr/bin/env python3
"""Build D15 on the exact deterministic/common-random-number instrument."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
WAVE6 = HERE.parent
FROZEN = WAVE6.parent / "eta2_champion"
OUT = pathlib.Path("/tmp/prism-wave6-d15-deterministic")
OUT.mkdir(parents=True, exist_ok=True)


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


spec = importlib.util.spec_from_file_location("build_deterministic", WAVE6 / "build_deterministic.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
source, inherited_count = module.derive()
assert hashlib.sha256(source.encode()).hexdigest() == json.loads(
    (WAVE6 / "deterministic-build-manifest.json").read_text()
)["source_sha256"]

s = source
patches = []


def patch(old, new, count=1):
    global s
    assert s.count(old) == count, (old[:120], s.count(old), count)
    s = s.replace(old, new)
    patches.append((old, new, count))


patch('#include "pcg_camera.cuh"', '#include "d15_pcg_camera.cuh"\n#include "d15_count_prior.cuh"')
patch(
    "  std::unique_ptr<PrismPcg> pcg;\n"
    "  if(getenv(\"OCA_PCG\"))pcg=std::make_unique<PrismPcg>(ncam);",
    "  std::unique_ptr<PrismPcg> pcg;\n"
    "  if(getenv(\"OCA_PCG\"))pcg=std::make_unique<PrismPcg>(ncam);\n"
    "  std::unique_ptr<D15CountPrior> d15;\n"
    "  if(getenv(\"OCA_D15_COUNT_PRIOR\"))d15=std::make_unique<D15CountPrior>(ncam,p.mf_coff,p.mf_cspt);",
)
patch(
    "  for(int k=replay_start;k<max_iter;){\n   const double numeric_prior_bnorm=prev_bnorm;",
    "  for(int k=replay_start;k<max_iter;){\n"
    "   if(d15){d15->Reset();if(pcg)pcg->SetPrior(nullptr);}\n"
    "   const double numeric_prior_bnorm=prev_bnorm;",
)
anchor = "    auto KvS=[&](const Scalar* vin,Scalar* vout){"
start = s.index(anchor)
end = s.index("\n    };", start) + len("\n    };")
body = s[start:end]
renamed = body.replace("auto KvS=", "auto D15KvSBase=", 1)
patch(body, renamed + "\n    auto KvS=[&](const Scalar* vin,Scalar* vout){D15KvSBase(vin,vout);if(d15)d15->Add(vin,vout);};")
patch(
    "      pcg->Prepare(Hcc,E,shifts[0],k,retries,Gp,fragment_points,p.mf_coff,Rf,nobs);pcg->Apply(r_);",
    "      if(d15)pcg->SetPrior(d15->active?d15->delta:nullptr);\n"
    "      pcg->Prepare(Hcc,E,shifts[0],k,retries,Gp,fragment_points,p.mf_coff,Rf,nobs);pcg->Apply(r_);",
)
patch(
    "      if(attr_radius){\n        PrismW6Dnrm2(blas,n_c,xs[0],1,&attr_raw_norm);",
    "      if(attr_radius){\n"
    "        PrismW6Dnrm2(blas,n_c,xs[0],1,&attr_raw_norm);\n"
    "        if(d15 && !d15->active && attr_R>0){\n"
    "          auto q=d15->Inspect(xs[0],attr_R);\n"
    "          std::printf(\"D15_TEST o=%d retry=%d ratio=%.17g gated_fraction=%.17g raw=%.17g radius=%.17g trigger=%d\\n\",k,retries,q.ratio,q.gated_fraction,q.norm,attr_R,(int)(q.ratio>100&&q.gated_fraction>.5));\n"
    "          if(q.ratio>100 && q.gated_fraction>.5){\n"
    "            if(mf_fp32)d15->Build<float>(Gc32,p.mf_cspt,p.mf_coff,Rf,Hcc,E,nobs);\n"
    "            else d15->Build<Fragment>(Gc?Gc:Gp,p.mf_cspt,p.mf_coff,Rf,Hcc,E,nobs,fragment_slots);\n"
    "            pcg->SetPrior(d15->delta);std::fill(preds.begin(),preds.end(),(Scalar)0.0);goto sweep_restart;\n"
    "          }\n"
    "        }",
)
patch("  if(final_lambda_out) *final_lambda_out = lam_cam;",
      "  if(d15)d15->Final();\n  if(final_lambda_out) *final_lambda_out = lam_cam;")

restored = s
for old, new, count in reversed(patches):
    assert restored.count(new) == count
    restored = restored.replace(new, old)
assert restored == source

src = OUT / "prism_d15_deterministic.cu"
binary = OUT / "prism-d15-deterministic"
src.write_text(s)
command = [
    "nvcc", "-O3", "-DNDEBUG", "-std=c++17", "-arch=sm_89", "-I/usr/include/eigen3",
    f"-I{HERE}", f"-I{WAVE6}", f"-I{FROZEN / 'source/headers'}",
    f"-I{WAVE6.parent / 'eta2_wave5'}", str(src), "-o", str(binary), "-lcublas", "-lcusolver",
]
with (OUT / "build.log").open("w") as log:
    subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True,
                   env={**os.environ, "TMPDIR": "/dev/shm"})
record = {
    "command": command,
    "deterministic_parent_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
    "derived_source_sha256": sha(src), "binary_sha256": sha(binary),
    "inherited_reversible_patch_count": inherited_count,
    "d15_reversible_patch_count": len(patches),
    "sources": {str(p): sha(p) for p in [
        HERE / "build_deterministic.py", HERE / "d15_count_prior.cuh", HERE / "d15_pcg_camera.cuh",
        WAVE6 / "build_deterministic.py",
    ]},
}
(HERE / "deterministic-build-manifest.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2))
