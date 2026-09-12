#!/usr/bin/env python3
"""Isolated opening radial-clipping ablation; frozen source remains immutable."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

P = Path(__file__).resolve().parent
C = P.parent
F = C.parent / 'eta2_champion'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def derive():
    subprocess.run(['python3', str(F / 'build.py'), '--check-only'], check=True)
    original = (F / 'source/prism_eta2.cu').read_text()
    source, patches = original, []

    def patch(old, new, kind):
        nonlocal source
        assert source.count(old) == 1, (old[:100], source.count(old))
        source = source.replace(old, new)
        patches.append((old, new, kind))

    anchor = 'template <int CD>\nRunLog SolveMFreeShiftedCG('
    patch(anchor, '#include "attempt_trace.h"\n\n' + anchor, 'instrumentation')
    anchor = '  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);'
    patch(anchor, anchor + '''
  const bool open_unclip_on=getenv("OCA_OPEN_UNCLIP") && atoi(getenv("OCA_OPEN_UNCLIP"))!=0;
  bool open_unclip_handoff_printed=false;
  std::unique_ptr<StcgAttemptTrace> attempt_trace;
  if(const char* path=getenv("OCA_STCG_ATTEMPTS"))attempt_trace=std::make_unique<StcgAttemptTrace>(path);
  if(open_unclip_on)std::printf("OPEN_UNCLIP_CONFIG accepted_outers=3 operator=production forcing=production clipping=off_strict_ball_retained\\n");''', 'configuration_and_instrumentation')
    anchor = '   if(BudgetExpired()){std::printf("BUDGET stop=before_attempt outer=%d seconds=%.9g\\n",k,max_seconds);break;}'
    patch(anchor, anchor + '''
   StcgAttemptClock attempt_clock(attempt_trace.get(),k,retries,!need_assembly,&st.matvecs);
   const bool open_unclip_active=open_unclip_on && n_accept<3;
   if(open_unclip_active)
     std::printf("OPEN_UNCLIP_ATTEMPT outer=%d retry=%d accepts_before=%d\\n",k,retries,n_accept);
   if(open_unclip_on && !open_unclip_active && !open_unclip_handoff_printed){
     open_unclip_handoff_printed=true;
     std::printf("OPEN_UNCLIP_HANDOFF outer=%d accepts=%d previous_rhs_norm=%.17g\\n",k,n_accept,(double)prev_bnorm);
   }''', 'configuration_and_instrumentation')
    anchor = '    // ---- operator ----\n    auto Kv='
    patch(anchor, '''    if(open_unclip_active &&
       (!pcg || !classical_lm || !attr_radius || !attr_strict || !numeric_guard ||
        CD!=9 || shared_intr || mf_fp32 || rk || !use_equil || L!=1 || block_on ||
        pcg->reuse || pcg->schur || attr_split || camera_tr || recycle_mode || jit_on ||
        k2mask!=0 || intr_damp!=1 || score_stride!=1 || tau_eff!=lam_cam ||
        (getenv("OCA_POLY_CONG") && atoi(getenv("OCA_POLY_CONG"))!=0) ||
        rld.actor || rld.fixed_eta!=2 ||
        (getenv("OCA_CG_STOP") && atoi(getenv("OCA_CG_STOP"))!=0)))
      throw std::runtime_error("opening unclipping requires frozen unshared SIMPLE_RADIAL coupled strict Eta2 configuration");

''' + anchor, 'configuration_guard')
    anchor = '    for(cg_it=0; cg_it<maxck; ++cg_it){\n      KvS(pv_,Ap_);'
    patch(anchor, '    for(cg_it=0; cg_it<maxck; ++cg_it){\n      if(attempt_trace)++attempt_clock.row.pcg_iterations;\n      KvS(pv_,Ap_);', 'instrumentation')
    anchor = '      if(!(pAp>1e-14*pp)){\n        if(model_capture'
    patch(anchor, '      if(!(pAp>1e-14*pp)){\n        if(attempt_trace)attempt_clock.row.cutoff=true;\n        if(model_capture', 'instrumentation')
    anchor = '        lam_cam=numeric_floor;prev_bnorm=numeric_prior_bnorm;need_assembly=false;factor_cached=false;'
    patch(anchor, anchor + '\n        if(attempt_trace)attempt_clock.row.numeric_repair=true;', 'instrumentation')
    anchor = '        if(attr_raw_norm>attr_R){double scale=attr_R/attr_raw_norm;cublasDscal(blas,n_c,&scale,xs[0],1);}'
    patch(anchor, anchor.replace('if(attr_raw_norm>attr_R)', 'if(!open_unclip_active && attr_raw_norm>attr_R)'), 'algorithm')
    anchor = '    if(!accepted && retries<max_inner_retry){'
    patch(anchor, '    if(attempt_trace)attempt_clock.row.accepted=accepted;\n' + anchor, 'instrumentation')
    restored = source
    for old, new, _ in reversed(patches):
        assert restored.count(new) == 1, ('inverse ambiguous', new[:100])
        restored = restored.replace(new, old)
    assert restored == original
    assert sum(kind == 'algorithm' for _, _, kind in patches) == 1
    return source, patches


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    source, patches = derive()
    build = P / 'build'
    build.mkdir(exist_ok=True)
    path = build / 'prism_opening_unclip.cu'
    path.write_text(source)
    assert sha(P / 'attempt_trace.h') == sha(C / 'steihaug/attempt_trace.h')
    headers = {'attempt_trace.h': sha(P / 'attempt_trace.h')}
    manifest = dict(frozen_source_sha256=sha(F / 'source/prism_eta2.cu'),
                    champion_config_sha256=sha(F / 'champion.json'),
                    source_manifest_sha256=sha(F / 'source_manifest.json'),
                    derived_source_sha256=sha(path),
                    substitutions=len(patches), algorithm_substitutions=1,
                    substitution_kinds=[kind for _, _, kind in patches],
                    inverse_patch_source_parity=True, local_headers=headers,
                    exact_common_attempt_trace_sha256=sha(C / 'steihaug/attempt_trace.h'),
                    protocol_sha256=sha(C / 'PROTOCOL_05_UNCLIP.md'),
                    flag='OCA_OPEN_UNCLIP=1', default='off')
    if not args.check_only:
        cmd = ['nvcc', '-O3', '-DNDEBUG', '-std=c++17', '-arch=sm_89',
               '-I/usr/include/eigen3', '-I' + str(P), '-I' + str(F / 'source/headers'),
               str(path), '-o', str(build / 'prism-opening-unclip'), '-lcublas', '-lcusolver']
        env = os.environ.copy()
        env['TMPDIR'] = '/dev/shm'
        with (build / 'build.log').open('w') as log:
            subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        assert headers == {name: sha(P / name) for name in headers}
        assert manifest['derived_source_sha256'] == sha(path)
        assert manifest['protocol_sha256'] == sha(C / 'PROTOCOL_05_UNCLIP.md')
        manifest.update(command=cmd, compiler_tmpdir='/dev/shm', binary_sha256=sha(build / 'prism-opening-unclip'))
    (P / 'build_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
