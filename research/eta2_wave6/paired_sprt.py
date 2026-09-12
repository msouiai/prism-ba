#!/usr/bin/env python3
"""Paired hit-rate inference for deterministic common-random-number cohorts."""
from dataclasses import dataclass, asdict
import argparse
import json
import math


@dataclass
class PairedSprt:
    q0: float = 0.35
    q1: float = 0.50
    alpha: float = 0.05
    beta: float = 0.05
    max_pairs: int = 100
    pairs: int = 0
    variant_wins: int = 0
    control_wins: int = 0
    double_hits: int = 0
    double_misses: int = 0

    def __post_init__(self):
        if not (0 < self.q0 < self.q1 < 1):
            raise ValueError("require 0 < q0 < q1 < 1")
        if not (0 < self.alpha < 1 and 0 < self.beta < 1):
            raise ValueError("alpha and beta must lie in (0,1)")
        if self.max_pairs <= 0:
            raise ValueError("max_pairs must be positive")

    @property
    def discordant(self):
        return self.variant_wins + self.control_wins

    @property
    def log_likelihood_ratio(self):
        return (self.variant_wins * math.log(self.q1 / self.q0)
                + self.control_wins * math.log((1 - self.q1) / (1 - self.q0)))

    @property
    def lower(self):
        return math.log(self.beta / (1 - self.alpha))

    @property
    def upper(self):
        return math.log((1 - self.beta) / self.alpha)

    @property
    def decision(self):
        value = self.log_likelihood_ratio
        if value >= self.upper:
            return "noninferior"
        if value <= self.lower:
            return "harmful"
        if self.pairs >= self.max_pairs:
            return "inconclusive_at_cap"
        return "continue"

    def update(self, control_hit, variant_hit):
        if self.pairs >= self.max_pairs:
            raise RuntimeError("pair cap already reached")
        control_hit, variant_hit = bool(control_hit), bool(variant_hit)
        self.pairs += 1
        if variant_hit and not control_hit:
            self.variant_wins += 1
        elif control_hit and not variant_hit:
            self.control_wins += 1
        elif control_hit:
            self.double_hits += 1
        else:
            self.double_misses += 1
        return self.decision

    def report(self):
        result = asdict(self)
        result.update({
            "discordant": self.discordant,
            "log_likelihood_ratio": self.log_likelihood_ratio,
            "lower_boundary": self.lower,
            "upper_boundary": self.upper,
            "decision": self.decision,
        })
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pairs_json", help="JSON list with control_hit and variant_hit")
    parser.add_argument("--q0", type=float, default=.35)
    parser.add_argument("--q1", type=float, default=.50)
    parser.add_argument("--alpha", type=float, default=.05)
    parser.add_argument("--beta", type=float, default=.05)
    parser.add_argument("--max-pairs", type=int, default=100)
    args = parser.parse_args()
    test = PairedSprt(args.q0, args.q1, args.alpha, args.beta, args.max_pairs)
    for pair in json.load(open(args.pairs_json)):
        if test.decision != "continue":
            break
        test.update(pair["control_hit"], pair["variant_hit"])
    print(json.dumps(test.report(), indent=2))


if __name__ == "__main__":
    main()
