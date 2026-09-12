# B6v4: preparation pruning and fusion

## Verdict

The full preparation arm is the largest transparent throughput improvement in
wave 5, but it remains a research candidate pending a larger Final3068
distribution gate.  It is **6.73% faster** on the nine-cell practical panel
and **2.00% faster** on Muell, with identical work on stable cells.  Combined
with B6v2 dots, it is **7.78% faster** than off on the panel and **2.35%
faster** on Muell.

The arithmetic audit passed bit-for-bit for point factor plus solve, direct
equilibration, and fused RHS finalisation.  The fourth change removes a Schur
diagonal that classical LM immediately discarded.  That removal changes the
arrival order of the existing observation atomics, so it can sample a
different member of Eta2's ordinary trajectory distribution.

## Stable practical panel

All 108 rows hit their targets.  Median products, outers, and rejects were
identical in all nine cells.  Prep versus off was faster with disjoint ranges
on all nine cells; dots+prep versus dots was faster on seven and overlapping
on two.  Maximum median endpoint movement was 0.00175%, far below the 0.15%
gate.

| Comparison | Geometric-mean target-time ratio | Speed change |
|---|---:|---:|
| prep / off | 0.9327 | **6.73% faster** |
| dots+prep / dots | 0.9342 | **6.58% faster** |
| dots / off | 0.9871 | 1.29% faster |
| dots+prep / off | 0.9222 | **7.78% faster** |

## Profile and Muell

On Muell the preparation bucket fell from 0.242 s to 0.160 s (prep) and
0.161 s (dots+prep), a **33–34% reduction**.  Assembly, Krylov, and candidate
times stayed flat.  The independent target-time cohort retained exactly 980
products and 3/3 hits in every arm:

| Comparison | Median target time | Ratio | Range relation |
|---|---:|---:|---|
| off → prep | 4.2183 → 4.1340 s | 0.9800 | disjoint |
| dots → dots+prep | 4.2070 → 4.1193 s | 0.9792 | disjoint |
| off → dots+prep | 4.2183 → 4.1193 s | 0.9765 | disjoint |

The measured saving matches the implementation mechanism.  In the frozen
classical-LM path, `MFRhsDiagFused` computed nine triangular solves and nine
diagonal atomics per observation; the next operation zeroed the result and
replaced it with `diag(H_cc)`.  Omitting that dead calculation provides most
of the gain.

## Initial N=10 tail gate

Final3068 sampled its known basin lottery: off 9/10, prep 6/10, dots 5/10,
dots+prep 7/10.  The ordering is internally contradictory: the arithmetic-
identical dots arm appears four hits below off, while adding prep appears two
hits above dots.  No pairwise difference is resolved by N=10.  Venice remained
0/10 in all arms; median endpoint changes were -0.009% for prep/off and
-0.253% for dots+prep/dots, inside its observed multimodal spread.

Because the protocol requires no tail reliability loss, the N=10 result is
not used to promote the pruning arm.  A preregistered extension pools the
arithmetic-identical controls from B6v4 and B6v5 and adds 20 active runs per
pruning arm.

## Durable finding

The original broad fusion suggestion was partly obsolete: the champion
already fused RHS and diagonal construction.  The useful optimization was
found by following the value's lifetime and proving that half of that fused
kernel's output was dead under classical LM.  This is a concrete example of
why a named “fused kernel” is not evidence that its work is needed.
