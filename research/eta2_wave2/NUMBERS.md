# Wave-2 numerical ledger

Generated from the retained result files. All native endpoints were independently rescored on the original full objective. Different stages use fresh cohorts; do not pool their control hit counts.


## venice

| Cell | Arm | Hits | Median final cost | Hit time s | Hit range s | Outers | Rejects | PCG/outer | Retry wall % |
|---|---|---|---|---|---|---|---|---|---|
| venice-52 | accurate_reference | 5/5 | 243382.00 | 0.3754 | 0.3741–0.3755 | 21.0 | 1.0 | 6.52 | 6.61 |
| venice-52 | forcing | 0/5 | 249659.19 | — | — | 181.0 | 1.0 | 2.26 | 1.43 |
| venice-52 | forcing_reject | 5/5 | 243382.00 | 0.3130 | 0.3121–0.3134 | 21.0 | 1.0 | 6.52 | 2.95 |
| venice-52 | jump16 | 0/5 | 248591.68 | — | — | 296.0 | 4.0 | 2.26 | 1.29 |
| venice-52 | lambda1 | 0/5 | 245108.89 | — | — | 100.0 | 1.0 | 2.73 | 1.26 |
| venice-52 | lambda10 | 0/5 | 245626.99 | — | — | 83.0 | 0.0 | 1.43 | 0.00 |
| venice-52 | lambda100 | 2/5 | 244030.99 | 0.6208 | 0.6055–0.6361 | 60.0 | 4.0 | 2.63 | 3.74 |
| venice-52 | no_interior | 0/5 | 257571.53 | — | — | 600.0 | 0.0 | 2.10 | 0.00 |
| venice-52 | off | 0/5 | 246317.04 | — | — | 158.0 | 7.0 | 2.06 | 2.93 |
| venice-52 | opening_no_interior | 0/5 | 251228.62 | — | — | 152.0 | 12.0 | 1.82 | 4.48 |


## final

| Cell | Arm | Hits | Median final cost | Hit time s | Hit range s | Outers | Rejects | PCG/outer | Retry wall % |
|---|---|---|---|---|---|---|---|---|---|
| final-3068 | accurate_reference | 3/5 | 1741686.10 | 3.1306 | 3.0970–4.5347 | 59.0 | 8.0 | 3.10 | 7.10 |
| final-3068 | forcing_reject | 4/5 | 1741644.81 | 4.3617 | 2.9874–5.3272 | 69.0 | 6.0 | 2.93 | 5.18 |
| final-3068 | off | 4/5 | 1740991.21 | 2.6833 | 1.5434–3.7925 | 47.0 | 3.0 | 4.36 | 5.27 |


## root-tail

| Cell | Arm | Hits | Median final cost | Hit time s | Hit range s | Outers | Rejects | PCG/outer | Retry wall % |
|---|---|---|---|---|---|---|---|---|---|
| final-3068 | coupled | 0/5 | 1846337.41 | — | — | 53.0 | 12.0 | 6.98 | 43.41 |
| final-3068 | frozen | 1/5 | 1794371.52 | 4.4302 | 4.4302–4.4302 | 56.0 | 11.0 | 9.15 | 36.62 |
| final-3068 | off | 2/5 | 1750956.68 | 3.7856 | 3.4829–4.0884 | 60.0 | 11.0 | 3.76 | 11.64 |
| final-3068 | opening | 2/5 | 1755665.92 | 5.2827 | 4.3128–6.2525 | 76.0 | 14.0 | 3.38 | 9.55 |
| venice-52 | coupled | 0/5 | 246496.55 | — | — | 91.0 | 2.0 | 12.23 | 36.87 |
| venice-52 | frozen | 0/5 | 252196.67 | — | — | 93.0 | 3.0 | 10.60 | 27.82 |
| venice-52 | off | 0/5 | 246433.85 | — | — | 128.0 | 1.0 | 1.78 | 1.59 |
| venice-52 | opening | 0/5 | 247567.51 | — | — | 127.0 | 7.0 | 1.68 | 3.14 |


## geodesic-tail

| Cell | Arm | Hits | Median final cost | Hit time s | Hit range s | Outers | Rejects | PCG/outer | Retry wall % |
|---|---|---|---|---|---|---|---|---|---|
| final-3068 | geodesic | 3/5 | 1743690.66 | 4.6313 | 3.7215–5.3697 | 62.0 | 9.0 | 9.32 | 14.85 |
| final-3068 | off | 4/5 | 1742681.44 | 4.1414 | 2.6056–5.0594 | 72.0 | 6.0 | 3.36 | 8.31 |
| venice-52 | geodesic | 0/5 | 253431.23 | — | — | 193.0 | 6.0 | 3.24 | 2.44 |
| venice-52 | off | 0/5 | 247549.61 | — | — | 128.0 | 7.0 | 1.68 | 3.18 |


## plateau-tail

| Cell | Arm | Hits | Median final cost | Hit time s | Hit range s | Outers | Rejects | PCG/outer | Retry wall % |
|---|---|---|---|---|---|---|---|---|---|
| final-3068 | off | 3/5 | 1744308.03 | 5.2429 | 2.6121–6.0087 | 72.0 | 12.0 | 2.82 | 8.99 |
| final-3068 | plateau | 3/5 | 1743826.84 | 3.5640 | 3.0075–4.0329 | 65.0 | 7.0 | 3.38 | 7.22 |
| venice-52 | off | 0/5 | 246316.71 | — | — | 131.0 | 5.0 | 2.22 | 1.81 |
| venice-52 | plateau | 0/5 | 246328.16 | — | — | 109.0 | 5.0 | 3.61 | 2.17 |


## plateau-extra

| Cell | Arm | Hits | Median final cost | Hit time s | Hit range s | Outers | Rejects | PCG/outer | Retry wall % |
|---|---|---|---|---|---|---|---|---|---|
| final-3068 | plateau | 10/13 | 1743494.91 | 3.9335 | 2.6847–5.5124 | 67.0 | 6.0 | 4.18 | 5.72 |


## All nine practical cells

Every cell has N3 per arm. Time ratios below1 favor the intervention. All target crossings, including regressions, are retained.


### practical / accurate_reference

Geometric mean time ratio **1.4942**; 0 disjoint faster, 7 disjoint slower, 2 overlapping.

| Cell | Control median s [range] | Variant median s [range] | Time ratio | Observed ranges |
|---|---|---|---|---|
| final-394-1.005 | 0.2450 [0.2450, 0.2450] | 0.3582 [0.3507, 0.3630] | 1.4620 | slower |
| final-394-1.01 | 0.1743 [0.1742, 0.1746] | 0.3418 [0.3148, 0.3613] | 1.9610 | slower |
| final-394-1.02 | 0.1303 [0.1301, 0.1305] | 0.2989 [0.2620, 0.3240] | 2.2939 | slower |
| ladybug-539-1.005 | 0.0907 [0.0906, 0.0908] | 0.1295 [0.1287, 0.1458] | 1.4278 | slower |
| ladybug-539-1.01 | 0.0624 [0.0624, 0.0625] | 0.1286 [0.1283, 0.1413] | 2.0609 | slower |
| ladybug-539-1.02 | 0.0621 [0.0620, 0.0622] | 0.1089 [0.1001, 0.1091] | 1.7536 | slower |
| trafalgar-138-1.005 | 0.2955 [0.2953, 0.2960] | 0.2763 [0.2734, 0.2985] | 0.9350 | overlap |
| trafalgar-138-1.01 | 0.2316 [0.2315, 0.2318] | 0.2265 [0.2122, 0.2342] | 0.9780 | overlap |
| trafalgar-138-1.02 | 0.1277 [0.1277, 0.1280] | 0.1528 [0.1527, 0.1528] | 1.1966 | slower |


### practical / forcing_reject

Geometric mean time ratio **1.0285**; 4 disjoint faster, 4 disjoint slower, 1 overlapping.

| Cell | Control median s [range] | Variant median s [range] | Time ratio | Observed ranges |
|---|---|---|---|---|
| final-394-1.005 | 0.2450 [0.2450, 0.2450] | 0.2554 [0.2246, 0.2567] | 1.0424 | overlap |
| final-394-1.01 | 0.1743 [0.1742, 0.1746] | 0.2189 [0.2133, 0.2193] | 1.2559 | slower |
| final-394-1.02 | 0.1303 [0.1301, 0.1305] | 0.1659 [0.1653, 0.1781] | 1.2732 | slower |
| ladybug-539-1.005 | 0.0907 [0.0906, 0.0908] | 0.0994 [0.0992, 0.1104] | 1.0959 | slower |
| ladybug-539-1.01 | 0.0624 [0.0624, 0.0625] | 0.0821 [0.0820, 0.0913] | 1.3157 | slower |
| ladybug-539-1.02 | 0.0621 [0.0620, 0.0622] | 0.0518 [0.0517, 0.0519] | 0.8341 | faster |
| trafalgar-138-1.005 | 0.2955 [0.2953, 0.2960] | 0.2453 [0.2452, 0.2457] | 0.8301 | faster |
| trafalgar-138-1.01 | 0.2316 [0.2315, 0.2318] | 0.1840 [0.1838, 0.1845] | 0.7945 | faster |
| trafalgar-138-1.02 | 0.1277 [0.1277, 0.1280] | 0.1244 [0.1242, 0.1244] | 0.9742 | faster |


### root-practical / coupled

Geometric mean time ratio **1.1808**; 0 disjoint faster, 2 disjoint slower, 7 overlapping.

| Cell | Control median s [range] | Variant median s [range] | Time ratio | Observed ranges |
|---|---|---|---|---|
| final-394-1.005 | 0.2454 [0.2451, 0.2458] | 0.2450 [0.2448, 0.2453] | 0.9984 | overlap |
| final-394-1.01 | 0.1745 [0.1743, 0.1745] | 0.1745 [0.1744, 0.1749] | 1.0000 | overlap |
| final-394-1.02 | 0.1302 [0.1302, 0.1302] | 0.1303 [0.1300, 0.1304] | 1.0008 | overlap |
| ladybug-539-1.005 | 0.0907 [0.0904, 0.0909] | 0.0908 [0.0905, 0.0909] | 1.0011 | overlap |
| ladybug-539-1.01 | 0.0651 [0.0620, 0.0686] | 0.0652 [0.0621, 0.0689] | 1.0015 | overlap |
| ladybug-539-1.02 | 0.0662 [0.0621, 0.0687] | 0.0688 [0.0684, 0.0689] | 1.0393 | overlap |
| trafalgar-138-1.005 | 0.3139 [0.2956, 0.3209] | 0.5884 [0.5879, 0.9894] | 1.8745 | slower |
| trafalgar-138-1.01 | 0.2320 [0.2318, 0.2322] | 0.5308 [0.4551, 0.5318] | 2.2879 | slower |
| trafalgar-138-1.02 | 0.1278 [0.1277, 0.1281] | 0.1277 [0.1277, 0.1278] | 0.9992 | overlap |


### root-practical / frozen

Geometric mean time ratio **1.2121**; 0 disjoint faster, 2 disjoint slower, 7 overlapping.

| Cell | Control median s [range] | Variant median s [range] | Time ratio | Observed ranges |
|---|---|---|---|---|
| final-394-1.005 | 0.2454 [0.2451, 0.2458] | 0.2451 [0.2450, 0.2453] | 0.9988 | overlap |
| final-394-1.01 | 0.1745 [0.1743, 0.1745] | 0.1744 [0.1741, 0.1745] | 0.9994 | overlap |
| final-394-1.02 | 0.1302 [0.1302, 0.1302] | 0.1302 [0.1301, 0.1304] | 1.0000 | overlap |
| ladybug-539-1.005 | 0.0907 [0.0904, 0.0909] | 0.0908 [0.0906, 0.0925] | 1.0011 | overlap |
| ladybug-539-1.01 | 0.0651 [0.0620, 0.0686] | 0.0686 [0.0657, 0.0690] | 1.0538 | overlap |
| ladybug-539-1.02 | 0.0662 [0.0621, 0.0687] | 0.0686 [0.0620, 0.0688] | 1.0363 | overlap |
| trafalgar-138-1.005 | 0.3139 [0.2956, 0.3209] | 0.7613 [0.7609, 0.7623] | 2.4253 | slower |
| trafalgar-138-1.01 | 0.2320 [0.2318, 0.2322] | 0.4950 [0.4943, 0.5789] | 2.1336 | slower |
| trafalgar-138-1.02 | 0.1278 [0.1277, 0.1281] | 0.1278 [0.1277, 0.1281] | 1.0000 | overlap |


### root-practical / opening

Geometric mean time ratio **0.9993**; 0 disjoint faster, 0 disjoint slower, 9 overlapping.

| Cell | Control median s [range] | Variant median s [range] | Time ratio | Observed ranges |
|---|---|---|---|---|
| final-394-1.005 | 0.2454 [0.2451, 0.2458] | 0.2452 [0.2447, 0.2452] | 0.9992 | overlap |
| final-394-1.01 | 0.1745 [0.1743, 0.1745] | 0.1743 [0.1743, 0.1745] | 0.9989 | overlap |
| final-394-1.02 | 0.1302 [0.1302, 0.1302] | 0.1301 [0.1300, 0.1302] | 0.9992 | overlap |
| ladybug-539-1.005 | 0.0907 [0.0904, 0.0909] | 0.0912 [0.0906, 0.1004] | 1.0055 | overlap |
| ladybug-539-1.01 | 0.0651 [0.0620, 0.0686] | 0.0661 [0.0661, 0.0761] | 1.0154 | overlap |
| ladybug-539-1.02 | 0.0662 [0.0621, 0.0687] | 0.0687 [0.0621, 0.0688] | 1.0378 | overlap |
| trafalgar-138-1.005 | 0.3139 [0.2956, 0.3209] | 0.2957 [0.2953, 0.2958] | 0.9420 | overlap |
| trafalgar-138-1.01 | 0.2320 [0.2318, 0.2322] | 0.2319 [0.2313, 0.2320] | 0.9996 | overlap |
| trafalgar-138-1.02 | 0.1278 [0.1277, 0.1281] | 0.1277 [0.1277, 0.1280] | 0.9992 | overlap |


### geodesic-practical / geodesic

Geometric mean time ratio **1.1195**; 3 disjoint faster, 6 disjoint slower, 0 overlapping.

| Cell | Control median s [range] | Variant median s [range] | Time ratio | Observed ranges |
|---|---|---|---|---|
| final-394-1.005 | 0.2456 [0.2445, 0.2662] | 0.2953 [0.2950, 0.2954] | 1.2024 | slower |
| final-394-1.01 | 0.1749 [0.1740, 0.1754] | 0.2096 [0.2091, 0.2109] | 1.1984 | slower |
| final-394-1.02 | 0.1304 [0.1300, 0.1306] | 0.2098 [0.2097, 0.2104] | 1.6089 | slower |
| ladybug-539-1.005 | 0.0907 [0.0905, 0.1004] | 0.1134 [0.1133, 0.1265] | 1.2503 | slower |
| ladybug-539-1.01 | 0.0621 [0.0620, 0.0646] | 0.1065 [0.1038, 0.1082] | 1.7150 | slower |
| ladybug-539-1.02 | 0.0621 [0.0620, 0.0623] | 0.0779 [0.0778, 0.0835] | 1.2544 | slower |
| trafalgar-138-1.005 | 0.3011 [0.2961, 0.3096] | 0.2260 [0.2246, 0.2286] | 0.7506 | faster |
| trafalgar-138-1.01 | 0.2316 [0.2314, 0.2333] | 0.1648 [0.1644, 0.1674] | 0.7116 | faster |
| trafalgar-138-1.02 | 0.1279 [0.1278, 0.1287] | 0.1061 [0.1054, 0.1072] | 0.8296 | faster |


## Initial-score and numerical checks

| Cell | Initial score min | Initial score max |
|---|---|---|
| dubrovnik-88 | 30562787.8472 | 30562787.8472 |
| final-3068 | 90993342.0243 | 90993342.0243 |
| final-394-1.005 | 4545737.6928 | 4545737.6928 |
| final-394-1.01 | 4545737.6928 | 4545737.6928 |
| final-394-1.02 | 4545737.6928 | 4545737.6928 |
| ladybug-539-1.005 | 5535080.11824 | 5535080.11824 |
| ladybug-539-1.01 | 5535080.11824 | 5535080.11824 |
| ladybug-539-1.02 | 5535080.11824 | 5535080.11824 |
| trafalgar-138-1.005 | 20163569.0159 | 20163569.0159 |
| trafalgar-138-1.01 | 20163569.0159 | 20163569.0159 |
| trafalgar-138-1.02 | 20163569.0159 | 20163569.0159 |
| venice-52 | 11152062.7728 | 11152062.7728 |

Maximum relative native-versus-independent endpoint cost error: 6.03e-11. `metrics.csv` contains all runs, native wall, outers, rejects, PCG/outer, retry fraction, initial score and archive source. Numeric/root solve attempts are separately identified in their traces; a root adjustment is not a nonlinear rejection.
