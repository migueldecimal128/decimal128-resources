#!/usr/bin/env python3
"""Check the shared Rosetta data in rosetta/ against the corpora (run by CI).

decimal128-workorder RosettaHarnessAlignmentWorkOrder.md R-6 (and, for the
native files, NativeCorpusExclusionWorkOrder.md). Fails (exit 1) when:

  native.index / native.exclude
  - a native/*.txt file is missing from the index, or the index lists a file
    that does not exist; the index is not sorted, or lists a file twice;
  - an exclusion line has an unknown port or runner, or no reason;
  - an exclusion names a file that is not in the index, or repeats another line.

  files.index
  - a dectest/fptest/intel corpus file is missing from it, or it lists a file
    that does not exist; it is not sorted, or lists a file twice.

  <source>.map (dectest, fptest, intel)
  - a token is both included and excluded; a corpus token is in neither; a map
    key is not in the corpus; the source yields no in-scope tokens.

  <source>.skip
  - a reason tag is used but not defined, or defined but not used;
  - an entry matches no case (a stale skip).

  runner.exclude
  - unknown port, runner or source; no reason; a token the source's map does
    not include (native: an op no native line has); a repeated line.

  corpus
  - a line of an included operator has a shape no runner can parse.

  expected.tsv
  - it differs from a fresh run of rosetta/gen_expected.py.

Usage: python3 rosetta/check_rosetta.py [rosetta dir]   (default: this script's dir)
Standard library only.
"""
import os
import sys

PORTS = {"c", "python", "swift", "rust", "go", "zig", "java", "kotlin", "csharp", "csharp-bid"}
RUNNERS = {"core", "wrapper", "net11"}
NET11_PORTS = {"csharp", "csharp-bid"}


def content_lines(path):
    """(line number, text) for each line that is not blank or a # comment."""
    with open(path, encoding="utf-8", newline="") as fh:
        raw = fh.read()
    if "\r" in raw:
        yield 0, None  # CRLF: reported by the caller
        return
    for n, line in enumerate(raw.split("\n"), 1):
        text = line.strip()
        if text and not text.startswith("#"):
            yield n, text


def check_native(root):
    errors = []
    native = os.path.join(root, "native")
    index_path = os.path.join(root, "native.index")
    exclude_path = os.path.join(root, "native.exclude")

    on_disk = sorted(f for f in os.listdir(native)
                     if f.endswith(".txt") and os.path.isfile(os.path.join(native, f)))

    index = []
    for n, text in content_lines(index_path):
        if text is None:
            return ["native.index: CRLF line endings (must be LF)"], 0, 0
        if len(text.split()) != 1:
            errors.append(f"native.index:{n}: one file name per line, got {text!r}")
            continue
        index.append(text)
    for f in sorted(set(index)):
        if index.count(f) > 1:
            errors.append(f"native.index: {f} listed {index.count(f)} times")
    if index != sorted(index):
        errors.append("native.index: not sorted")
    for f in on_disk:
        if f not in index:
            errors.append(f"native.index: missing {f} (in native/, not indexed: no port would run it)")
    for f in index:
        if f not in on_disk:
            errors.append(f"native.index: {f} does not exist in native/")

    seen = set()
    for n, text in content_lines(exclude_path):
        if text is None:
            return errors + ["native.exclude: CRLF line endings (must be LF)"], len(index), 0
        parts = text.split(None, 2)
        where = f"native.exclude:{n}"
        if len(parts) < 3:
            errors.append(f"{where}: needs <port>[:<runner>] <file> <reason>, got {text!r}")
            continue
        scope, f, _reason = parts
        port, _, runner = scope.partition(":")
        if port not in PORTS:
            errors.append(f"{where}: unknown port {port!r}")
        if runner:
            if runner not in RUNNERS:
                errors.append(f"{where}: unknown runner {runner!r}")
            elif (runner == "net11") and (port not in NET11_PORTS):
                errors.append(f"{where}: runner net11 exists only for {sorted(NET11_PORTS)}")
        if f not in index:
            errors.append(f"{where}: {f} is not in native.index (stale exclusion?)")
        if (scope, f) in seen:
            errors.append(f"{where}: {scope} {f} excluded twice")
        seen.add((scope, f))

    return errors, len(index), len(seen)


CORPUS_EXT = {"dectest": (".decTest", ".dectest"), "fptest": (".fptest",), "intel": (".in",)}


def check_shared(root):
    """Errors in files.index, the maps, the skips, runner.exclude and expected.tsv."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import gen_expected as gen

    try:
        corpus = gen.Corpus(root)
    except gen.DataError as e:
        return [str(e)], None
    errors = list(corpus.errors)

    # files.index against the directories.
    listed = []
    for n, line in gen.data_lines(os.path.join(root, "files.index")):
        listed.append(tuple(line.split("\t", 1)))
    if listed != sorted(listed):
        errors.append("files.index: not sorted")
    for src in gen.MAPPED:
        names = corpus.files[src]
        for f in sorted(set(names)):
            if names.count(f) > 1:
                errors.append(f"files.index: {src} {f} listed {names.count(f)} times")
        d = os.path.join(root, gen.SOURCE_DIRS[src])
        on_disk = sorted(f for f in os.listdir(d)
                         if f.endswith(CORPUS_EXT[src]) and os.path.isfile(os.path.join(d, f)))
        for f in on_disk:
            if f not in names:
                errors.append(f"files.index: missing {src} {f} (in {src}/, not listed: no port would run it)")
        for f in names:
            if f not in on_disk:
                errors.append(f"files.index: {src} {f} does not exist in {src}/")

    # The partition (Rosetta.md §9): both / neither / stale / empty.
    for src in gen.MAPPED:
        m = corpus.maps[src]
        toks = corpus.tokens[src]
        if not toks:
            errors.append(f"{src}.map: the corpus yields no in-scope tokens (path broken?)")
        both = sorted(set(m.include) & set(m.exclude))
        if both:
            errors.append(f"{src}.map: contradictory decision for: {', '.join(both)}")
        neither = sorted(toks - set(m.include) - set(m.exclude))
        if neither:
            errors.append(f"{src}.map: undecided operator(s) — add to include or exclude: {', '.join(neither)}")
        stale = sorted((set(m.include) | set(m.exclude)) - toks)
        if stale:
            errors.append(f"{src}.map: map key(s) not present in the corpus — prune: {', '.join(stale)}")

    # Skips: every tag used, every entry matching a case.
    for src in gen.MAPPED:
        sk = corpus.skips[src]
        used_tags = {e[3] for e in sk.entries}
        for tag in sorted(set(sk.reasons) - used_tags):
            errors.append(f"{src}.skip: reason tag {tag!r} is defined but not used")
        for where, kind, key, _ in sk.entries:
            if where not in corpus.used_skips[src]:
                errors.append(f"{where}: matches no case (stale skip): {key if kind == 'line' else ' '.join(key)}")

    # runner.exclude.
    seen = set()
    for n, port, runner, src, tok, _reason in corpus.runner_exclude:
        where = f"runner.exclude:{n}"
        if port not in gen.PORTS:
            errors.append(f"{where}: unknown port {port!r}")
        elif runner and runner not in gen.PORT_RUNNERS[port]:
            errors.append(f"{where}: {port} has no {runner!r} runner")
        if src == "native":
            if tok not in corpus.native_tokens:
                errors.append(f"{where}: {tok} is the op of no native line")
        elif src not in gen.MAPPED:
            errors.append(f"{where}: unknown source {src!r}")
        elif tok not in corpus.maps[src].include:
            errors.append(f"{where}: {tok} is not included by {src}.map")
        if (port, runner, src, tok) in seen:
            errors.append(f"{where}: repeats an earlier line")
        seen.add((port, runner, src, tok))

    errors += [f"corpus: {m}" for m in corpus.malformed]

    # expected.tsv is up to date.
    fresh = gen.render(corpus.rows())
    path = os.path.join(root, "expected.tsv")
    if not os.path.exists(path):
        errors.append("expected.tsv: missing — run rosetta/gen_expected.py")
    else:
        with open(path, encoding="utf-8", newline="") as f:
            if f.read() != fresh:
                errors.append("expected.tsv: out of date — run rosetta/gen_expected.py")
    return errors, corpus


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    errors, n_index, n_exclude = check_native(root)
    shared, corpus = check_shared(root)
    errors += shared
    for e in errors:
        print(f"ERROR {e}")
    if errors:
        print(f"check_rosetta: {len(errors)} error(s)")
        return 1
    print(f"check_rosetta: OK (native: {n_index} indexed files, {n_exclude} exclusions; "
          + ", ".join(f"{s}: {len(corpus.files[s])} files, {len(corpus.maps[s].include)} include + "
                      f"{len(corpus.maps[s].exclude)} exclude, {len(corpus.skips[s].entries)} skips"
                      for s in ("dectest", "fptest", "intel"))
          + f"; {len(corpus.runner_exclude)} runner exclusions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
