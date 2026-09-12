# D0 runner amendment

The first `run` invocation stopped before any solver process was launched.
`native_light.run` computes evidence paths relative to its module-level
`HERE`, which still pointed at `research/eta2_wave5`; the requested wave-6
evidence path therefore raised `ValueError` during manifest construction.

The runner now sets `native_light.HERE` to the wave-6 directory immediately
after import.  Binary, flags, inputs, repetitions, metrics and gates are
unchanged.  No scored row existed before this amendment.
