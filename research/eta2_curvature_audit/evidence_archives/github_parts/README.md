# Curvature audit evidence archive parts

These files preserve the three compressed XOR capture archives in chunks below GitHub’s 100 MB object limit.

Reconstruct from the repository root:

```bash
cat research/eta2_curvature_audit/evidence_archives/github_parts/capture-0.xor.tar.xz.part-* > research/eta2_curvature_audit/evidence_archives/capture-0.xor.tar.xz
cat research/eta2_curvature_audit/evidence_archives/github_parts/capture-1.xor.tar.xz.part-* > research/eta2_curvature_audit/evidence_archives/capture-1.xor.tar.xz
cat research/eta2_curvature_audit/evidence_archives/github_parts/capture-2.xor.tar.xz.part-* > research/eta2_curvature_audit/evidence_archives/capture-2.xor.tar.xz
sha256sum -c research/eta2_curvature_audit/evidence_archives/github_parts/SHA256SUMS.archives
```
