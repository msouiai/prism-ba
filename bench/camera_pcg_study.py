import pathlib,sys
import tr_cg_study as s
s.ROOT=pathlib.Path('/workspace/prism-tr-preconditioner');s.BINS={'double':pathlib.Path('/workspace/prism-tr-point-prep/combined/prism-tr'),'storage':s.ROOT/'pcg-v2/prism-tr'};s.COMMON.update(OCA_CG_STOP='2',OCA_PCG='1');s.SCOPE_OVERRIDE='Control=combined guarded TR. Candidate=ordinary block PCG on unchanged diagonal coordinates, damping and TR metric. Full Gram projected z basis and reference model gate. Every endpoint audited against original-double observations. Small audit uses instrumented recurrence checks; timing has no diagnostic matvecs. Conditional refresh is preconditioner-only, never reuses the linear system.'
if '--schur' in sys.argv:sys.argv.remove('--schur');s.COMMON['OCA_PCG_SCHUR']='1'
if '--reuse' in sys.argv:sys.argv.remove('--reuse');s.COMMON['OCA_PCG_REUSE']='1'
s.SCENES['final-4585']=(7488277.5282109585,20)
if __name__=='__main__':s.main()
