# Result digests

`digests.tsv` holds one expected 64-bit digest per (operation, rounding mode).
Every core computes each digest from the same generated inputs and fails if its
digest differs. A digest covers both the result encoding and the exception
flags of every call, so any difference in any result, in any port, changes it.

This is check C1 of the port-parity checks. It complements the Rosetta corpora:
the corpora pin chosen cases; the digests cover a large volume of generated
ones.

Everything below is specified exactly. Two ports that follow it compute the
same digest if and only if they return the same results and flags.

## Table format

`digests.tsv` is tab-separated. Lines starting with `#` are comments.

```
op      mode    count   seed    digest
add     0       2000    1       4b1f0c2e8a6d3f17
```

- `op`: the core operation; the call is `d128_<op>_rnd_ctxnull`.
- `mode`: the core rounding code, `ROUND_*` 0..4 (0 ties-to-even, 1 ties-to-away,
  2 toward-zero, 3 toward-positive, 4 toward-negative).
- `count`: number of calls.
- `seed`: the generator seed.
- `digest`: 16 lowercase hex digits.

## Generator

SplitMix64, the generator every port's `TestU320` already uses. Unsigned 64-bit
arithmetic, wrapping:

```
next():
    state = state + 0x9E3779B97F4A7C15
    z = state
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9
    z = (z ^ (z >> 27)) * 0x94D049BB133111EB
    return z ^ (z >> 31)
```

`>>` is a logical (unsigned) shift and `%` is unsigned remainder. Each table line
starts a new generator with `state = seed`.

## Operands

A decimal operand is generated as a string and read with the port's
`d128_parse`. Parsing must succeed.

```
decimal():
    c = next() % 16
    if c == 0:                                   special or zero
        k = next() % 6
        k == 0: "NaN"
        k == 1: "-NaN"
        k == 2: "sNaN"
        k == 3: "Inf"
        k == 4: "-Inf"
        k == 5: s = next() % 2
                e = (next() % 41) - 20
                return (s == 1 ? "-" : "") + "0E" + e
    s = next() % 2
    n = 1 + next() % 34                          number of coefficient digits
    digits = n characters, each '0' + (next() % 10), in order
    if c <= 2:                                   wide exponent
        q = (next() % 12288) - 6176              q in [-6176, 6111]
    else:                                        near 1
        e = (next() % 41) - 20                   adjusted exponent in [-20, 20]
        q = e - (n - 1)
    return (s == 1 ? "-" : "") + digits + "E" + q
```

Exponents are written in decimal with a leading `-` when negative and no `+`.
Leading zeros in `digits` are kept.

An integer operand (for `compound`, `pown`, `rootn`) is:

```
integer():
    return (next() % 2001) - 1000                in [-1000, 1000]
```

## Operations and draw order

| arity | ops | call |
|---|---|---|
| unary | sqrt, exp, exp10, expm1, exp10m1, ln, lnp1, log10, log10p1, log2p1 | `op(x, mode, ctx)` |
| binary | add, subtract, multiply, divide, pow, quantize | `op(x, y, mode, ctx)` |
| ternary | fma | `op(x, y, z, mode, ctx)` |
| integer | compound, pown, rootn | `op(x, n, mode, ctx)` |

For each call, operands are drawn in argument order: `x`, then `y`, then `z`,
then `n`.

## Digest

```
h = 0
repeat count times:
    draw the operands
    ctx = a new default Context
    r = d128_<op>_rnd_ctxnull(operands..., mode, ctx)
    (lo, hi) = the two 64-bit words of d128_to_bid128(r), least significant first
    f = ctx.exceptionFlagsInt()                  bit i set for Exception754 code i
    h = mix(h ^ lo)
    h = mix(h ^ hi)
    h = mix(h ^ f)
digest = h

mix(z):
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9
    z = (z ^ (z >> 27)) * 0x94D049BB133111EB
    return z ^ (z >> 31)
```

`mix` is the SplitMix64 output function.

## Recording and checking

The reference port (Swift) records the digests. A port's test reads
`digests.tsv`, computes every line, and fails on the first mismatch, printing the
line. To find the first differing call, compare a port's per-call
`(lo, hi, f)` stream against the reference's for that line.
