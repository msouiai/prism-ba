import pathlib
import tr_cg_study as s
s.ROOT=pathlib.Path('/workspace/prism-tr-point-prep');s.BINS={'double':pathlib.Path('/workspace/prism-tr-safeguard/factored/prism-tr'),'storage':s.ROOT/'combined/prism-tr'};s.COMMON.update(OCA_CG_STOP='2');s.SCOPE_OVERRIDE='double=factored guarded TR control, storage=point preparation candidate described in hashed manifest. Original double observation endpoint audit. FP64 full nonlinear/model acceptance, same target and controller. Native timing, no diagnostic instrumentation.'
s.SCENES['final-4585']=(7488277.5282109585,20)
if __name__=='__main__':s.main()
