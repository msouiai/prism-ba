#!/usr/bin/env python3
"""Frozen compact FP64 comparison on five additional large BAL instances."""
import argparse,pathlib,sys
import validation_study as study
SCENES=['final-871','final-961','venice-951','venice-1778','dubrovnik-356']
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,default=pathlib.Path('/workspace/prism-five-large'));a=p.parse_args()
 study.COMMON.update(OCA_COMPACT_FRAGMENTS='2')
 sys.argv=['validation_study.py','budgets','--root',str(a.root),'--binary',str(a.root/'prism-frozen'),'--caspar','/workspace/prism-validation/caspar-frozen','--scenes',*SCENES,'--reps','1','--budget-seconds','30','--timeout','180','--keep-going']
 study.main()
if __name__=='__main__':main()
