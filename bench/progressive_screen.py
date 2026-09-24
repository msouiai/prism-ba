#!/usr/bin/env python3
"""Short, interleaved work/quality screen; all arms use one frozen binary."""
import novelty_ablation as runner

runner.ARMS = {
    'single': {'OCA_NSHIFTS': '1', 'OCA_MENU_BACKTRACK': '8'},
    'multi': {'OCA_NSHIFTS': '5', 'OCA_MENU_BACKTRACK': '8'},
    'progressive': {'OCA_NSHIFTS': '5', 'OCA_MENU_BACKTRACK': '8',
                    'OCA_PROGRESSIVE_DEPTH': '1'},
}

if __name__ == '__main__':
    runner.main()
