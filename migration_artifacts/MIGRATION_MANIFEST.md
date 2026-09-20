# Machine migration manifest

Generated 2026-09-20 before migrating the Prism BA research machine.

## GitHub preservation branches

- `archive/machine-migration-20260920` — exact legacy working tree, research scripts, reports, plots, collaboration material, and standalone multishift reproduction package.
- `research/eta2-wave6-categorical` — latest Eta2 research line plus checksummed curvature-audit capture archives.
- `research/eta2-champion-publish` — frozen Eta2 champion.
- `research/linear-edge-clean-v2` — clean promotable linear-edge correction.
- `research/agent-audit-consolidation`, `research/agent-audit-integration`, and `research/assembly-context-cycle` — final agent audits and prototypes.
- Earlier wave, experiment, Schur, and adaptive-menu branches remain on origin.

## Included under migration_artifacts

- Collaboration mail, protocols, compact results, Muell/Caspar traces, and the Venice-52 audit-state archive.
- Claude’s standalone multishift reproduction source, binaries, scripts, and run logs.

## External data requiring separate transfer

BAL inputs, the Fuchsberg source archive, large collaboration evidence archives, and preserved raw-evidence archives are intentionally outside Git. Their SHA-256 hashes are in `migration_artifacts/EXTERNAL_SHA256SUMS`.

Generated endpoint `.state`, matrix-capture files, build trees, package caches, and duplicate expanded archives are reproducible scratch data and are not migration requirements.
