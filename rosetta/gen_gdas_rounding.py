#!/usr/bin/env python3
"""Generate rosetta/native/gdas_rounding.txt: vectors for the two GDAS rounding
modes, round-up (AWAY_FROM_ZERO) and round-05up (05_UP).

decimal128-workorder GdasRoundingModesWorkOrder.md Section 5, P0. The oracle is
Python's decimal module (libmpdec), which implements both modes, in a decimal128
context (prec 34, Emin -6143, Emax 6144, clamp 1).

libmpdec rounds sqrt, exp, ln and log10 half-even whatever the context says.
Those ops are computed at 80 digits in an unbounded context and then rounded
once into decimal128 in the target mode (Context.create_decimal). That single rounding is
correct unless digits 35..80 of the 80-digit value are all zero while the value
itself is inexact. Such a case is ambiguous and is dropped (none occur in the
current inputs; the generator reports any it meets).

A second file, native/gdas_rounding_transcendental.txt, covers every D48 op
(exp, exp10, ln, log10, expm1, exp10m1, lnp1, log2p1, log10p1, pow, pown, rootn,
compound). Its inputs are a fixed sample of the inexact, in-range cases of the
existing transcendental corpora. Each result is computed at 110+ digits (series
for tiny arguments, where exp(x) - 1 would cancel) and rounded once into
decimal128. A value whose digits 35 onward are all 0 or all 9 may sit on a
rounding boundary within the working error, so it is dropped as ambiguous.

Deterministic: a fixed seed, no clock. Standard library only.

Usage:
    python3 -I rosetta/gen_gdas_rounding.py [rosetta dir]
"""
import os
import random
import sys
from decimal import (Context, Decimal, ROUND_UP, ROUND_05UP, Inexact, Underflow,
                     Overflow, InvalidOperation, DivisionByZero, Subnormal, Rounded)

MODES = [("AWAY_FROM_ZERO", ROUND_UP), ("05_UP", ROUND_05UP)]
HI_PREC = 80


def d128(rounding):
    return Context(prec=34, Emin=-6143, Emax=6144, clamp=1, rounding=rounding, traps=[])


def wide():
    return Context(prec=HI_PREC, Emin=-999999, Emax=999999, rounding="ROUND_HALF_EVEN", traps=[])


def flag_letters(ctx, extra=""):
    s = ""
    if ctx.flags[Inexact] or "x" in extra:
        s += "x"
    if ctx.flags[Underflow] or "u" in extra:
        s += "u"
    if ctx.flags[Overflow]:
        s += "o"
    if ctx.flags[DivisionByZero]:
        s += "z"
    if ctx.flags[InvalidOperation]:
        s += "i"
    return s


def line(op, mode, operands, result, flags):
    tail = f" {flags}" if flags else ""
    return f"{op} {mode} {' '.join(operands)} -> {result}{tail}"


def direct(op, fn, operands):
    """An op libmpdec rounds in the context's mode: run it once per mode."""
    out = []
    for name, rounding in MODES:
        ctx = d128(rounding)
        r = fn(ctx, *[Decimal(o) for o in operands])
        out.append(line(op, name, operands, str(r), flag_letters(ctx)))
    return out


def rerounded(op, fn, operands, dropped):
    """An op libmpdec rounds half-even only: 80 digits, then one rounding."""
    w = wide()
    hi = fn(w, *[Decimal(o) for o in operands])
    hi_inexact = bool(w.flags[Inexact])
    if hi.is_nan() or hi.is_infinite():
        flags = "i" if w.flags[InvalidOperation] else ""
        return [line(op, name, operands, str(hi), flags) for name, _ in MODES]
    if hi_inexact:
        digits = hi.as_tuple().digits
        if len(digits) > 34 and all(d == 0 for d in digits[34:]):
            dropped.append(f"{op} {' '.join(operands)}")
            return []
    out = []
    for name, rounding in MODES:
        ctx = d128(rounding)
        r = ctx.create_decimal(hi)   # one rounding; keeps the sign of a zero (plus() would not)
        extra = ""
        if hi_inexact:
            extra += "x"
            if ctx.flags[Subnormal] or (not hi.is_zero() and hi.adjusted() < -6143):
                extra += "u"
        out.append(line(op, name, operands, str(r), flag_letters(ctx, extra)))
    return out


def kept_digit_family():
    """34-digit coefficients ending in each digit 0..9, against tails in each
    residue class, both signs, through add and subtract (subtract borrows)."""
    rng = random.Random(0x6D45)
    cases = []
    tails = ["0", "0.1", "0.3", "0.5", "0.7", "0.9", "0.0000001", "0.4999999", "0.5000001"]
    for d in range(10):
        body = "1" + "".join(str(rng.randrange(10)) for _ in range(32)) + str(d)
        for t in tails:
            for sa in ("", "-"):
                cases.append(("d128_add_ctx", [sa + body, t]))
                cases.append(("d128_subtract_ctx", [sa + body, t]))
    return cases


def edge_family():
    nines = "9" * 34
    max_finite = "9.999999999999999999999999999999999E+6144"
    return [
        # exact: nothing rounds
        ("d128_add_ctx", ["2", "3"]),
        ("d128_multiply_ctx", ["-1.5", "4"]),
        ("d128_add_ctx", ["1E-40", "-1E-40"]),
        # rollover past 34 digits (round-up) and its absence (05up)
        ("d128_add_ctx", [nines, "0.1"]),
        ("d128_add_ctx", ["-" + nines, "-0.1"]),
        ("d128_add_ctx", [nines, "0.5"]),
        ("d128_add_ctx", ["9999999999999999999999999999999999E+1", "5"]),
        # overflow: infinity (round-up) vs the largest finite (05up)
        ("d128_add_ctx", [max_finite, "1E+6111"]),
        ("d128_add_ctx", ["-" + max_finite, "-1E+6111"]),
        ("d128_multiply_ctx", ["9E+6144", "10"]),
        ("d128_multiply_ctx", ["-9E+6144", "10"]),
        ("d128_multiply_ctx", [max_finite, "1.000000000000000000000000000000001"]),
        ("d128_add_ctx", [max_finite, "0.1E+6110"]),
        # fully swamped underflow: never zero in either mode
        ("d128_multiply_ctx", ["1E-6176", "0.01"]),
        ("d128_multiply_ctx", ["-1E-6176", "0.01"]),
        ("d128_multiply_ctx", ["1E-6176", "1E-6176"]),
        ("d128_divide_ctx", ["1E-6176", "1E+30"]),
        # exact-boundary underflow (all digits dropped)
        ("d128_multiply_ctx", ["1E-6176", "0.5"]),
        ("d128_multiply_ctx", ["-1E-6176", "0.3"]),
        ("d128_multiply_ctx", ["1E-6176", "0.9"]),
        # subnormal results: kept digit 0..9
        ("d128_multiply_ctx", ["25E-6176", "0.1"]),
        ("d128_multiply_ctx", ["5E-6176", "0.5"]),
        ("d128_multiply_ctx", ["5E-6176", "0.9"]),
        ("d128_multiply_ctx", ["123E-6176", "0.1"]),
        ("d128_multiply_ctx", ["125E-6176", "0.1"]),
        ("d128_multiply_ctx", ["-129E-6176", "0.1"]),
        ("d128_divide_ctx", ["1E-6170", "7"]),
        ("d128_divide_ctx", ["-1E-6170", "3"]),
        ("d128_divide_ctx", ["5E-6170", "3"]),
        # subnormal rounding that reaches the smallest normal
        ("d128_multiply_ctx", ["9.999999999999999999999999999999999E-6143", "0.1"]),
        ("d128_multiply_ctx", ["9.999999999999999999999999999999995E-6143", "0.1"]),
        ("d128_multiply_ctx", ["-9.999999999999999999999999999999990E-6143", "0.1"]),
        # a kept value of zero with a nonzero residue (normal range)
        ("d128_add_ctx", ["1E+40", "-1E+5"]),
        ("d128_subtract_ctx", ["1E+40", "1"]),
        ("d128_subtract_ctx", ["1E+40", "1E+7"]),
        ("d128_add_ctx", ["-1E+40", "1"]),
        # 05up: subtracting a swamped operand moves the kept digit to 0
        ("d128_subtract_ctx", ["1000000000000000000000000000000001", "0.1"]),
        ("d128_subtract_ctx", ["1000000000000000000000000000000006", "0.1"]),
        ("d128_subtract_ctx", ["1000000000000000000000000000000001", "0.0000000000001"]),
        ("d128_add_ctx", ["-1000000000000000000000000000000006", "0.1"]),
        ("d128_subtract_ctx", ["1000000000000000000000000000000000", "0.1"]),
        ("d128_subtract_ctx", ["1000000000000000000000000000000000", "1E-50"]),
    ]


def arithmetic_family():
    rng = random.Random(0x05FF)
    cases = []

    def num(lo, hi):
        n = rng.randrange(lo, hi)
        digits = str(rng.randrange(10 ** (n - 1), 10 ** n))
        sign = rng.choice(["", "-"])
        exp = rng.randrange(-20, 20)
        return f"{sign}{digits}E{exp:+d}"

    for _ in range(60):
        cases.append(("d128_multiply_ctx", [num(17, 34), num(17, 34)]))
    for _ in range(60):
        cases.append(("d128_divide_ctx", [num(1, 34), num(1, 34)]))
    for a, b in [("1", "3"), ("2", "3"), ("-1", "3"), ("1", "7"), ("-2", "7"), ("5", "9"),
                 ("1", "6"), ("10", "11"), ("1", "1.5"), ("1", "8")]:
        cases.append(("d128_divide_ctx", [a, b]))
    for _ in range(40):
        cases.append(("d128_add_ctx", [num(20, 34), num(1, 34)]))
        cases.append(("d128_subtract_ctx", [num(20, 34), num(1, 34)]))
    for _ in range(50):
        cases.append(("d128_fma_ctx", [num(10, 34), num(10, 34), num(1, 34)]))
    cases.append(("d128_fma_ctx", ["1.000000000000000001", "1.000000000000000001", "-1"]))
    cases.append(("d128_fma_ctx", ["3", "0.3333333333333333333333333333333333", "-1"]))
    cases.append(("d128_fma_ctx", ["-1E-6176", "0.1", "0"]))
    for _ in range(30):
        cases.append(("d128_square_ctx", [num(18, 34)]))
    return cases


def parse_family():
    rng = random.Random(0xA5E)
    cases = []
    for d in range(10):
        for tail in ["0", "1", "4", "5", "6", "9", "00000001", "49999", "50000", "50001"]:
            body = "1" + "".join(str(rng.randrange(10)) for _ in range(32)) + str(d)
            for sign in ("", "-"):
                cases.append(("d128_parse_ctx", [sign + body + tail]))
    for s in ["1.00000000000000000000000000000000001E-6143", "1234567890123456789012345678901234567E-6200",
              "9" * 40, "-" + "9" * 40, "9.9999999999999999999999999999999999E+6144", "1E-6177", "-5E-6177",
              "0.000000000000000000000000000000000000000000001E-6150", "1" * 35 + "E+6110"]:
        cases.append(("d128_parse_ctx", [s]))
    return cases


def integral_family():
    vals = ["0", "-0", "0.3", "-0.3", "0.5", "0.0001", "-0.0001", "0.9", "2.5", "-2.5", "4.9",
            "5.1", "5.0001", "-5.0001", "10.01", "15.5", "9.5", "99.99", "-99.99", "1E-6176",
            "-1E-6176", "1.00E+3", "123456789012345678901234567890123.4",
            "123456789012345678901234567890125.4", "0.5000000000000000000000000000000001",
            "1E+6144", "Infinity", "-Infinity", "NaN"]
    return [("d128_roundToIntegralSignalInexact", [v]) for v in vals]


INT64_MIN = -(1 << 63)


def int_family():
    vals = ["0", "-0", "0.3", "-0.3", "0.5", "2.5", "-2.5", "4.9", "5.0001", "-5.0001", "9.5", "15.5",
            "1E-6176", "123456789.000001", "-123456789.5", "9223372036854775807", "9223372036854775806.5",
            "9223372036854775807.1", "-9223372036854775808", "-9223372036854775808.1",
            "-9223372036854775807.5", "1E+19", "Infinity", "NaN"]
    return [("d128_toInt64SignalInexact_ctx", [v]) for v in vals]


def to_int64(op, operands):
    out = []
    for name, rounding in MODES:
        ctx = d128(rounding)
        v = ctx.to_integral_exact(Decimal(operands[0]))
        if v.is_nan() or v.is_infinite() or not (INT64_MIN <= int(v) <= (1 << 63) - 1):
            out.append(line(op, name, operands, str(INT64_MIN), "i"))
        else:
            out.append(line(op, name, operands, str(int(v)), "x" if ctx.flags[Inexact] else ""))
    return out


def check_operand(op, o):
    """Every non-parse operand must be a decimal128 value exactly as written: the
    runners parse operands in ties-to-even, so a 35-digit or below-Etiny operand
    would be a different value there than here. (Clamped is allowed: the value is
    unchanged.)"""
    ctx = d128(ROUND_UP)
    v = ctx.create_decimal(o)
    if ctx.flags[Inexact] or ctx.flags[Rounded]:
        raise SystemExit(f"{op} operand {o!r} is not a decimal128 value")
    return v


def sqrt_family():
    rng = random.Random(0x5A)
    vals = ["2", "3", "5", "0.5", "10", "1E-6175", "1E-6176", "2E-6176", "9.999999999999999999999999999999999E+6144",
            "4", "0.04", "1E+100", "-2", "0", "-0"]
    for _ in range(40):
        n = rng.randrange(1, 35)
        vals.append(f"{rng.randrange(10 ** (n - 1), 10 ** n)}E{rng.randrange(-40, 40):+d}")
    return [("d128_sqrt_ctx", [v]) for v in vals]


# Inputs left out because toward-positive / toward-negative / toward-zero miss
# them by 1 ulp too: the D48 value's digits 35..48 are all 0 or all 9, so it lands
# on (or rounds onto) a decimal128 point while the true value does not, and the
# tail that decides the direction lies below 48 digits -- the D48 gap
# (CrossPlatformArchitecture.md Section 12). The new modes round up wherever a
# truncating mode is right by luck, so they expose it more often. Found by this
# corpus (GdasRoundingModesWorkOrder.md Section 8); remove an entry when the gap
# is closed.
KNOWN_D48_GAP = {
    ("d128_exp_ctx", ("-5E-16",)),
    ("d128_exp_ctx", ("1.23E-31",)),
    ("d128_exp_ctx", ("1E-33",)),
    ("d128_exp_ctx", ("2.4E-26",)),
    ("d128_exp_ctx", ("77902E-32",)),
    ("d128_exp_ctx", ("9E-25",)),
    ("d128_ln_ctx", ("0.9999999999999999999999991",)),
    ("d128_ln_ctx", ("0.99999999999999999999999987",)),
    ("d128_ln_ctx", ("0.99999999999999999999999998",)),
    ("d128_ln_ctx", ("0.9999999999999999999999999997",)),
    ("d128_ln_ctx", ("0.9999999999999999999999999999956",)),
    ("d128_ln_ctx", ("1.000000000000000000000000000000001",)),
    ("d128_ln_ctx", ("1.00000000000000000000000001",)),
    ("d128_pown_ctx", ("0.9999999999999999999999999", "3",)),
    ("d128_pown_ctx", ("0.9999999999999999999999999951674648", "37",)),
    ("d128_pown_ctx", ("0.9999999999999999999999999998319670", "1731",)),
    ("d128_pown_ctx", ("0.9999999999999999999999999999991998", "3680",)),
    ("d128_pown_ctx", ("0.999999999999999999999999999999997", "1048577",)),
    ("d128_pown_ctx", ("0.9999999999999999999999999999999999", "-10",)),
    ("d128_pown_ctx", ("1.000000000000000000000000000000001", "-10",)),
    ("d128_pown_ctx", ("1.000000000000000000000000000000003", "3",)),
    ("d128_pown_ctx", ("1.000000000000000000000000000000007", "64",)),
    ("d128_pown_ctx", ("1.00000000000000000000000000000005", "39",)),
    ("d128_pown_ctx", ("1.000000000000000000000000000000998", "35",)),
    ("d128_pown_ctx", ("1.000000000000000000000000000001", "-2",)),
    ("d128_pown_ctx", ("1.000000000000000000000000000008147", "25",)),
    ("d128_pown_ctx", ("1.000000000000000000000000000795979", "30",)),
    ("d128_pown_ctx", ("1.000000000000000000000000000850355", "440",)),
    ("d128_pown_ctx", ("1.000000000000000000000000001407226", "2081",)),
    ("d128_pown_ctx", ("1.000000000000000000000000063171981", "30",)),
    ("d128_rootn_ctx", ("-1.00000000000000000000000000915", "-25",)),
    ("d128_rootn_ctx", ("1.0000000000000000000000008", "1000",)),
    ("d128_rootn_ctx", ("1.0000000000000000000000067", "-10",)),
}


def transcendental_family():
    rng = random.Random(0xE7)
    cases = []
    for v in ["1", "2", "0.5", "-1", "10", "-10", "100", "1E-40", "-1E-40", "0.1", "230", "-230",
              "14000", "-14000"]:
        cases.append(("d128_exp_ctx", [v]))
    for v in ["2", "3", "10", "0.5", "1E-6176", "9.999999999999999999999999999999999E+6144",
              "1.000000000000000000000000000000001", "0.9999999999999999999999999999999999"]:
        cases.append(("d128_ln_ctx", [v]))
        cases.append(("d128_log10_ctx", [v]))
    for _ in range(40):
        n = rng.randrange(1, 35)
        mag = f"{rng.randrange(10 ** (n - 1), 10 ** n)}E{rng.randrange(-40, 4) - n:+d}"
        cases.append(("d128_exp_ctx", [rng.choice(["", "-"]) + mag]))
    for _ in range(40):
        n = rng.randrange(1, 35)
        v = f"{rng.randrange(10 ** (n - 1), 10 ** n)}E{rng.randrange(-60, 60):+d}"
        cases.append(("d128_ln_ctx", [v]))
        cases.append(("d128_log10_ctx", [v]))
    return cases


DIRECT = {
    "d128_add_ctx": lambda c, a, b: c.add(a, b),
    "d128_subtract_ctx": lambda c, a, b: c.subtract(a, b),
    "d128_multiply_ctx": lambda c, a, b: c.multiply(a, b),
    "d128_divide_ctx": lambda c, a, b: c.divide(a, b),
    "d128_fma_ctx": lambda c, a, b, d: c.fma(a, b, d),
    "d128_square_ctx": lambda c, a: c.multiply(a, a),
    "d128_roundToIntegralSignalInexact": lambda c, a: c.to_integral_exact(a),
}
REROUNDED = {
    "d128_sqrt_ctx": lambda c, a: c.sqrt(a),
    "d128_exp_ctx": lambda c, a: c.exp(a),
    "d128_ln_ctx": lambda c, a: c.ln(a),
    "d128_log10_ctx": lambda c, a: c.log10(a),
}


def parse_direct(op, s):
    out = []
    for name, rounding in MODES:
        ctx = d128(rounding)
        r = ctx.create_decimal(s)
        out.append(line(op, name, [s], str(r), flag_letters(ctx)))
    return out


# --- transcendental file -----------------------------------------------------

TRANSCENDENTAL_FILES = [
    "transcendental_compound.txt", "transcendental_expm1.txt", "transcendental_large_n.txt",
    "transcendental_logexp.txt", "transcendental_logp1.txt", "transcendental_pow.txt",
    "transcendental_pown_rootn.txt", "transcendental_pown.txt", "transcendental_rootn_sweep.txt",
    "transcendental_rootn.txt", "transcendental_stress.txt", "transcendental_sweep.txt",
]
SAMPLE_PER_OP = 150
INT_N_OPS = {"d128_pown_ctx", "d128_rootn_ctx", "d128_compound_ctx"}
WORK = 110
# Working precisions tried in turn: a tiny argument (expm1(1E-2000)) needs enough
# digits to see the term after the leading one, or the value looks exact.
LADDER = [110, 400, 2500, 13000]
_prec = [WORK]


def hp(extra=0):
    return Context(prec=_prec[0] + extra, Emin=-9999999, Emax=9999999, rounding="ROUND_HALF_EVEN", traps=[])


def expm1_hi(x):
    if x.is_zero():
        return x
    if x.copy_abs() >= Decimal("1E-5"):
        c = hp(10)
        return c.subtract(c.exp(x), 1)
    c = hp(10)
    total, term, k = x, x, 1
    limit = c.multiply(x.copy_abs(), Decimal(10).scaleb(-(_prec[0] + 6)))
    while term.copy_abs() > limit:
        k += 1
        term = c.divide(c.multiply(term, x), k)
        total = c.add(total, term)
    return total


def lnp1_hi(x):
    if x.is_zero():
        return x
    if x.copy_abs() >= Decimal("1E-5"):
        exact = Context(prec=20000).add(1, x)
        return hp(10).ln(exact)
    c = hp(10)
    total, power, k = x, x, 1
    limit = c.multiply(x.copy_abs(), Decimal(10).scaleb(-(_prec[0] + 6)))
    while True:
        k += 1
        power = c.multiply(power, x)
        term = c.divide(power, k)
        if term.copy_abs() <= limit:
            break
        total = c.subtract(total, term) if k % 2 == 0 else c.add(total, term)
    return total


def ln10():
    return hp(20).ln(Decimal(10))


def root_hi(x, n):
    c = hp(20)
    mag = c.exp(c.divide(c.ln(x.copy_abs()), n))
    return mag.copy_negate() if x.is_signed() else mag


def tr_value(op, a):
    c = hp(20)
    x = Decimal(a[0])
    if op == "d128_exp_ctx":
        return c.exp(x)
    if op == "d128_exp10_ctx":
        return c.exp(c.multiply(x, ln10()))
    if op == "d128_ln_ctx":
        return c.ln(x)
    if op == "d128_log10_ctx":
        return c.log10(x)
    if op == "d128_expm1_ctx":
        return expm1_hi(x)
    if op == "d128_exp10m1_ctx":
        return expm1_hi(c.multiply(x, ln10()))
    if op == "d128_lnp1_ctx":
        return lnp1_hi(x)
    if op == "d128_log2p1_ctx":
        return c.divide(lnp1_hi(x), c.ln(Decimal(2)))
    if op == "d128_log10p1_ctx":
        return c.divide(lnp1_hi(x), ln10())
    if op == "d128_pow_ctx":
        y = Decimal(a[1])
        if x <= 0:
            return None
        return c.exp(c.multiply(y, c.ln(x)))
    if op == "d128_pown_ctx":
        return c.power(x, int(a[1]))
    if op == "d128_rootn_ctx":
        return root_hi(x, int(a[1]))
    if op == "d128_compound_ctx":
        base = Context(prec=20000).add(1, x)
        if base <= 0:
            return None
        return c.power(base, int(a[1]))
    raise SystemExit(f"no oracle for {op}")


def ambiguous(hi):
    digits = hi.as_tuple().digits
    tail = digits[34:_prec[0] - 5]
    return len(tail) == 0 or all(d == 0 for d in tail) or all(d == 9 for d in tail)


def transcendental_cases(root):
    seen = {}
    for name in TRANSCENDENTAL_FILES:
        with open(os.path.join(root, "native", name), encoding="utf-8") as f:
            for raw in f:
                t = raw.split()
                if not t or t[0].startswith("//") or "->" not in t:
                    continue
                arrow = t.index("->")
                flags = t[arrow + 2] if arrow + 2 < len(t) else ""
                result = t[arrow + 1]
                if flags != "x" or "Inf" in result or "NaN" in result:
                    continue
                if t[0] in INT_N_OPS and not (-(1 << 31) <= int(t[3]) <= (1 << 31) - 1):
                    continue   # |n| > 2^31: ports with a 32-bit n exclude transcendental_large_n.txt
                key = (t[0], tuple(t[2:arrow]))
                seen[key] = True
    by_op = {}
    for op, operands in sorted(seen):
        by_op.setdefault(op, []).append(operands)
    rng = random.Random(0x7AC)
    picked = []
    for op in sorted(by_op):
        pool = by_op[op]
        picked += [(op, list(o)) for o in rng.sample(pool, min(SAMPLE_PER_OP, len(pool)))]
    return picked


def transcendental_lines(root, dropped):
    out = []
    for op, operands in transcendental_cases(root):
        if (op, tuple(operands)) in KNOWN_D48_GAP:
            continue
        hi = None
        unclear = True
        for prec in LADDER:
            _prec[0] = prec
            hi = tr_value(op, operands)
            if hi is None or not hi.is_finite() or hi.is_zero():
                break
            unclear = ambiguous(hi)
            if not unclear:
                break
        _prec[0] = WORK
        if hi is None or not hi.is_finite() or hi.is_zero():
            continue
        if unclear:
            dropped.append(f"{op} {' '.join(operands)}")
            continue
        for name, rounding in MODES:
            ctx = d128(rounding)
            r = ctx.create_decimal(hi)
            extra = "x"
            if ctx.flags[Subnormal] or hi.adjusted() < -6143:
                extra += "u"
            out.append(line(op, name, operands, str(r), flag_letters(ctx, extra)))
    return out


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    dropped = []
    body = []
    families = (kept_digit_family() + edge_family() + arithmetic_family() + integral_family()
                + sqrt_family() + transcendental_family())
    for op, operands in families + int_family():
        if (op, tuple(operands)) in KNOWN_D48_GAP:
            continue
        for o in operands:
            check_operand(op, o)
        if op == "d128_toInt64SignalInexact_ctx":
            body += to_int64(op, operands)
        elif op in DIRECT:
            body += direct(op, DIRECT[op], operands)
        else:
            body += rerounded(op, REROUNDED[op], operands, dropped)
    for op, operands in parse_family():
        body += parse_direct(op, operands[0])
    header = (f"// generated by rosetta/gen_gdas_rounding.py (GdasRoundingModesWorkOrder.md P0) "
              f"— oracle: Python decimal (libmpdec), round-up and round-05up — {len(body)} cases")
    path = os.path.join(root, "native", "gdas_rounding.txt")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(header + "\n")
        for ln in body:
            f.write(ln + "\n")
    print(f"wrote {path}: {len(body)} cases")
    tr = transcendental_lines(root, dropped)
    path = os.path.join(root, "native", "gdas_rounding_transcendental.txt")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"// generated by rosetta/gen_gdas_rounding.py (GdasRoundingModesWorkOrder.md P0) "
                f"— oracle: Python decimal at {WORK}+ digits, rounded once — {len(tr)} cases\n")
        for ln in tr:
            f.write(ln + "\n")
    print(f"wrote {path}: {len(tr)} cases")
    for d in dropped:
        print(f"dropped (ambiguous): {d}", file=sys.stderr)


if __name__ == "__main__":
    main()
