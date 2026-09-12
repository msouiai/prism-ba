#!/usr/bin/env python3
"""Algebra checks for the registered soft-rho map."""
import math
import unittest


def scale(rho, threshold=.1):
    if 0 < rho <= threshold:
        return rho / threshold
    return 1.0


class SoftAcceptanceTest(unittest.TestCase):
    def test_registered_examples(self):
        self.assertEqual(scale(-1), 1)
        self.assertEqual(scale(0), 1)
        self.assertAlmostEqual(scale(.027), .27)
        self.assertEqual(scale(.1), 1)
        self.assertEqual(scale(.2), 1)

    def test_continuity_at_accept_boundary(self):
        left = scale(math.nextafter(.1, 0.0))
        right = scale(math.nextafter(.1, 1.0))
        self.assertLess(abs(left - right), 1e-14)

    def test_state_tends_to_rejected_state_at_zero(self):
        for rho in (1e-3, 1e-6, 1e-12):
            self.assertAlmostEqual(scale(rho), 10*rho)


if __name__ == "__main__":
    unittest.main()
