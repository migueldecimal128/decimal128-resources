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
band+profile generators in `bid_inputs.cpp` (splitmix64, seed `0x1234567`, N=4096
per band/profile), rendered to canonical decimal strings via Intel libbid's
`__bid128_to_string`. Every operand is round-trip certified by
`verify_corpus.cpp`: string → `d128_parse` → `d128_to_bid128` reproduces the
original BID bit-for-bit (**196,608/0 mismatches** across all three profiles).
`__bid128_to_string` on a canonical value (coefficient < 10^34) is an exact
decimal→decimal render — no float round-trip — so parse-back is exact in any
conformant decimal128.

## Layout

```
swept/
  P-gen/        general: digit-length-uniform coefficients 1..34 (log-uniform magnitude)
    SQ.txt NQ.txt MQ.txt OQ.txt FQ.txt   add/sub alignment bands (§3.1)
    CP.txt WP.txt XP.txt          mul product-width bands (§3.2)
    CD.txt WD.txt XD.txt          div divisor-width bands (§3.3)
    ET.txt PT.txt                 div value-driven exact/power-of-ten (§3.3)
  P-fin/        financial: coefficients < 2^64 (≤19 digits, log-uniform), currency
                quantum {0,-2,-4,-6}, every operand ≥1 integer digit
    MIX.txt                       realistic add/sub mix (see below)
    CP.txt WP.txt                 mul (XP needs >19-digit operands ⇒ omitted)
    CD.txt WD.txt ET.txt PT.txt   div (XD needs a >19-digit divisor ⇒ omitted)
  P-max/        full-width stress: coefficients pinned 33..34 (wide-path diagnostic)
    SQ.txt OQ.txt FQ.txt          add/sub (NQ can't be no-round at 34 digits ⇒ omitted)
    XP.txt                        mul extra-wide (CP/WP need small operands ⇒ omitted)
    XD.txt                        div extra (CD/WD/ET/PT need small divisors ⇒ omitted)
```

Bands follow `decimal128-www/BenchmarkMatrix.md`. A **band** is a RELATION between the
two operands (exponent gap + digit widths); a **profile** (§2.1) is the cross-cutting
operand-magnitude axis. Each per-band file serves whichever op(s) exercise its
distribution: SQ/NQ/OQ/FQ feed add AND sub, CP/WP/XP feed mul, CD/WD/XD/ET/PT feed div.

**Profiles are not all-12-bands each** — a profile gates band feasibility:

- **P-gen** — all 13 bands; the default headline for the P-gen cross-port sweep. The
  add/sub alignment axis (§3.1) splits the no-round region by exponent gap Δ: **SQ**
  (Δ=0), **NQ** (1≤Δ≤4, pack-direct path), **MQ** (Δ>4, qAlignDelta>4 path) — all three
  `trim=0`. SQ/NQ/MQ are the **compact regime**: qExp ∈ [0,−8] and operands sized so
  the add/sub result stays < 10²⁸, i.e. representable by the 28-digit compact
  alternatives (rust_decimal / System.Decimal). **OQ** (align + round, `trim≥1`) and
  **FQ** (fully swamped) keep the full 34-digit / wide-exponent range — no compact
  alternative there.
- **P-fin** — the financial reality: 64-bit coefficients, so the aligned add/sub span
  stays < 34 digits and never rounds ⇒ no OQ/FQ. Add/sub is a single realistic
  **`MIX.txt`**: 75% of pairs share a qExp (same-quantum), 25% draw each operand's
  quantum independently from {0,-2,-4,-6}. That one stream spans the SQ path (gap 0),
  the pack path (gap 2/4), and the qAlignDelta>4 path (gap 6) in realistic proportion —
  so it is NOT split into SQ/NQ band files. Mul is CP/WP, div is CD/WD/ET/PT (XP/XD need
  >19-digit operands, unreachable in 64-bit money math).
- **P-max** — the full-width stress diagnostic: only the wide-path bands (SQ/OQ/FQ, XP,
  XD); the compact bands need small operands and are omitted.

Because the profiles differ in which bands exist, a consumer iterating a profile must
use that profile's band set (the files present), not assume all 12.

## File format

Two space-separated canonical decimal strings per line (operand x, operand y);
`#` begins a comment. Coefficient + `E` + signed exponent (e.g.
`-797492671848831E+21`), the ecosystem scientific form. 4096 data lines per file.
