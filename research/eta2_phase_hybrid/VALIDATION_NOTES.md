# Validation notes

The initial shifted recurrence failed the tight SPD-63 synthetic check at depth
125 because forming z*z_previous underflowed for a highly damped lane while the
seed still needed work. Before any native candidate measurements, algebraically
cancel z_previous from the denominator and compute the multiplier directly.
Freeze a lane only once |z|<1e-150; still audit its true residual at exit. All
nine fixed-system checks then pass, including three materialized BA Schur
operators. This is numerical maintenance of the known recurrence, not a novelty
claim. The all-zero bare operator check also exhibits raw diversity .9999 but
clipped diversity ~3.2e-8 (exact value zero); radius projection can erase the
menu's apparent amplitude diversity. Gram subtraction noise is far below the
registered 1e-3 collapse threshold in this test.

Before the native screen, compare original/generated mode-off N=3 at eight
outers on the three small scenes: require matching median accept/reject/product
counts and <1e-4 relative difference of median cost. This tolerates the measured
atomic-order variability from the prior campaign; it is not bitwise parity.
