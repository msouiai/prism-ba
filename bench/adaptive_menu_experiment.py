#!/usr/bin/env python3
import novelty_ablation as runner
runner.ARMS={
 'single':{'OCA_NSHIFTS':'1','OCA_MENU_BACKTRACK':'8'},
 'multi':{'OCA_NSHIFTS':'5','OCA_MENU_BACKTRACK':'8'},
 'adaptive':{'OCA_NSHIFTS':'5','OCA_MENU_BACKTRACK':'8','OCA_ADAPTIVE_MENU':'1'}}
if __name__=='__main__':runner.main()
