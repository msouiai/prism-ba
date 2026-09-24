#!/usr/bin/env python3
import pathlib
import cg_stop_large as study
study.ROOT=pathlib.Path('/workspace/prism-tr-safeguard/large')
study.BINS={'control':pathlib.Path('/workspace/prism-tr-cg-stop/guarded/prism-tr'),'tr':pathlib.Path('/workspace/prism-tr-safeguard/pair/prism-tr'),'factored':pathlib.Path('/workspace/prism-tr-safeguard/factored/prism-tr'),'caspar32':pathlib.Path('/workspace/prism-caspar-current/caspar32')}
study.PRISM_ARMS=('control','tr','factored');study.COMMON.update(OCA_CG_STOP='2',OCA_FP32_PRODUCTS='1',OCA_PAIR_SAFE='2')
study.SCOPE_OVERRIDE='N1 largest scene: frozen guarded TR, paired safeguard with FP32 products/reference ranking, factored FP64 derivatives/Jd on guarded TR, Caspar FP32. Direct full nonlinear acceptance retained. Effective original-observation endpoint target nominal*(1-1e-8). Caspar32 fixed .1% tighter native stopping margin, credited at that stricter crossing only. All mandatory candidate checks charged; no diagnostic instrumentation. Native timing excludes input loading, established setup-scope differences remain. Misses retained.'
if __name__=='__main__':study.main()
