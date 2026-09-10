#!/usr/bin/env python3
"""Small, cyclic-order rejection ablations (one frozen binary per study)."""
import argparse
import sys
import novelty_ablation as runner

p=argparse.ArgumentParser(add_help=False)
p.add_argument('--study',choices=['coverage','coverage-pair','rearm'],default='coverage')
a,remaining=p.parse_known_args()
sys.argv=[sys.argv[0]]+remaining
if a.study in ['coverage','coverage-pair']:
    runner.ARMS={
        'single': {'OCA_NSHIFTS':'1','OCA_MENU_BACKTRACK':'8'},
        'multi': {'OCA_NSHIFTS':'5','OCA_MENU_BACKTRACK':'8'},
        'coverage': {'OCA_NSHIFTS':'5','OCA_MENU_BACKTRACK':'8','OCA_MENU_COVERAGE':'1'},
    }
    if a.study=='coverage-pair':del runner.ARMS['single']
else:
    runner.ARMS={
        'multi': {'OCA_NSHIFTS':'5','OCA_MENU_BACKTRACK':'8'},
        'rearm': {'OCA_NSHIFTS':'5','OCA_MENU_BACKTRACK':'8','OCA_BACKTRACK_REARM':'1'},
    }
if __name__=='__main__':runner.main()
