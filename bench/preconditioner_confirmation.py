import pathlib
import cg_stop_large as s
s.PRISM_ARMS=('combined',);s.COMMON.update(OCA_CG_STOP='2');s.SCOPE_OVERRIDE='N3 paired combined PRISM and Caspar FP32 on two large scenes. Same audited targets, .1% tighter Caspar native guard, 20s native caps, original-double endpoint audits. Solver-native timing excludes loading; established setup-scope differences retained. GPU serialized.'
bins={'combined':pathlib.Path('/workspace/prism-tr-point-prep/combined/prism-tr'),'caspar32':pathlib.Path('/workspace/prism-caspar-current/caspar32')}
for rep in range(3):
 s.ROOT=pathlib.Path('/workspace/prism-tr-preconditioner')/f'confirmation-{rep}';s.BINS=dict(list(bins.items())[::(-1 if rep%2 else 1)]);s.SCENES=[('final-13682',27318392.631312046,20),('final-4585',7488277.5282109585,20)];s.main()
