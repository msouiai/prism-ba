# Pair restoration and probe precision

This isolated derivative keeps the frozen Eta2 source and binary unchanged.
The protocol was committed as `62a756b` before implementation/measurements.
Read `PROTOCOL.md` for targets, interventions, repetition counts and gates.

`build.py` verifies the frozen source/headers and the previous depth-probe
source, then generates a new CUDA translation unit. The new flags are
`OCA_DEPTH_PAIR=1` (requires `OCA_DEPTH_STOP=1`) and `OCA_DEPTH_FP64=1`
(requires a stopping or de-clipping probe). Both default off. FP64 cross
blocks are allocated lazily and used only during a probe, including RHS
and point back-substitution. The original point factors remain unchanged.
This is a local repair of the previously measured cross-rounding defect,
not a guarantee that every mixed point-factor system is positive definite.

```sh
python3 research/eta2_pair_precision/build.py
python3 research/eta2_pair_precision/run.py compatibility
python3 research/eta2_pair_precision/run.py final
python3 research/eta2_pair_precision/run.py venice
python3 research/eta2_pair_precision/run.py screen
python3 research/eta2_pair_precision/analyze.py
```

`run.py` uses a lock for serial measurements, scrubs unrelated solver flags,
rotates arm order, hashes binaries/inputs, and independently scores every
exported endpoint in CPU FP64. Native target crossing times include all
probe overhead. Each original stopping state remains a within-run witness;
fresh trajectories that finish before a probe are not credited as rescues.
The optional `combo` stage requires both registered primary gates to pass.

The external-state audit requires NumPy/SciPy and uses a separate diagnostic
binary. It captures the initial linearization of each supplied BAL snapshot
without accepting an optimization step. `external.py` verifies all 18
input hashes, exact observation correspondence and zero k2, then builds
the 468-dimensional Schur matrices at common lambda=tau=1e-8. Its matrix
products are checked against captured native products. The mixed minimum
eigenvector is evaluated independently in extended precision under each
operator. These are diagnostic timings, never solver benchmark times.

```sh
python3 research/eta2_pair_precision/build_external.py
python3 research/eta2_pair_precision/external.py --phase opening
python3 research/eta2_pair_precision/external.py --phase tail
```

Dense matrices/eigenvectors, native product diagnostics, metadata, hashes
and the first complete raw operator capture are retained. Other raw operator
arrays are transient and removed only after their dense audit is validated,
as registered to keep storage bounded. All optimizer endpoint states are
retained losslessly compressed. Build/protocol/binary provenance is explicit.
