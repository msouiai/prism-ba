# D9 preflight amendment

The first active preflight exited at startup and produced no solver score.  Its
guard rejected the CLI's default `use_alpha=true`, although the frozen
classical-LM path makes alpha search inert unless `OCA_ALPHA_RHO` is present.
Version 2 checks that actual activation flag instead.  No formula, scale,
opening duration, dataset, target, gate, or comparison rule changed.  The old
registration and failed preflight are retained; all valid evidence uses the
`d9v2-*` prefix and a freshly built binary plus repeated flag-off screen.
