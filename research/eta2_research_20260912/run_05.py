#!/usr/bin/env python3
"""Frozen twenty-repeat opening predictor cohort; no outcome-based sampling."""
from pathlib import Path
import subprocess
from grid_common import P,F,ORIGINAL,run,write
def main():
    subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
    rows=[]
    for rep in range(20):
        for scene in (['ladybug-1197','final-3068'] if rep%2==0 else ['final-3068','ladybug-1197']):
            folder=P/'evidence/predictor'/f'{scene}-original-{rep}'
            rows.append(run(folder,scene,'original',rep,ORIGINAL,{},P/'PROTOCOL_05_PRETEST.md'))
            write(P/'predictor-results.json',rows)
if __name__=='__main__':main()
