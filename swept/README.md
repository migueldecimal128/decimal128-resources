# swept/ — cross-port swept-benchmark operand corpus

Canonical decimal-string operand pairs for the **swept** microbenchmark: a
4096-input average per op/band (bare `thru`), the headline methodology across all
ports (complements the fixed-operand best-case rows). Every port reads THESE
strings and parses them with its own conformant parser, so the cross-port swept
numbers run over byte-identical operands — and identical to the operands the C
benchmark (`decimal128-c/benchmark/bench_main.cpp`) already sweeps, since both
draw from the same deterministic generators.

## Provenance

Generated once by `decimal128-c/benchmark/dump_corpus.cpp` from the deterministic
band generators in `bid_inputs.cpp` (splitmix64, seed `0x1234567`, N=4096 per
band), rendered to canonical decimal strings via Intel libbid's
`__bid128_to_string`. Every operand is round-trip certified by
`verify_corpus.cpp`: string → `d128_parse` → `d128_to_bid128` reproduces the
original BID bit-for-bit (98,304/0 mismatches). `__bid128_to_string` on a
canonical value (coefficient < 10^34) is an exact decimal→decimal render — no
float round-trip — so parse-back is exact in any conformant decimal128.

## Layout

```
swept/
  P-gen/        profile: digit-length-uniform (coefficients 1..34 digits)
    SQ.txt NQ.txt OQ.txt FQ.txt   add/sub alignment bands (§3.1)
    CP.txt WP.txt XP.txt          mul product-width bands (§3.2)
    CD.txt WD.txt XD.txt          div divisor-width bands (§3.3)
    ET.txt PT.txt                 div value-driven exact/power-of-ten (§3.3)
```

Bands follow `decimal128-www/BenchmarkMatrix.md`. A band is a RELATION between the
two operands (exponent gap + digit widths), so each file keeps its band label and
serves whichever op(s) exercise that distribution: SQ/NQ/OQ/FQ feed add AND sub,
CP/WP/XP feed mul, CD/WD/XD/ET/PT feed div.

Additional profiles **P-fin** (64-bit coefficients) and **P-max** (34-digit) are a
planned follow-up; they need a width knob threaded through the generators.

## File format

Two space-separated canonical decimal strings per line (operand x, operand y);
`#` begins a comment. Coefficient + `E` + signed exponent (e.g.
`-797492671848831E+21`), the ecosystem scientific form. 4096 data lines per file.
