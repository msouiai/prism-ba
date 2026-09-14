# B6v7 phase profile

The archived B6v7 binary SHA `b6462682592916fa5cd9ee506bf2b24cb1bfbc10ed8dcb5fb3f0db05bcef198a` was run with the champion configuration plus the hashed B6v7 overlay, fixed to three outer iterations as preregistered. Final13682 fit on the 16 GB RTX 2000 Ada, so no feasibility fallback was used. Every endpoint was independently rescored in FP64; maximum native/audit relative disagreement was `2.44e-15` on Muell and `1.78e-14` on Final13682.

| scene | unprofiled process wall median, N=3 | returned solve median, N=3 | assembly | point factor + RHS | Krylov | candidates | unclassified solve |
|---|---:|---:|---:|---:|---:|---:|---:|
| Muell-gba146 | 1.7727 s | 0.2280 s | 63.0% | 6.2% | 6.2% | 3.5% | 21.1% |
| Final13682 | 20.1855 s | 2.2517 s | 38.7% | 10.3% | 29.2% | 6.3% | 15.5% |

The process wall includes BAL parsing and setup before the returned `Solve` timer. That cold path dominates these short three-outer calls (about 87% on Muell and 89% on Final13682), so input/setup is the first cold-workload ceiling. Inside the solver, assembly is the largest measured phase on both scenes; Final13682 also spends a substantial 29% in Krylov. A single kernel optimization cannot address the scene-dependent balance. Profiled runs provide attribution only; timing medians use the three unprofiled runs and are not time-to-target measurements.
