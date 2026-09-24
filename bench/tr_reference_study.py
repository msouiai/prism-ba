#!/usr/bin/env python3
"""Bounded endpoint-audited comparisons to frozen guarded projected TR."""
import pathlib,sys
import tr_cg_study as study
study.ROOT=pathlib.Path('/workspace/prism-tr-reference')
study.BINS={'double':pathlib.Path('/workspace/prism-tr-cg-stop/guarded/prism-tr'),'storage':study.ROOT/'rank/prism-tr'}
study.COMMON.update(OCA_CG_STOP='2',OCA_FP32_PRODUCTS='1')
study.SCOPE_OVERRIDE='double=guarded projected TR control; storage=explicit candidate manifest. Rank candidate uses FP32 local products and reference FP64 projected model ranking, residual fallback, radius checks/full nonlinear acceptance. Point-owned candidate retains FP64 arithmetic. Original-observation independent endpoint audit. Trace/residual-audit runs are diagnostic; misses retained.'
if '--residual-audit' in sys.argv:
 sys.argv.remove('--residual-audit');study.COMMON['OCA_FP32_RESIDUAL_AUDIT']='1'
if __name__=='__main__':study.main()
