# Eta2 wave 3 — verdict and handoff

**Keep frozen Eta2 as the general champion.** Completed 513 scored native runs
and 12 separate diagnostic captures. No tested camera-local actuator earned
promotion. Full evidence and qualifications: [AGENT_FEEDBACK.md](AGENT_FEEDBACK.md).

| Experiment | Result | Decision |
|---|---|---|
| E1 starvation audit | Final3068 has a 13-observation exceptional camera; Venice has a weak f/t_z mode in a camera with 2,959 observations. | Low counts alone miss geometric weakness. |
| E2 cap30 | Venice 0/5, Final3068 0/5; fresh off Final3068 4/5. | Reject the tested standalone rule. |
| E2 block/global spectral floors | Even weakest settings touch >=15.40% / >=14.29% on calm Ladybug539. | Killed at the 5% locality pre-test; no native spectral-solver claim. |
| E3 intrinsic gating | Venice 0/5, Final3068 0/5; projected-solve audit passes. | Reject the tested gate. |
| E3 shorter/looser opening | Only the existing eta0.05, three-accept policy reaches Venice without caps. | No cheaper opening found. |
| E3 cap/opening interaction | Four variants get Venice 4–5/5; every one gets Final3068 0/5 and is 12.9–31.8% slower on the practical panel. | No general candidate. |
| Existing opening, fresh confirmation | Venice 5/5 at median 0.3129 s versus off 0/5; practical time/control 1.00792. Final3068 1/5 versus off 4/5. | Passes narrow Venice/time gate; retain as an option, not a universal default. |
| E4 trajectory split | One two-observation point contributes 1,538.21 of a 1,549.40 post-step cost gap before the first large camera-direction difference. | Point approaches a projection horizon; camera-only explanation is insufficient. |
| E5 local feedback | No standalone actuator passes its Venice entry gate. | Not run; not refuted. |

The successful Venice opening rejection is **not** dominated by the weak tail
camera: its top five cameras carry only 26.6% of squared step norm, and the
leading camera is well observed and spectrally ordinary.

The opening's Final3068 evidence is mixed across fresh cohorts: opening/off
5/5 vs 4/5, then 4/5 vs 3/5, then 1/5 vs 4/5. Keep these separate; N=5 is not
a precise probability estimate. The practical panel is nine tolerance cells
on **three scenes**, not nine independent scenes. Confirmation has four faster,
three slower and two overlapping timing ranges; individual losses reach 32%.

The main reusable finding is a distinction between **late weak-camera norms,
distributed opening rejection, and thin-track horizon sensitivity**. The next
useful causal test is a controlled one-track replay at the preserved E4 state.
The current cost-swap diagnostic does not prove that this rescues the basin.

Sources, registrations, positive and negative rows, and checks are indexed by
[NUMBERS.md](NUMBERS.md), [metrics.csv](metrics.csv),
[REPRODUCING.md](REPRODUCING.md) and [release_audit.json](release_audit.json).
No original defaults were overwritten; no new Caspar comparison was run here.
