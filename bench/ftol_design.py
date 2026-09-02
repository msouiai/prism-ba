#!/usr/bin/env python3
"""Offline ftol stop-rule design from no-stop reference traces.

Replays the persistent-flatness rule (stop after K consecutive outers whose
relative cost improvement < ftol, rejects counting as zero improvement, same
semantics as OCA_FTOL/OCA_FTOL_K) over full 400-outer traces and reports, for
each (ftol, K): stop wall, stop cost, and quality gap vs the full run's final
cost. Goal: find the frontier point that keeps venice-style late gains without
paying final-4585-style storm walls.
"""
import re, sys, glob, os

PAT = re.compile(r"^\s*([0-9.]+)\s+MFCG it\s+(\d+)\s+cost=([0-9.e+]+)\s.*\s(acc|REJ)\s")

def load(path):
    rows = []
    for ln in open(path, errors="replace"):
        m = PAT.match(ln)
        if m:
            rows.append((float(m.group(1)), int(m.group(2)), float(m.group(3)), m.group(4) == "acc"))
    return rows

def simulate(rows, ftol, K):
    prev = None
    streak = 0
    for t, it, cost, acc in rows:
        if prev is not None:
            rel = (prev - cost) / max(prev, 1e-300) if acc else 0.0
            streak = streak + 1 if rel < ftol else 0
            if streak >= K:
                return t, cost
        if acc:
            prev = cost
    return rows[-1][0], min(c for _, _, c, a in rows if a) if rows else (0, 0)

def main(d):
    ftols = [1e-5, 2e-5, 5e-5, 1e-4]
    Ks = [3, 5, 8, 12]
    for path in sorted(glob.glob(os.path.join(d, "*_nostop_*.trace"))):
        rows = load(path)
        if not rows:
            continue
        full_t = rows[-1][0]
        full_c = min(c for _, _, c, a in rows if a)
        name = os.path.basename(path).replace(".trace", "")
        print(f"\n== {name}: full run {full_t:.0f}s cost={full_c:.6e} ({len(rows)} outer rows) ==")
        print(f"{'ftol':>8} {'K':>3} {'stop_s':>8} {'stop_cost':>14} {'gap%':>8} {'wall%':>7}")
        for ftol in ftols:
            for K in Ks:
                t, c = simulate(rows, ftol, K)
                gap = 100.0 * (c - full_c) / full_c
                print(f"{ftol:8.0e} {K:3d} {t:8.1f} {c:14.6e} {gap:8.3f} {100*t/full_t:7.1f}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/workspace/agent_rev/ftolref")
