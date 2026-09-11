# Verified evidence archive

The completed study at commit `2228606` is sealed in:

`/workspace/collab/results/eta2_external_coverage_20260911T162315Z.tar.gz`

- SHA256: `f24599ef6da21a167121773ad0c24ab84f341796fe8258f8e5edcd7ccc659cc7`
- Size: 535,975,108 bytes.
- Contents: 591 files plus the embedded `ARCHIVE_MANIFEST.json`.
- Every archived file was read back and checked against its individual hash.

The archive includes the 61 losslessly compressed endpoint states, native
logs and curves, protocols, checked result tables, plots, frozen Eta2 source
and headers, and four native binaries (Eta2, original Ceres, Caspar32, and
the separate Ceres setup driver). BAL inputs are referenced by their hashes;
they are not duplicated. External runtime libraries remain necessary.

Matching `.sha256` and `.manifest.json` files sit beside the archive. The
Git branch contains source, tables, and raw textual evidence; large states
and native executables are in this archive. This pointer was added after
sealing, so it does not change the archived commit or its recorded hashes.
