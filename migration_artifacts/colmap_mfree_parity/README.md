# COLMAP MFREE parity integration snapshot

This directory preserves the exact modified/new COLMAP integration files used with Prism branch `mfree-parity`. The source checkout was detached at upstream COLMAP commit `711b23a7994f9a6b31bf88245b412838370f29c7`.

- `source_snapshot/` contains every modified or untracked source file at capture time.
- `tracked_changes.patch` is the binary-safe diff for tracked upstream files.
- `manifest.json` records paths, statuses, sizes, and SHA-256 hashes.

The Prism CUDA solver itself lives on branch `mfree-parity`; this snapshot is the COLMAP adapter/build layer needed to reconstruct `/workspace/colmap-mfree-parity` without depending on that local checkout.
