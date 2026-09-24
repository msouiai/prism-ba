# Muell GBA146: Caspar extension

The target was frozen before this Caspar extension: `1946488.746262194`.
Each run used Caspar’s default COLMAP-equivalent driver profile, a 90 s solver-only cap,
and a `1e-8` inward native threshold. A target result requires both a native crossing and
an independent original-observation FP64 endpoint audit at or below the frozen target.

| solver | certified hits | target seconds, median [min,max] | audited final cost, median [min,max] | iterations, median | rejects, median |
|---|---:|---:|---:|---:|---:|
| caspar32 | 0/3 | — | 1961895.563 [1961455.361, 1962014.747] | 1655 [1589, 1655] | 682 [655, 695] |
| caspar64 | 0/3 | — | 1962982.125 [1962495.546, 1963246.326] | 568 [567, 568] | 0 [0, 0] |

Per-run records, raw Caspar logs, command manifests, and exported-state checksums are in `runs/`.

The N=3 convergence figure, including Prism's matched controls and champion, is in `figures/muell_gba146_prism_caspar_convergence.png` (with SVG and plotting metadata alongside it).
