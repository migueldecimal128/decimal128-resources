# Cairo University decimal128 test vectors

Decimal floating-point verification vectors by **Amr Sayed-Ahmed** and
**Hossam A. H. Fahmy**, Cairo University, from Fahmy's "Arithmetic operations
debugging and verification" page:

    http://eece.cu.edu.eg/~hfahmy/arith_debug/      (plain HTTP; HTTPS fails the TLS handshake)

**License (as stated on that page):** copyrighted to the authors; free to use
for any purpose, provided as is, with no warranty; credit to the authors is
requested.

**Documentation:** Amr A.-F. R. Sayed-Ahmed, *Verification of Decimal
Floating-Point Operations*, MSc thesis (supervisor Hossam A. H. Fahmy),
Faculty of Engineering, Cairo University, 2011. Copy: `doc/2011_06_vdfp.pdf`,
from

    http://www.eece.cu.edu.eg/~hfahmy/thesis/2011_06_vdfp.pdf

(byte-identical to `amr_thesis_final.pdf` linked from the vectors page, md5
`b2e675b131fbb655f6ea9ea506b01671`). Chapters 2–6 describe the five engines
(add/subtract, multiply, FMA, square root, divide) and their coverage models.
The model names are the file-name suffixes (types, result, rounding, sticky,
shift, carry, cancel, trailing, nines/zeros, overflow, underflow, clamping).
Appendix A is the vector syntax summarized below. The authors' Asilomar 2010
and AICCSA 2011 papers cover the same work.

## Contents

The six decimal128 sets, downloaded 2026-11-23, every file checked against the
upstream `.md5sum` before use. Each zip's per-set subdirectory is flattened
here; the file names already begin with the set name.

| Set | Files | Vectors |
|---|---:|---:|
| `2011_09_d128_add` (`+` `-`) | 17 | 1,247,467 |
| `2011_10_d128_mul` (`*`) | 16 | 1,103,450 |
| `2011_09_d128_fma` (`*+` `*-`) | 36 | 4,388,064 |
| `2011_04_d128_div` (`/`) | 15 | 341,808 |
| `2011_11_d128_div` (`/`) | 14 | 1,665,375 |
| `2011_04_d128_sqrt` (`V`) | 12 | 199,024 |
| **total** | **110** | **8,945,188** |

`md5sum/` holds the six upstream `.md5sum` files verbatim (their paths carry
the zip's subdirectory, `<set>/<file>`).

## Format

IBM FPgen syntax, the same family as `../fptest/` (thesis Appendix A); one
vector per line, LF, no header:

    d128<op> <rounding> <operand>... -> <result> [<flags>]

- op: `+` `-` `*` `/` `*+` (fused a·b + c) `*-` (fused a·b − c) `V` (square root)
- rounding: `=0` ties-to-even, `h>` ties-to-away, `>` toward +∞, `<` toward −∞,
  `0` toward zero. (`h>` is Cairo's spelling of fptest's `=^`.)
- operands/results: `±<coefficient>E<exponent>`, `±Inf`, `Q` (qNaN), `S` (sNaN).
  (Appendix A spells infinity `<sign>inf`; the files use `+Inf`/`-Inf`.)
- flags: `x` inexact, `u` underflow, `o` overflow, `z` division by zero,
  `i` invalid

`*-` was confirmed as the fused a·b − c: every vector matches a correctly
rounded fma(a, b, −c).

## Validation

Before import, all 8,945,188 vectors were checked against Python's `decimal`
(precision 34, Emax 6144, clamp 1): result value, exponent (cohort), sign and
flags all agree, in all five rounding modes. (Python's `sqrt` rounds
ties-to-even regardless of context, so directed-mode square roots were
recomputed at 120 digits and rounded in the vector's mode.)

## Corrections

Three lines are deleted from the upstream files. The upstream files match their
published md5, so the damage is in the source, not in transfer.

| File | Upstream md5 | Lines | Stored md5 |
|---|---|---|---|
| `2011_09_d128_fma_type4.txt` | `8905a8829dba067949b99f9e53bd8032` | 245,648 → 245,646 | `927b55d12b55065a1e78643bb0068850` |
| `2011_04_d128_sqrt_type1.txt` | `2d5b8781c0136934a750e1d2866cff78` | 1,098 → 1,097 | `2c34e1bd67d89d8e950f1c28700f0a46` |

- `2011_09_d128_fma_type4.txt`, lines 233,509–233,510: bytes
  37,279,771–37,296,166 (16,396 bytes) are a run of `#` with one newline,
  overwriting about 100 vectors. What remained was a 9,999-character line
  `d128*+ > +135611477298866693835828130923706###…` (no third operand, no
  `->`) and a 6,490-character line `###…E6111 -> -9999999999999999999999999999999999E6111 x`
  (the tail of an unknown vector). Both are deleted.
- `2011_04_d128_sqrt_type1.txt`, line 726: `d128V =0 -> Q i`, a square root
  with no operand. Deleted.

The other 108 files are byte-identical to upstream.
