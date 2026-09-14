# B6v7 phase profile

The archived B6v7 binary SHA `b6462682592916fa5cd9ee506bf2b24cb1bfbc10ed8dcb5fb3f0db05bcef198a` was run with the champion configuration plus the hashed B6v7 overlay, fixed to three outer iterations as preregistered. Final13682 fit on the 16 GB RTX 2000 Ada, so no feasibility fallback was used. Every endpoint was independently rescored in FP64; maximum native/audit relative disagreement was `2.44e-15` on Muell and `1.78e-14` on Final13682.

| scene | unprofiled process wall median, N=3 | returned solve median, N=3 | assembly | point factor + RHS | Krylov | candidates | unclassified solve |
|---|---:|---:|---:|---:|---:|---:|---:|
| Muell-gba146 | 1.7727 s | 0.2280 s | 63.0% | 6.2% | 6.2% | 3.5% | 21.2% |
| Final13682 | 20.1855 s | 2.2517 s | 38.7% | 10.3% | 29.2% | 6.2% | 15.6% |

The process wall outside the returned `Solve` timer includes BAL parsing, startup, state output, and teardown; these were not timed separately. Together they dominate these short three-outer calls (87.1% on Muell and 88.8% on Final13682), identifying outside-Solve work as the first cold-workload measurement target without attributing it solely to parsing. Inside the one profiled returned solve, assembly is the largest measured phase on both scenes; Final13682 also spends 29.2% in Krylov. The phase clocks are logged to 1 ms. These fixed three-outer shares do not establish full target-run bottlenecks. Profiled runs provide attribution only; timing medians use the three unprofiled runs and are not time-to-target measurements.
