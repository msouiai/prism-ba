#!/usr/bin/env python3
"""Bounded medium-scene screen. Early progress only, no convergence claim."""
import sys
import novelty_ablation as runner
runner.ARMS={
 'single':{'OCA_NSHIFTS':'1','OCA_MENU_BACKTRACK':'8'},
 'multi':{'OCA_NSHIFTS':'5','OCA_MENU_BACKTRACK':'8'},
 'rearm':{'OCA_NSHIFTS':'5','OCA_MENU_BACKTRACK':'8','OCA_BACKTRACK_REARM':'1'},
}
if __name__=='__main__':runner.main()
