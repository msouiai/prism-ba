#!/usr/bin/env python3
"""Build the wave-6 fixed-reduction measurement binary."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

P = Path(__file__).resolve().parent
W5 = P.parent / "eta2_wave5"
F = P.parent / "eta2_champion"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_b6v7():
    spec = importlib.util.spec_from_file_location("build_b6v7", W5 / "build_b6v7.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derive():
    source, inherited = load_b6v7().derive()
    intermediate = source
    changes = []

    def patch(before, after):
        nonlocal source
        assert source.count(before) == 1, (before[:160], source.count(before))
        source = source.replace(before, after)
        changes.append((before, after))

    patch(
        '#include "bal_hessian_generated.cuh"',
        '#include "deterministic_blas.cuh"\n#include "bal_hessian_generated.cuh"',
    )
    patch('#include "full_step_model.cuh"', '#include "deterministic_full_model.cuh"')
    patch(
        'Scalar ComputeCost(const DeviceProblem& p, const DeviceState& s,\n'
        '                   int rk = 0, Scalar rk_a2 = 0.0) {',
        '#include "deterministic_cost.cuh"\n\n'
        'Scalar ComputeCost(const DeviceProblem& p, const DeviceState& s,\n'
        '                   int rk = 0, Scalar rk_a2 = 0.0) {\n'
        '  if (PrismW6DeterministicEnabled())\n'
        '    return PrismW6DeterministicCost(p,s,rk,rk_a2);',
    )
    patch(
        '// ===== REVIEW: block-congruence scaling (OCA_BLOCKEQ=1)',
        '#include "deterministic_mfree.cuh"\n\n'
        '// ===== REVIEW: block-congruence scaling (OCA_BLOCKEQ=1)',
    )
    patch(
        '  M((void**)&bc,(size_t)n_cf*sizeof(Scalar));M((void**)&bp,(size_t)n_p*sizeof(Scalar));',
        '  const bool w6_deterministic=PrismW6DeterministicEnabled();\n'
        '  int* w6_cslot_to_obs=nullptr;\n'
        '  if(w6_deterministic){\n'
        '    if(CD!=9||compact_mode!=2||mf_fp32||shared_intr||!classical_lm)\n'
        '      throw std::runtime_error("wave6 deterministic path requires the CD9 unshared compact2 single-shift champion");\n'
        '    M((void**)&w6_cslot_to_obs,(size_t)nobs*sizeof(int));\n'
        '    W6InvertPermutation<<<GridSize(nobs),256>>>(p.obs2cslot,nobs,w6_cslot_to_obs);\n'
        '    std::printf("W6_DETERMINISTIC active fixed assembly/pass1/cost/model trees\\n");\n'
        '  }\n'
        '  M((void**)&bc,(size_t)n_cf*sizeof(Scalar));M((void**)&bp,(size_t)n_p*sizeof(Scalar));',
    )
    patch(
        '    if(r2acc) KernelDampIntr9<<<GridSize(ncam),256>>>(Hcc,INTR_F(p,s),r2acc,obscnt,ncam,intr_damp,k2mask);',
        '    if(w6_deterministic){\n'
        '      W6DeterministicCameraAssembly9<<<ncam,32>>>(p.mf_coff,w6_cslot_to_obs,p.cam_idx,p.pt_idx,p.uv,\n'
        '        s.R,s.t,s.X,INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),ncam,k2mask,rk,rk_a2,Hcc,bc,r2acc,obscnt);\n'
        '      W6DeterministicPointAssembly9<<<npt,32>>>(p.point_obs_offsets,p.point_obs_list,p.cam_idx,p.pt_idx,p.uv,\n'
        '        s.R,s.t,s.X,INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),npt,k2mask,rk,rk_a2,Cdiag,bp);\n'
        '    }\n'
        '    if(r2acc) KernelDampIntr9<<<GridSize(ncam),256>>>(Hcc,INTR_F(p,s),r2acc,obscnt,ncam,intr_damp,k2mask);',
    )
    patch(
        '      else       { MFPass1<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,vf,nobs,tacc);\n'
        '                   MFVinvApply<<<GridSize(npt),256>>>(Rf,tacc,npt,uu);',
        '      else       { if(w6_deterministic)\n'
        '                     W6DeterministicPass1<CD,Fragment><<<npt,32>>>(Gp,p.point_obs_offsets,p.point_obs_list,p.cam_idx,p.obs2cslot,vf,npt,nobs,tacc);\n'
        '                   else MFPass1<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,vf,nobs,tacc);\n'
        '                   MFVinvApply<<<GridSize(npt),256>>>(Rf,tacc,npt,uu);',
    )
    patch(
        '        else        MFPass1Multi<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,XCU,n_cf,na,nobs,TACC,n_p); });',
        '        else if(w6_deterministic)\n'
        '          W6DeterministicPass1Multi<CD,Fragment><<<npt,32>>>(Gp,p.point_obs_offsets,p.point_obs_list,p.cam_idx,p.obs2cslot,XCU,n_cf,na,npt,nobs,TACC,n_p);\n'
        '        else MFPass1Multi<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,XCU,n_cf,na,nobs,TACC,n_p); });',
    )
    patch(
        '  cudaFree(Hcc);cudaFree(Cdiag);cudaFree(Gp);cudaFree(Gc);cudaFree(Bo);cudaFree(fragment_slots);cudaFree(fragment_camera_ids);',
        '  cudaFree(Hcc);cudaFree(Cdiag);cudaFree(Gp);cudaFree(Gc);cudaFree(Bo);cudaFree(fragment_slots);cudaFree(fragment_camera_ids);cudaFree(w6_cslot_to_obs);',
    )

    # cuBLAS reductions use block-level accumulation internally and showed
    # last-bit run-to-run variation at the first accepted outer.  Route every
    # source-level dot/norm through a fixed two-level tree while D0 is active;
    # the wrappers delegate verbatim when the flag is off.  Header-internal
    # calls belong to inactive research features and remain untouched.
    dot_count = source.count("cublasDdot(")
    norm_count = source.count("cublasDnrm2(")
    assert dot_count > 20 and norm_count > 10, (dot_count, norm_count)
    source = source.replace("cublasDdot(", "PrismW6Ddot(")
    source = source.replace("cublasDnrm2(", "PrismW6Dnrm2(")

    transformed = source
    restored = source.replace("PrismW6Ddot(", "cublasDdot(")
    restored = restored.replace("PrismW6Dnrm2(", "cublasDnrm2(")
    for before, after in reversed(changes):
        assert restored.count(after) == 1
        restored = restored.replace(after, before)
    assert restored == intermediate
    return transformed, inherited + len(changes) + 2


def main():
    subprocess.run(["python3", str(F / "build.py"), "--check-only"], check=True)
    build = P / "build"
    build.mkdir(exist_ok=True)
    src = build / "deterministic.cu"
    binary = build / "prism-deterministic"
    source, count = derive()
    src.write_text(source)
    cmd = ["nvcc", "-O3", "-DNDEBUG", "-std=c++17", "-arch=sm_89",
           "-I/usr/include/eigen3", "-I" + str(P),
           "-I" + str(F / "source" / "headers"), "-I" + str(W5),
           str(src), "-o", str(binary), "-lcublas", "-lcusolver"]
    with (build / "deterministic-build.log").open("w") as log:
        subprocess.run(cmd, env=dict(os.environ, TMPDIR="/dev/shm"),
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    manifest = {
        "command": cmd,
        "source_sha256": sha(src),
        "binary_sha256": sha(binary),
        "champion_sha256": sha(F / "champion.json"),
        "wave5_candidate_sha256": sha(W5 / "optimized_candidate.json"),
        "reversible_patch_count": count,
        "sources": {str(path): sha(path) for path in [
            P / "build_deterministic.py", P / "deterministic_blas.cuh", P / "deterministic_cost.cuh",
            P / "deterministic_full_model.cuh", P / "deterministic_mfree.cuh"]},
        "protocol_sha256": sha(P / "PROTOCOL.md"),
    }
    (P / "deterministic-build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("BUILT", binary, manifest["binary_sha256"])


if __name__ == "__main__":
    main()
