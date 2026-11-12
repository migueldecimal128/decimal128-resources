#!/usr/bin/env python3
"""Generate rosetta/expected.tsv: the exact Rosetta counts every port must see.

decimal128-workorder RosettaHarnessAlignmentWorkOrder.md §4.5. One row per
port x runner x source x file:

    <port> <runner> <source> <file> <cases> <skipped>

`cases` is every case the runner parses from the file after the scope filters,
the operator map (<source>.map) and the per-runner exclusions (runner.exclude,
by operator token, or for native by canonical op name; native.exclude, by
file). `skipped` is how many of those the per-line skips
(<source>.skip) drop. A runner passes a file when it reports
passed == cases - skipped, skipped as given, failed == 0.

This is a second, independent parser of the corpora. When it disagrees with a
port, the difference is investigated; neither side is assumed right.

Usage:
    python3 rosetta/gen_expected.py [rosetta dir]          write expected.tsv
    python3 rosetta/gen_expected.py --print [rosetta dir]  print it instead

Standard library only.
"""
import os
import sys

PORTS = ["c", "csharp", "csharp-bid", "go", "java", "kotlin", "python", "rust", "swift", "zig"]
RUNNERS = {"core", "wrapper"}
# Python runs the wrapper variant only (its core is the vendored C).
PORT_RUNNERS = {p: (["wrapper"] if p == "python" else ["core", "wrapper"]) for p in PORTS}
SOURCES = ["dectest", "fptest", "intel", "native"]
MAPPED = ["dectest", "fptest", "intel"]


class DataError(Exception):
    pass


# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------

def read_text(path):
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    if "\r" in text:
        raise DataError(f"{os.path.basename(path)}: CRLF line endings (must be LF)")
    return text


def data_lines(path):
    """(line number, text) for each line that is not blank or a # comment.
    Text keeps its inner tabs; only the line end is stripped."""
    out = []
    for n, line in enumerate(read_text(path).split("\n"), 1):
        if line.strip() and not line.lstrip().startswith("#"):
            out.append((n, line.rstrip(" ")))
    return out


def fields(path, n, line, count):
    parts = line.split("\t", count - 1)
    if len(parts) != count or any(not p.strip() for p in parts):
        raise DataError(f"{os.path.basename(path)}:{n}: expected {count} tab-separated fields, got {line!r}")
    return parts


class Map:
    def __init__(self):
        self.scope = {}      # rule -> value
        self.include = {}    # token -> canonical op
        self.exclude = {}    # token -> reason
        self.errors = []


def load_map(root, source):
    path = os.path.join(root, source + ".map")
    m = Map()
    for n, line in data_lines(path):
        kind = line.split("\t", 1)[0]
        where = f"{source}.map:{n}"
        if kind == "scope":
            _, rule, value = fields(path, n, line, 3)
            m.scope[rule] = value
        elif kind == "include":
            _, tok, op = fields(path, n, line, 3)
            if tok in m.include:
                m.errors.append(f"{where}: {tok} included twice")
            m.include[tok] = op
        elif kind == "exclude":
            _, tok, reason = fields(path, n, line, 3)
            if tok in m.exclude:
                m.errors.append(f"{where}: {tok} excluded twice")
            m.exclude[tok] = reason
        else:
            m.errors.append(f"{where}: unknown entry kind {kind!r}")
    return m


class Skips:
    def __init__(self):
        self.reasons = {}    # tag -> reason
        self.lines = {}      # exact line -> tag
        self.attrs = []      # (tag, set(ops), attribute)
        self.errors = []
        self.entries = []    # (where, kind, key) for the unused-entry check


def load_skips(root, source):
    path = os.path.join(root, source + ".skip")
    s = Skips()
    if not os.path.exists(path):
        return s
    for n, line in data_lines(path):
        where = f"{source}.skip:{n}"
        if line.startswith("="):
            tag, reason = fields(path, n, line[1:], 2)
            if tag in s.reasons:
                s.errors.append(f"{where}: reason tag {tag!r} defined twice")
            s.reasons[tag] = reason
            continue
        kind = line.split("\t", 1)[0]
        if kind == "line":
            _, tag, text = fields(path, n, line, 3)
            text = text.strip()
            if text in s.lines:
                s.errors.append(f"{where}: line skipped twice: {text}")
            s.lines[text] = tag
            s.entries.append((where, "line", text, tag))
        elif kind == "attr":
            _, tag, ops, attr = fields(path, n, line, 4)
            s.attrs.append((tag, set(ops.split(",")), attr))
            s.entries.append((where, "attr", (ops, attr), tag))
        else:
            s.errors.append(f"{where}: unknown entry kind {kind!r}")
    for where, _, _, tag in s.entries:
        if tag not in s.reasons:
            s.errors.append(f"{where}: reason tag {tag!r} is not defined")
    return s


def skip_tag(skips, text, tokens):
    """The reason tag that skips this case, or None."""
    for tag, ops, attr in skips.attrs:
        if tokens and (tokens[0] in ops) and (attr in tokens):
            return tag
    return skips.lines.get(text.strip())


def load_files_index(root):
    path = os.path.join(root, "files.index")
    out = {s: [] for s in MAPPED}
    errors = []
    for n, line in data_lines(path):
        src, name = fields(path, n, line, 2)
        if src not in out:
            errors.append(f"files.index:{n}: unknown source {src!r}")
            continue
        out[src].append(name)
    return out, errors


def scope_entries(path, n, line, count, errors, where_name):
    """Split a whitespace-separated exclusion line (the native.exclude style)."""
    parts = line.split(None, count - 1)
    if len(parts) < count:
        errors.append(f"{where_name}:{n}: too few fields (reason required): {line!r}")
        return None
    return parts


def load_native(root):
    """(index, [(scope, file, reason)], errors) from native.index / native.exclude."""
    errors = []
    index = [t.strip() for _, t in data_lines(os.path.join(root, "native.index"))]
    excl = []
    for n, line in data_lines(os.path.join(root, "native.exclude")):
        parts = line.split(None, 2)
        if len(parts) < 3:
            errors.append(f"native.exclude:{n}: needs <port>[:<runner>] <file> <reason>, got {line!r}")
            continue
        excl.append((n, parts[0], parts[1], parts[2]))
    return index, excl, errors


def load_runner_exclude(root):
    """[(line, port, runner or '', source, token, reason)], errors."""
    path = os.path.join(root, "runner.exclude")
    out, errors = [], []
    for n, line in data_lines(path):
        parts = line.split("\t", 3)
        if len(parts) != 4 or any(not p.strip() for p in parts):
            errors.append(f"runner.exclude:{n}: needs <port>[:<runner>] <source> <token> <reason>, got {line!r}")
            continue
        scope, src, tok, reason = parts
        port, _, runner = scope.partition(":")
        out.append((n, port, runner, src, tok, reason))
    return out, errors


def applies(port, runner, line_port, line_runner):
    return (line_port == port) and ((not line_runner) or (line_runner == runner))


# ---------------------------------------------------------------------------
# Corpus parsers. Each yields (token, line text, tokens) per in-scope case;
# the caller applies the operator map, the exclusions and the skips.
# ---------------------------------------------------------------------------

def strip_comment(line):
    # Rosetta.md §8: `--` starts a comment. (Not quote-aware yet: the two dqBase
    # vectors with `--` inside a quoted operand drop here in every port;
    # RosettaHarnessAlignmentWorkOrder.md Phase 4.)
    i = line.find("--")
    return line[:i] if i >= 0 else line


def _quoted_operands(text, maximum):
    """dectest operands: whitespace-separated, single or double quoted (a doubled
    quote inside is a literal quote)."""
    out = []
    n = len(text)
    i = 0
    while i < n and len(out) < maximum:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        q = text[i]
        if q not in ("'", '"'):
            j = i
            while j < n and not text[j].isspace():
                j += 1
            out.append(text[i:j])
            i = j
            continue
        sb = []
        j = i + 1
        while True:
            if j >= n:
                raise DataError(f"unterminated quoted token: {text[i:]!r}")
            if text[j] == q:
                if j + 1 < n and text[j + 1] == q:
                    sb.append(q)
                    j += 2
                    continue
                break
            sb.append(text[j])
            j += 1
        out.append("".join(sb))
        i = j + 1
    return out


def parse_dectest(text, m):
    precision_ok = m.scope.get("precision", "34")
    roundings = set(m.scope.get("rounding", "").split(","))
    null_operand = m.scope.get("null-operand")
    precision = precision_ok  # as decNumber: a file without a precision: line is not filtered
    rounding = "half_even"
    for line in text.split("\n"):
        raw = strip_comment(line).strip()
        if not raw:
            continue
        if (":" in raw) and ("->" not in raw):
            key, _, value = raw.partition(":")
            key = key.strip().lower()
            value = value.strip().lower()
            if key == "precision":
                precision = value
            elif key == "rounding":
                rounding = value
            continue
        if "->" not in raw:
            continue
        lhs, _, rhs = raw.partition("->")
        lhs_tokens = lhs.split(None, 2)
        if len(lhs_tokens) < 2:
            continue
        token = lhs_tokens[1].lower()
        yield ("token", token)
        if precision != precision_ok:
            continue
        if rounding not in roundings:
            continue
        if len(lhs_tokens) < 3:
            continue
        operands = _quoted_operands(lhs_tokens[2], 3)
        if not operands:
            continue
        if null_operand and (null_operand in operands):
            continue
        if not _quoted_operands(rhs.strip(), 1):
            continue
        yield ("case", token, raw, raw.split())


def parse_fptest(text, m):
    fmt = m.scope.get("format", "d128")
    for line in text.split("\n"):
        tokens = line.split()
        if not tokens or not tokens[0].startswith(fmt):
            continue
        token = tokens[0][len(fmt):]
        yield ("token", token)
        if "->" not in tokens:
            continue
        yield ("case", token, line, tokens)


def _is_flag_register(tok):
    t = tok[2:] if tok.startswith(("0x", "0X")) else tok
    return (1 <= len(t) <= 2) and all(c in "0123456789abcdefABCDEF" for c in t)


def parse_intel(text, m):
    prefix = m.scope.get("prefix", "bid128_")
    for line in text.split("\n"):
        tokens = strip_comment(line).split()
        if not tokens or not tokens[0].startswith(prefix):
            continue
        yield ("token", tokens[0])
        flag_idx = None
        for j in range(len(tokens) - 1, -1, -1):
            if _is_flag_register(tokens[j]):
                flag_idx = j
                break
        # Line shape (Rosetta.md §9): func, rounding, >= 1 operand, result,
        # flag register. A line that doesn't fit is the runner's hard error,
        # not a silent drop; it is counted here so the runner must report it.
        if flag_idx is None or flag_idx < 4 or not tokens[1].isdigit():
            yield ("malformed", tokens[0], line.strip())
            continue
        yield ("case", tokens[0], line.strip(), line.split())


PARSERS = {"dectest": parse_dectest, "fptest": parse_fptest, "intel": parse_intel}
SOURCE_DIRS = {"dectest": "dectest", "fptest": "fptest", "intel": "intel"}


# ---------------------------------------------------------------------------
# Expected counts
# ---------------------------------------------------------------------------

class Corpus:
    """Everything the generator and the checker need, loaded once."""

    def __init__(self, root):
        self.root = root
        self.errors = []
        self.maps = {s: load_map(root, s) for s in MAPPED}
        self.skips = {s: load_skips(root, s) for s in MAPPED}
        self.files, e = load_files_index(root)
        self.errors += e
        self.native_index, self.native_exclude, e = load_native(root)
        self.errors += e
        self.runner_exclude, e = load_runner_exclude(root)
        self.errors += e
        for s in MAPPED:
            self.errors += self.maps[s].errors + self.skips[s].errors
        # Per source: corpus tokens seen, skip entries used, malformed lines.
        self.tokens = {s: set() for s in MAPPED}
        self.used_skips = {s: set() for s in MAPPED}
        self.malformed = []
        # Per (source, file): list of (token, skip tag or None).
        self.cases = {}
        for s in MAPPED:
            for name in self.files[s]:
                path = os.path.join(root, SOURCE_DIRS[s], name)
                if not os.path.isfile(path):
                    continue  # reported by the checker
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read()
                self.cases[(s, name)] = self._cases(s, name, text)
        # Per native file: the op token (canonical op name) of each active line.
        self.native_ops = {}
        self.native_tokens = set()
        for name in self.native_index:
            path = os.path.join(root, "native", name)
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    ops = [line.split()[0] for line in f
                           if line.strip() and not line.strip().startswith("//")]
                self.native_ops[name] = ops
                self.native_tokens.update(ops)

    def _cases(self, source, name, text):
        m = self.maps[source]
        sk = self.skips[source]
        out = []
        for item in PARSERS[source](text, m):
            if item[0] == "token":
                self.tokens[source].add(item[1])
                continue
            if item[0] == "malformed":
                if item[1] in m.include:
                    self.malformed.append(f"{source} {name}: line shape: {item[2]}")
                continue
            _, token, text_line, tokens = item
            if token not in m.include:
                continue  # excluded, or undecided (the checker reports it)
            tag = skip_tag(sk, text_line, tokens)
            if tag is not None:
                for e in sk.entries:
                    if (e[1] == "line" and e[2] == text_line.strip()) or \
                       (e[1] == "attr" and tokens and tokens[0] in e[2][0].split(",") and e[2][1] in tokens):
                        self.used_skips[source].add(e[0])
            out.append((token, tag))
        return out

    def native_files(self, port, runner):
        excluded = {f for _, scope, f, _ in self.native_exclude
                    if applies(port, runner, *scope.partition(":")[::2])}
        return [f for f in self.native_index if f not in excluded]

    def excluded_tokens(self, port, runner, source):
        return {tok for _, p, r, s, tok, _ in self.runner_exclude
                if s == source and applies(port, runner, p, r)}

    def rows(self):
        """[(port, runner, source, file, cases, skipped)], sorted."""
        out = []
        for port in PORTS:
            for runner in PORT_RUNNERS[port]:
                for s in MAPPED:
                    gone = self.excluded_tokens(port, runner, s)
                    for name in self.files[s]:
                        cs = [c for c in self.cases.get((s, name), []) if c[0] not in gone]
                        out.append((port, runner, s, name, len(cs),
                                    sum(1 for c in cs if c[1] is not None)))
                gone = self.excluded_tokens(port, runner, "native")
                for name in self.native_files(port, runner):
                    ops = self.native_ops.get(name, [])
                    out.append((port, runner, "native", name, sum(1 for o in ops if o not in gone), 0))
        return out


HEADER = """# Rosetta expected counts: generated by rosetta/gen_expected.py. Do not edit.
# decimal128-workorder RosettaHarnessAlignmentWorkOrder.md §4.5 and R-3.
#
#   <port> <runner> <source> <file> <cases> <skipped>
#
# A runner passes a file when it reports passed == cases - skipped, the given
# skipped count, and failed == 0. rosetta/check_rosetta.py fails when this file
# differs from a fresh run of the generator.
"""


def render(rows):
    lines = [HEADER]
    for r in rows:
        lines.append("\t".join(str(x) for x in r) + "\n")
    return "".join(lines)


def summary(rows):
    tot = {}
    for port, runner, s, _, cases, skipped in rows:
        k = (port, runner)
        t = tot.setdefault(k, {src: [0, 0] for src in SOURCES})
        t[s][0] += cases
        t[s][1] += skipped
    out = []
    for (port, runner), t in sorted(tot.items()):
        passed = {s: t[s][0] - t[s][1] for s in SOURCES}
        out.append(f"{port:10} {runner:7} " +
                   " ".join(f"{s}={passed[s]}+{t[s][1]}" for s in SOURCES) +
                   f"  total passed={sum(passed.values())} skipped={sum(t[s][1] for s in SOURCES)}")
    return out


def main(argv):
    to_stdout = "--print" in argv
    args = [a for a in argv if a != "--print"]
    root = args[0] if args else os.path.dirname(os.path.abspath(__file__))
    corpus = Corpus(root)
    rows = corpus.rows()
    text = render(rows)
    if to_stdout:
        sys.stdout.write(text)
    else:
        with open(os.path.join(root, "expected.tsv"), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        for line in summary(rows):
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
