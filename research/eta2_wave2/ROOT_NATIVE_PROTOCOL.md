# Native radius-fitting registration

The coherent fixed-state screen passed the predeclared entry gate: coupled
radius fitting increases true decrease on Final5 and Final6 and decreases it
on Final0. Frozen-tau fitting has the same directional pattern with smaller
gains. No claim of a universal improvement or exact camera-only TR solution.
Independent CPU verification of exported radius-fit directions is required
before the scored grid; if it fails, retain the row and stop this extension.

One new derived binary, all defaults off. Matched off, coupled radius fitting,
frozen-tau radius fitting, opening-only coupled radius fitting (first3 accepts).
Each active outer retains radius while re-solving. Trigger raw norm>2R, fit
[R/2,R] using safeguarded log secant toward0.75R; eight updates/outer maximum.
Re-solves start PCG from zero, preserve forcing history across the same state,
reuse only unchanged assembly, and rebuild changed point factors/RHS/preconditioner.
Frozen tau is captured at the start of each outer and retained through retries;
next outer uses the current camera lambda. No multishift candidate generation.
The present systems baseline is fresh PCG re-solves, not a free multishift claim.
Numeric recovery, true-cost checks, radius controller and stopping stay enabled.
Exhausted root searches use ordinary clipping and log fallback explicitly.

All root work is charged and logged separately from nonlinear rejection. Native
attempt telemetry from the first-stage binary remains enabled identically.
First Venice52 and Final3068 N5/arm at243740.27 and1744796.9841897595,
600outers/60native-seconds, full objective/independent endpoint audit. Both
directions and all arms retained. Nine practical cells N3/arm follow; extension
kill is >=5/9 slowdowns plus no hit-rate improvement, as in the supplied brief.
No averaging failed crossing times into successful-run times. No post-hoc
combination with static track damping or selecting flags by scene.

Later multishift root-finding, W5-native, W6-native and W8 are separate gates;
none are silently included in this arm.
