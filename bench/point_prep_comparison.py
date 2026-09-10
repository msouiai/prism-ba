#!/usr/bin/env python3
import pathlib
import cg_stop_large as s
BASE=pathlib.Path('/workspace/prism-tr-point-prep')
s.COMMON.update(OCA_CG_STOP='2')
s.PRISM_ARMS=('factored','control')
s.SCOPE_OVERRIDE='Paired factored FP64 guarded TR, old guarded TR control, Caspar FP32. Three largest-scene repeats in rotating order plus N1 another large scene. Original-double endpoint qualification at nominal*(1-1e-8), Caspar native .1% tighter stop. Solver-native times exclude input loading and retain established setup-scope differences; GPU work serialized.'
allbins={'factored':pathlib.Path('/workspace/prism-tr-safeguard/factored/prism-tr'),'caspar32':pathlib.Path('/workspace/prism-caspar-current/caspar32'),'control':pathlib.Path('/workspace/prism-tr-cg-stop/guarded/prism-tr')}
for rep in range(3):
 s.ROOT=BASE/('repeat-'+str(rep));keys=list(allbins);keys=keys[rep:]+keys[:rep];s.BINS={k:allbins[k] for k in keys};s.SCENES=[('final-13682',27318392.631312046,20)];s.main()
s.ROOT=BASE/'other-large';s.BINS=allbins;s.SCENES=[('final-4585',7488277.5282109585,20)];s.main()
