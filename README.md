# decimal128-resources

Shared, **read-only** data assets for the [decimal128](https://github.com/migueldecimal128)
ports — benchmark inputs, conformance corpora, and reference outputs.

The eight ports (`decimal128-c`, `-java`, `-kotlin`, `-python`, `-rust`, `-go`,
`-swift`, `-csharp`) are independent repositories. Rather than duplicate these
data files in each one, they consume this repo as a **git submodule**, so the
bytes live here once and each port pins a commit.

## Layout

```
telco/          Cowlishaw "telco" benchmark (https://speleotrove.com/decimal/telco.html)
  expon180.1e6b         1,000,000-number binary input (primary perf workload)
  expon180.1e6.expected reference output for the 1e6 run (correctness gate)
  telco.testb           10-number binary input (smoke test)
  telco.expected        reference output for the 10-number run
  README.txt            provenance, formats, control totals, computation

rosetta/        conformance corpora shared by every port's test suite
  dectest/              IBM/Cowlishaw decQuad + math dectest vectors (+ doc/*.pdf)
  fptest/               IBM 754-2019 fptest vectors
  intel/readtest.in     Intel BID reference vectors (+ LICENSE/eula/sample)
  native/               hand-authored decimal128 cases (strict: 0 skips)
  native.index          every native/ file; ports run these (see below)
  native.exclude        native files a port does not run, each with a reason
  files.index           the dectest / fptest / intel files every port runs
  dectest.map           scope filters + operator include/exclude, per source
  fptest.map              (include: token -> canonical op; exclude: token -> reason)
  intel.map
  dectest.skip          per-line skips, each with a reason, per source
  intel.skip
  runner.exclude        operators one port's runner does not run, with a reason
  expected.tsv          exact counts per port x runner x source x file (generated)
  gen_expected.py       writes expected.tsv from the corpora and the files above
  check_rosetta.py      checks all of the above against the corpora (run by CI)
  golden/               bit-exact transcendental oracle (ln/log10/exp)

d48/            internal D48 (48-digit transcendental domain) vectors (see d48/README.md)
  ops.txt               D48 arithmetic vectors, 48-digit results
  transc_truth.txt      130-digit true values for the kernel error bounds
  bench_pool.txt        transcendental benchmark pools, 64 inputs per op

swept/          cross-port swept-benchmark operand corpus (4096/band, see swept/README.md)
  P-gen/                general profile: digit-length-uniform coefficients 1..34 (all 12 bands)
  P-fin/                financial profile: 64-bit coeffs, currency quantum (MIX + mul/div bands)
  P-max/                full-width stress: 33..34-digit coeffs (wide-path bands only)

text_bid_dpd/   text <-> BID/DPD interchange vectors
  text_bid128_dpd128_100.csv.txt           100-row smoke set
  text_bid128_dpd128_canonical.csv.txt     full canonical cohort/payload sweep
  text_bid128_dpd128_noncanonical.csv.txt  non-canonical decode-only cases
  text_bid128_dpd128_parse.csv.txt         parse-direction accepts (quoted text column)
  text_bid128_dpd128_error.csv.txt         parse-direction rejects, each with its status token
```

The `dectest/exp`, `ln`, and `log10` files use LF (the rest of the corpus is
already LF); all other corpora are stored verbatim.

Reference outputs use CRLF line endings, matching the benchmark programs'
`"\r\n"` writes; correctness is byte-for-byte against the `*.expected` files.

## Running and excluding native files

Ports don't list `rosetta/native/` themselves. Each port's Rosetta runner runs the
files in `rosetta/native.index`, minus its own lines in `rosetta/native.exclude`:

```
# <port>[:<runner>]  <file>  <reason>
csharp:net11  transcendental_sweep.txt  runs .NET 11's own Decimal128, not this port's D48
```

- Ports: `c python swift rust go zig java kotlin csharp csharp-bid`. Runners:
  `core`, `wrapper`, `net11` (csharp and csharp-bid only). A line without a runner excludes the file
  from every runner of that port.
- Every exclusion carries a reason. Remove the line when the reason no longer
  holds. Excluding or re-enabling a file is a change here only, not in the ports.
- A new `native/` file must be added to `native.index`, or no port runs it.
  `rosetta/check_rosetta.py` checks this and the exclusion format; the
  `check-rosetta` GitHub Action runs it on every push.

Design: `decimal128-workorder/NativeCorpusExclusionWorkOrder.md`.

## What every port runs: the shared Rosetta data

What a port runs from the dectest, fptest and Intel corpora is data here, not
code in each port. Each port reads these files and keeps only one table of its
own: canonical op name -> its dispatch arm.

- `files.index`: the corpus files, `<source>\t<file>`.
- `<source>.map`: `scope` filters (dectest precision 34, the five IEEE rounding
  modes, no bare `#` operand; fptest `d128` lines; Intel `bid128_` tokens), then
  `include <token> <canonical op>` or `exclude <token> <reason>`. Every in-scope
  corpus token is in exactly one of the two.
- `<source>.skip`: `=<tag> <reason>` defines a reason; `line <tag> <exact line>`
  skips one case; `attr <tag> <ops> <attribute>` skips lines of those ops that
  carry the attribute (Intel `longintsize=32`).
- `runner.exclude`: `<port>[:<runner>] <source> <token> <reason>`, for an
  included operator one runner cannot run (Java's wrapper has no unsigned
  conversions).
- `expected.tsv`: generated by `gen_expected.py`. A runner passes a file when
  it reports `passed == cases - skipped`, the listed `skipped`, and no failures.
  After any change to the corpora or the files above, run
  `python3 rosetta/gen_expected.py` and commit the result.

All fields are tab-separated; `#` starts a comment line. `check_rosetta.py`
fails on a contradictory, undecided or stale map entry, a skip that matches no
case, an unused or undefined reason, a bad `runner.exclude` line, a file-list
mismatch, or a stale `expected.tsv`.

Design: `decimal128-workorder/RosettaHarnessAlignmentWorkOrder.md`.

## Consuming this repo (submodule)

Each port mounts this repo at a fixed path and resolves data through its own
build/source anchor (never a working-directory-relative path):

```sh
git submodule add https://github.com/migueldecimal128/decimal128-resources.git <mount-path>
git submodule update --init
```

Clone a consumer with its data in one step via `git clone --recursive`, or
`git submodule update --init` in an existing checkout. This repo is **public**,
so no authentication is required in CI.

## Provenance & licensing

These are publicly distributed reference/test data:

- **telco** — Mike Cowlishaw's telco benchmark and specification
  (`speleotrove.com/decimal/telco.html`, `telcoSpec.html`). Input files are
  redistributed verbatim; `*.expected` files were generated from the benchmark
  and validated against the published control totals and cross-port agreement.
  See `telco/README.txt`.
- **rosetta** — IBM/Cowlishaw `dectest`, IBM `fptest`, Intel test
  vectors, plus hand-authored `native` cases.
