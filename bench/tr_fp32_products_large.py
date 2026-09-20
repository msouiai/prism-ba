#!/usr/bin/env python3
"""One bounded fresh pair plus Caspar FP32, retaining original-double endpoint audit."""
import pathlib
import cg_stop_large as study
study.ROOT=pathlib.Path('/workspace/prism-tr-fp32-products/large')
study.BINS={'control':pathlib.Path('/workspace/prism-tr-cg-stop/guarded/prism-tr'),'tr':pathlib.Path('/workspace/prism-tr-fp32-products/reliable/prism-tr'),'caspar32':pathlib.Path('/workspace/prism-caspar-current/caspar32')}
study.COMMON.update(OCA_CG_STOP='2',OCA_FP32_PRODUCTS='1')
study.SCOPE_OVERRIDE='N1 Final13682: guarded projected TR control, reliable FP32-products candidate, Caspar FP32. Candidate retains FP64 accumulation/factors/model/acceptance and reference residual checks/fallback (charged). OCA_FP32_PRODUCTS ignored by frozen control. Effective original-double audited target nominal*(1-1e-8). Caspar FP32 fixed .1% tighter native stop, credited at that stricter crossing only. Same existing solver-native timing scopes; no profiler. Misses retained.'
if __name__=='__main__':study.main()
