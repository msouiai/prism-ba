#!/usr/bin/env python3
"""Isolate early stopping from the central-convergence scoring probe."""
import novelty_ablation as runner

runner.ARMS = {
    'probe-only': {'OCA_NSHIFTS': '5', 'OCA_MENU_BACKTRACK': '8',
                   'OCA_PROGRESSIVE_DEPTH': '2'},
    'progressive': {'OCA_NSHIFTS': '5', 'OCA_MENU_BACKTRACK': '8',
                    'OCA_PROGRESSIVE_DEPTH': '1'},
}

if __name__ == '__main__':
    runner.main()
