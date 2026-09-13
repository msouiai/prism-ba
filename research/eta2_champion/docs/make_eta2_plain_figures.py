#!/usr/bin/env python3
"""Generate the explanatory figure used by eta2_plain_language.tex."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


HERE = Path(__file__).resolve().parent
OUT = HERE / "figures" / "explanatory" / "directional_curvature.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)

plt.rcParams.update(
    {
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "legend.fontsize": 8,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    }
)

fig, axes = plt.subplots(1, 2, figsize=(9.1, 3.25), constrained_layout=True)

# Left: isolate the second-order term so that the sign of p^T A p is visible.
ax = axes[0]
alpha = np.linspace(-1.35, 1.35, 400)
for q, color, label in [
    (1.0, "#2474b5", r"$q>0$: upward bowl"),
    (0.06, "#d18b00", r"$q\approx0$: almost flat"),
    (-0.35, "#b33a3a", r"$q<0$: bends downward"),
]:
    ax.plot(alpha, 0.5 * q * alpha**2, lw=2.3, color=color, label=label)
ax.axhline(0, color="#777777", lw=0.7)
ax.axvline(0, color="#777777", lw=0.7)
ax.set_xlabel(r"distance $\alpha$ along the current PCG direction $p$")
ax.set_ylabel(r"second-order term $\frac{1}{2}\alpha^2p^TAp$")
ax.set_title("What the sign of directional curvature means")
ax.legend(frameon=False, loc="upper center")
ax.spines[["top", "right"]].set_visible(False)

# Right: distinguish the inner curvature guard from the outer gain-ratio test.
ax = axes[1]
ax.set_axis_off()
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)


def box(x, y, w, h, text, color):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.018,rounding_size=0.025",
        linewidth=1.3,
        edgecolor=color,
        facecolor=color + "18",
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color="#202020")


box(0.05, 0.72, 0.90, 0.17, "Inside PCG:  q = (pᵀAp)/(pᵀp)\nIs the numerical quadratic safe along p?", "#2474b5")
box(0.05, 0.39, 0.90, 0.17, "After a full camera + point proposal:  ρ = actual / predicted decrease\nDid the nonlinear image error behave like the model?", "#218c63")
box(0.05, 0.06, 0.90, 0.17, "Only an accepted ρ-test changes the BA state\nA curvature repair merely rebuilds the linear solve", "#7c4d9e")
for y0, y1 in [(0.72, 0.56), (0.39, 0.23)]:
    ax.add_patch(
        FancyArrowPatch(
            (0.5, y0),
            (0.5, y1 + 0.01),
            arrowstyle="-|>",
            mutation_scale=12,
            lw=1.1,
            color="#555555",
        )
    )
ax.set_title("Two different checks, at two different stages", pad=9)

fig.savefig(OUT, bbox_inches="tight")
print(OUT)
