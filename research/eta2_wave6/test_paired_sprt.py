import math
import unittest

from paired_sprt import PairedSprt


class PairedSprtTest(unittest.TestCase):
    def test_registered_all_win_and_all_loss_boundaries(self):
        wins = PairedSprt()
        while wins.decision == "continue":
            wins.update(False, True)
        self.assertEqual(wins.decision, "noninferior")
        self.assertEqual(wins.variant_wins, 9)

        losses = PairedSprt()
        while losses.decision == "continue":
            losses.update(True, False)
        self.assertEqual(losses.decision, "harmful")
        self.assertEqual(losses.control_wins, 12)

    def test_concordant_pairs_do_not_change_likelihood(self):
        test = PairedSprt()
        for pair in [(True, True), (False, False)] * 10:
            test.update(*pair)
        self.assertEqual(test.discordant, 0)
        self.assertEqual(test.log_likelihood_ratio, 0.0)
        self.assertEqual(test.decision, "continue")

    def test_arm_order_and_pair_order_are_irrelevant(self):
        pairs = [(False, True)] * 5 + [(True, False)] * 4 + [(True, True)] * 3
        forward, reverse = PairedSprt(), PairedSprt()
        for pair in pairs:
            forward.update(*pair)
        for pair in reversed(pairs):
            reverse.update(*pair)
        self.assertEqual(forward.report(), reverse.report())

    def test_cap_is_explicitly_inconclusive(self):
        test = PairedSprt(max_pairs=4)
        for pair in [(True, True), (False, False)] * 2:
            test.update(*pair)
        self.assertEqual(test.decision, "inconclusive_at_cap")

    def test_registered_boundaries(self):
        test = PairedSprt()
        self.assertAlmostEqual(test.upper, math.log(19.0))
        self.assertAlmostEqual(test.lower, -math.log(19.0))


if __name__ == "__main__":
    unittest.main()
