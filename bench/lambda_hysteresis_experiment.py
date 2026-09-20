#!/usr/bin/env python3
"""Frozen two-arm priority pilot, using the existing retained-run harness."""
import sys,pathlib
import novelty_ablation as runner
runner.ARMS={
 'control':{'OCA_NSHIFTS':'5','OCA_MENU_BACKTRACK':'8','OCA_LAMBDA_HYSTERESIS_LOG':'1'},
 'hysteresis':{'OCA_NSHIFTS':'5','OCA_MENU_BACKTRACK':'8','OCA_LAMBDA_HYSTERESIS_LOG':'1','OCA_LAMBDA_HYSTERESIS':'0.95'}}
if __name__=='__main__':runner.main()
