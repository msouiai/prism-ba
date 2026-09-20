#!/usr/bin/env python3
"""Fresh bounded largest-scene reference-ranking comparison with Caspar FP32."""
import pathlib
import cg_stop_large as study
study.ROOT=pathlib.Path('/workspace/prism-tr-reference/large')
study.BINS={'control':pathlib.Path('/workspace/prism-tr-cg-stop/guarded/prism-tr'),'tr':pathlib.Path('/workspace/prism-tr-reference/rank/prism-tr'),'caspar32':pathlib.Path('/workspace/prism-caspar-current/caspar32')}
study.COMMON.update(OCA_CG_STOP='2',OCA_FP32_PRODUCTS='1')
study.SCOPE_OVERRIDE='N1 Final13682: guarded projected TR control, reference-ranking FP32-products candidate, Caspar FP32. Candidate uses exact reference Schur values to rank/stop projected proposals; residual fallback, radius and FP64 nonlinear acceptance retained and charged. Effective original-double target nominal*(1-1e-8). Caspar FP32 fixed .1% tighter native stop, credited only at that stricter crossing. Solver-native timings; misses retained.'
if __name__=='__main__':study.main()
