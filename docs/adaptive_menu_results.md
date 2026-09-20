# Adaptive candidate-menu pilot

Completed all 36 paired runs.
Three repeats per cell; 600-outer cap. Adaptive retains five CG shifts and changes scored candidates, with a confidence rule for the next center. Fixed single/multi controls use one/five shifts. All costs are GPU-fp64, initial costs independently checked. Small endpoint differences are tradeoffs; primary target bands are 1%,3%,5%.

| Phase | Scene | Arm | Success / failures | Cost median [range] | Seconds median [range] | Iterations / retries / matvecs / scored medians |
|---|---|---|---|---|---|---|
| development | ladybug-1197 | adaptive | 3 / 0 | 366763 [366715, 366786] | 21.155 [19.8963, 23.8973] | 145 / 143 / 10727 / 3691 |
| development | ladybug-1197 | multi | 3 / 0 | 366342 [365941, 366349] | 29.6503 [24.9882, 31.3376] | 129 / 299 / 16609 / 3721 |
| development | ladybug-1197 | single | 3 / 0 | 366156 [366129, 366189] | 12.4483 [10.9713, 15.0947] | 109 / 0 / 6897 / 1173 |
| development | venice-52 | adaptive | 3 / 0 | 244016 [242644, 244727] | 29.7915 [14.6374, 31.7693] | 338 / 0 / 24580 / 4500 |
| development | venice-52 | multi | 3 / 0 | 248711 [248701, 248776] | 32.5957 [28.7346, 59.009] | 371 / 0 / 26621 / 5865 |
| development | venice-52 | single | 3 / 0 | 253489 [253456, 253528] | 30.2954 [28.894, 48.0253] | 363 / 0 / 25507 / 4045 |
| evaluation | ladybug-598 | adaptive | 3 / 0 | 179916 [179914, 179993] | 4.21682 [3.90119, 4.75567] | 60 / 0 / 4045 / 822 |
| evaluation | ladybug-598 | multi | 3 / 0 | 180211 [180211, 180212] | 3.37112 [3.29615, 3.76643] | 49 / 0 / 3195 / 751 |
| evaluation | ladybug-598 | single | 3 / 0 | 179951 [179951, 179952] | 3.38595 [3.06914, 3.89077] | 56 / 0 / 3280 / 590 |
| evaluation | trafalgar-126 | adaptive | 3 / 0 | 103981 [103976, 103996] | 6.4541 [4.61684, 7.23447] | 121 / 0 / 11253 / 1791 |
| evaluation | trafalgar-126 | multi | 3 / 0 | 103981 [103979, 104014] | 8.29983 [8.20823, 10.3837] | 166 / 0 / 14411 / 2819 |
| evaluation | trafalgar-126 | single | 3 / 0 | 103984 [103982, 104213] | 9.71222 [7.47168, 14.6497] | 222 / 0 / 17446 / 2545 |

## Time to acceptable quality

Per scene, reference is the lowest endpoint among these three fixed measured arms, not a proven optimum. Target is reference*(1+epsilon). Trace crossing bounds charge all untraced solver time and rounding before crossing. Missing attainment is retained; a median is shown only when all three runs reach the target.

| Scene | Band | Arm | Reached / runs | Median upper-bound seconds |
|---|---:|---|---|---:|
| ladybug-1197 | 1% | single | 3/3 | 0.788566 |
| ladybug-1197 | 1% | multi | 3/3 | 1.62481 |
| ladybug-1197 | 1% | adaptive | 3/3 | 3.51879 |
| ladybug-1197 | 3% | single | 3/3 | 0.466084 |
| ladybug-1197 | 3% | multi | 3/3 | 0.890912 |
| ladybug-1197 | 3% | adaptive | 3/3 | 0.618617 |
| ladybug-1197 | 5% | single | 3/3 | 0.316584 |
| ladybug-1197 | 5% | multi | 3/3 | 0.734826 |
| ladybug-1197 | 5% | adaptive | 3/3 | 0.487817 |
| ladybug-598 | 1% | single | 3/3 | 0.38987 |
| ladybug-598 | 1% | multi | 3/3 | 0.389121 |
| ladybug-598 | 1% | adaptive | 3/3 | 0.525419 |
| ladybug-598 | 3% | single | 3/3 | 0.18937 |
| ladybug-598 | 3% | multi | 3/3 | 0.277651 |
| ladybug-598 | 3% | adaptive | 3/3 | 0.232419 |
| ladybug-598 | 5% | single | 3/3 | 0.17237 |
| ladybug-598 | 5% | multi | 3/3 | 0.211351 |
| ladybug-598 | 5% | adaptive | 3/3 | 0.177519 |
| trafalgar-126 | 1% | single | 3/3 | 1.12312 |
| trafalgar-126 | 1% | multi | 3/3 | 1.01913 |
| trafalgar-126 | 1% | adaptive | 3/3 | 0.369839 |
| trafalgar-126 | 3% | single | 3/3 | 0.236403 |
| trafalgar-126 | 3% | multi | 3/3 | 0.32293 |
| trafalgar-126 | 3% | adaptive | 3/3 | 0.281839 |
| trafalgar-126 | 5% | single | 3/3 | 0.16082 |
| trafalgar-126 | 5% | multi | 3/3 | 0.22293 |
| trafalgar-126 | 5% | adaptive | 3/3 | 0.211339 |
| venice-52 | 1% | single | 0/3 | — |
| venice-52 | 1% | multi | 0/3 | — |
| venice-52 | 1% | adaptive | 3/3 | 8.45039 |
| venice-52 | 3% | single | 0/3 | — |
| venice-52 | 3% | multi | 3/3 | 10.8742 |
| venice-52 | 3% | adaptive | 3/3 | 3.87709 |
| venice-52 | 5% | single | 3/3 | 13.8416 |
| venice-52 | 5% | multi | 3/3 | 3.93342 |
| venice-52 | 5% | adaptive | 3/3 | 2.52182 |

## Controller execution

| Scene | N | Full / center-only checkpoint menus (summed) | Freeze-eligible attempts | Anchor / extra scoring seconds (summed) |
|---|---:|---|---:|---|
| ladybug-1197 | 3 | 1682 / 182 | 779 | 2.093 / 4.731 |
| ladybug-598 | 3 | 128 / 454 | 76 | 0.368 / 0.202 |
| trafalgar-126 | 3 | 276 / 1091 | 116 | 0.473 / 0.235 |
| venice-52 | 3 | 521 / 2299 | 400 | 1.947 / 0.868 |

## Geometric diagnostics

These are reprojection and cheirality diagnostics, not ground-truth reconstruction accuracy.

| Scene | Arm | N | Median reprojection error (px), median across runs | Cheirality violations (observations), median across runs |
|---|---|---:|---:|---:|
| ladybug-1197 | adaptive | 3 | 0.560929 | 181 |
| ladybug-1197 | multi | 3 | 0.560796 | 181 |
| ladybug-1197 | single | 3 | 0.560646 | 188 |
| venice-52 | adaptive | 3 | 0.355995 | 2 |
| venice-52 | multi | 3 | 0.361256 | 10 |
| venice-52 | single | 3 | 0.369079 | 38 |
| ladybug-598 | adaptive | 3 | 0.541802 | 40 |
| ladybug-598 | multi | 3 | 0.54208 | 48 |
| ladybug-598 | single | 3 | 0.541857 | 42 |
| trafalgar-126 | adaptive | 3 | 0.52929 | 212 |
| trafalgar-126 | multi | 3 | 0.52926 | 216 |
| trafalgar-126 | single | 3 | 0.529262 | 212 |
