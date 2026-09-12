# Storage update for the retained pair/precision evidence

During the later static track-damping confirmation, the 122 individual
`endpoint.state.gz` containers in this study were verified byte-for-byte
against their members in the existing complete archive, then the duplicate
containers were removed to recover 382,175,761 bytes. The archive's SHA256
still matches `archive.json`; no unique numerical evidence was removed.

The original historical handoff's statement that all individual containers
remain present describes its publication time. Their current restoration
map is [storage-archive-dedup.json](../eta2_track_damping/storage-archive-dedup.json).
Each record gives the original file path, exact tar member, byte count and
SHA256 of the complete gzip container. Restore that member from the retained
archive to reproduce the original file exactly. Source, logs, result JSONs,
captured witness arrays and the complete archive remain in place.
