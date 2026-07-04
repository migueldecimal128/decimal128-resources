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
  golden/               bit-exact transcendental oracle (ln/log10/exp)
```

The `dectest/exp`, `ln`, and `log10` files use LF (the rest of the corpus is
already LF); all other corpora are stored verbatim.

Reference outputs use CRLF line endings, matching the benchmark programs'
`"\r\n"` writes; correctness is byte-for-byte against the `*.expected` files.

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
