"""Optional fresh output directory and reference binary for reproduction."""
import os,pathlib
ROOT=pathlib.Path(__file__).resolve().parent
OUT=pathlib.Path(os.environ.get('PRISM_PHYSICS_OUT','/workspace/prism-schur-physics'))
def reference_eta2():
    old=pathlib.Path('/tmp/prism-rl-actor/build/prism-tr')
    default=old if old.exists() else ROOT.parent/'eta2_champion/build/prism-eta2'
    return os.environ.get('PRISM_REFERENCE_ETA2',str(default))
