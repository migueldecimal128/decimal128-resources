#!/usr/bin/env python3
"""Check rosetta/native.index and rosetta/native.exclude against rosetta/native/.

Ports run the files in native.index minus their own entries in native.exclude
(decimal128-workorder NativeCorpusExclusionWorkOrder.md), so the two files must
agree with the directory. Fails (exit 1) when:

  - a native/*.txt file is missing from the index, or the index lists a file
    that does not exist;
  - the index is not sorted, or lists a file twice;
  - an exclusion line has an unknown port or runner, or no reason;
  - an exclusion names a file that is not in the index, or repeats another line.

Usage: python3 rosetta/check_native.py [rosetta dir]   (default: this script's dir)
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


def check(root):
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


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    errors, n_index, n_exclude = check(root)
    for e in errors:
        print(f"ERROR {e}")
    if errors:
        print(f"check_native: {len(errors)} error(s)")
        return 1
    print(f"check_native: OK ({n_index} indexed files, {n_exclude} exclusions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
