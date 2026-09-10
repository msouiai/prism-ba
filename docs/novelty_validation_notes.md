# Validation notes retained during the frozen study

## Nonfinite shifted recurrences

The original fixed-system audit produced a nonfinite high-shift solution on
Ladybug-1197 at outer 5, at both requested tolerances. Final-3068 outer 5 also
produced a nonfinite high-shift solution and did not meet the seed residual
target within 2,048 iterations. These are failed accuracy comparisons, not
valid speedups. Earlier progress output accidentally admitted Ladybug's
1e-4 cell because Python `max` can ignore a later NaN. The report now requires
every residual to be finite and below the stated limit, and serializes
nonfinite residuals as JSON null with `valid=false`. Original logs remain.

The diagnostic keeps updating every shifted recurrence until the seed stops.
The recurrence divides by the previous zeta; strongly damped systems can
converge long before the seed, so continuing their updates risks underflow
and division by zero. The production source also divides by zeta without a
zero-denominator guard at that operation. The present evidence demonstrates
a diagnostic failure at long sweeps; it does not establish how often the
frozen nonlinear production runs encounter the same condition.

A follow-up remedy is to retire a shift after checking its true residual,
preserving its current solution and ceasing zeta updates. Recurrence residual
estimates alone can drift. Count any verification matvecs and recheck all
final true residuals. This would be a separate, labeled experiment; the
current frozen four-arm data must not be replaced with a changed solver.

## Diagnostic-off regression comparison

A first three-outer Ladybug-49 comparison between the original executable
and the audit-enabled executable with the diagnostic disabled failed a
1e-8 relative endpoint identity check: costs 21380.1551946112 and
21380.1138907071 (relative difference about 1.93e-6). Both used three accepted
steps, zero rejections, 143 matvecs and 59 scored candidates. Stripping the
audit include and hook from its compiled source exactly reproduces the
original source SHA. Additional alternating original/audit repetitions and
CUDA memcheck are running; this note does not yet attribute the discrepancy
to nondeterminism or claim numerical identity.

All nonlinear study arms use the original frozen executable, so this
regression discrepancy does not mix implementations across those arms.

## Objective verification scope

Caspar-fp32 and Ceres final states are reevaluated using CPU double arithmetic
and the original double observations. Prism's frozen executable supplies
GPU double endpoint costs and accepted traces; its initial cost is checked
independently, but its final states are not exported and separately checked
on the CPU in the present protocol. Reports distinguish these checks.

## Build isolation

The current source builds successfully with `OCA_KRYLOV_AUDIT_BUILD=OFF` and
`ON` in separate directories. The audit snapshot literal is absent from the
normal binary and present in the enabled binary. The opt-in definition is
attached to the standalone CLI only, never to `oca_core`. Binary hashes and
this check are recorded in `audit-build-validation.json` under the study
root. These validation builds do not replace any frozen experiment binary.
