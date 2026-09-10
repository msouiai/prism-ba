#!/usr/bin/env python3
import pathlib,sys
import tr_cg_study as study
study.ROOT=pathlib.Path('/workspace/prism-tr-safeguard');study.BINS={'double':pathlib.Path('/workspace/prism-tr-cg-stop/guarded/prism-tr'),'storage':study.ROOT/'pair/prism-tr'}
study.COMMON.update(OCA_CG_STOP='2',OCA_FP32_PRODUCTS='1',OCA_PAIR_SAFE='2')
study.SCOPE_OVERRIDE='double=guarded projected TR; storage=the candidate described in its hashed stop-manifest. Pair candidate safeguards both proposals before ranking; factored candidate changes FP64 derivatives/Jd only. Direct FP64 full-model acceptance retained. Original-observation endpoint audit. Block model, when requested, is diagnostic only.'
if '--block-audit' in sys.argv:sys.argv.remove('--block-audit');study.COMMON['OCA_BLOCK_MODEL_AUDIT']='1'
if '--pair-diagnostic' in sys.argv:sys.argv.remove('--pair-diagnostic');study.COMMON['OCA_PAIR_SAFE']='1'
if __name__=='__main__':study.main()
