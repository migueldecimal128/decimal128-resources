# d48/ — internal D48 test data

Test data for the D48 extended-precision domain that the transcendentals (exp,
exp10, ln, log10, pow, pown, rootn) compute in: a 48-digit coefficient with
96-digit exact intermediates (`workorder/D48SwiftWorkOrder.md`). These files test
D48 internals and drive its benchmark. The public-API sweeps live in
`rosetta/native/transcsweep.txt` and `transcstress.txt`.

All files are LF. Generators are in `decimal128-workorder/d48-prototype/`.

| file | lines | content | generator |
|---|---|---|---|
| `ops.txt` | 22,505 | D48 arithmetic, `op a b [c] -> r`: add, sub, mul, sqr, div, sqrt, fma, rta, rtn, cmp, tol; 48-digit results from Python decimal at prec 48 (seed 48) | `gen_d48_vectors.py` |
| `transc_truth.txt` | 1,989 | `fn x [y] -> v`: exp, exp10, ln, log10, pow true values at 130 digits (seed 6), for measuring the D48 kernels' error bounds | `gen_transc_vectors.py` |
| `bench_pool.txt` | 512 | the transcendental benchmark pools: 64 inputs per op (exp, exp10, ln, log10, pow, pown_pos, pown_neg, compound), taken from the 14k sweep; run ties-to-even | `widesweep.py gen-bench-pool` |

Each file's first line is a `#` comment naming its generator and seed. Values are
written `coefficient E exponent` (`ops.txt`, `transc_truth.txt`) or as plain
decimal strings (`bench_pool.txt`).

## Related files in `rosetta/native/`

- `transcsweep.txt`: the 14,000-line differential sweep (seed 3).
- `transcstress.txt`: the 16,180-line boundary-stress sweep (seed 6).
- `transccompound.txt`: the sweep's 1,330 compound lines that a port rounding
  1 + x to 34 digits gets wrong, split out of `transcsweep.txt` by
  `split_compound.py` (CompoundD48OnePlusXWorkOrder.md CX-6).
- `translargen.txt`: pown and compound at |n| > 2^31, 6,619 active lines and 21
  gap lines (seed 29), written by `pown_largen_phase0.py gen-rosetta`
  (PownLargeNWorkOrder.md LN-7). Ports with a 32-bit n exclude it.

The sweeps were written by `widesweep.py gen-rosetta`. Expected results are Python
decimal's correctly rounded values, with flags. An exact result takes its op's
preferred exponent. Lines the D48 configuration doesn't get right are commented
out with a reason:

- `// gap:` the documented 1-ulp gap near 1, with the D48 answer every port must
  match;
- `// pow-cohort:` a known punchlist bug, not D48.
