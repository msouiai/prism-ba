#!/usr/bin/env python3
"""Reuse the endpoint-audited bounded paired harness with guarded TR as control."""
import sys,pathlib
import tr_cg_study as study
study.ROOT=pathlib.Path('/workspace/prism-tr-fp32-products')
study.BINS={'double':pathlib.Path('/workspace/prism-tr-cg-stop/guarded/prism-tr'),'storage':study.ROOT/'reliable/prism-tr'}
study.SCOPE_OVERRIDE='double=guarded projected TR control; storage=FP32 local Schur products candidate. FP64 sums, point solve, CG, state, checkpoint reference model, projection verification and nonlinear acceptance. OCA_FP32_PRODUCTS ignored by frozen control. Timing with --residual-audit is instrumented and not a benchmark. Original-observation independent endpoint audit; misses retained.'
study.COMMON.update(OCA_CG_STOP='2',OCA_FP32_PRODUCTS='1')
if '--residual-audit' in sys.argv:
 sys.argv.remove('--residual-audit');study.COMMON['OCA_FP32_RESIDUAL_AUDIT']='1'
# Labels double/storage are inherited: guarded control/FP32-products candidate.
if __name__=='__main__':study.main()
