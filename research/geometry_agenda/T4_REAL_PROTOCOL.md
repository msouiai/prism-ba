# T4 sampled-real transfer registration

Conditional on synthetic automatic-partition success. Three unchanged T1
initial parent states: Ladybug49, Dubrovnik88, Venice52. Construct a small,
explicit diagnostic subproblem from each: select up to 24 cameras greedily by
shared-track connectivity starting at camera0, then sample up to 300 points
with at least three selected views, using RNG seed51. Exclude an entire point
from the diagnostic sample if any of its selected views has nonnegative depth
or nonfinite projection initially. Retain every selected observation of each
sampled point. Save the exact indices and packed inputs. This is a new sampled
fixed-intrinsics problem, not a benchmark claim about the full BAL scene or
native 9-DOF Eta2/Caspar.

Before comparative runs, compute a feasible reference with ordinary six-DOF LM,
120 attempts/3 seconds, and freeze `Fref+1e-3*(F0-Fref)`. Report any reference
stall and the actual reference; do not call it the optimum. Then compare fine,
automatic linear and automatic nonlinear (v2 confidence ownership), N=3,
rotated order, same total 2-second cap and eight coarse steps. Include all
partition/coarse work. Record final/target cost, target hits, trace, retries,
depth validity and any instability. No truth geometry exists for these samples.
Keep synthetic and sampled-real claims separate; no production promotion from
a single passing sample. Failed real transfer closes T4 as a conditional
synthetic mechanism, with native transfer unproven.
