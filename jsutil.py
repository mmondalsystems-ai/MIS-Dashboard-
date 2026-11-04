"""Small helpers that behave like the JavaScript functions the original code used."""
import math
import re
from decimal import Decimal, ROUND_HALF_UP

_FLOAT_RE = re.compile(r"^[+-]?(?:Infinity|\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)")
_INT_RE = re.compile(r"^[+-]?\d+")


def s(v):
    """String(v) for None / numbers."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v == int(v) and abs(v) < 1e15:
        return str(int(v))
    return str(v)


def parse_float(v):
    """JS parseFloat -> float or None (NaN)."""
    m = _FLOAT_RE.match(s(v).lstrip())
    if not m:
        return None
    t = m.group(0)
    if t.endswith("Infinity"):
        return float("-inf") if t.startswith("-") else float("inf")
    return float(t)


def parse_int(v):
    m = _INT_RE.match(s(v).lstrip())
    return int(m.group(0)) if m else None


def to_fixed(x, places=0):
    """JS Number.prototype.toFixed (rounds half up on the exact value)."""
    x = float(x)
    if math.isnan(x):
        return "NaN"
    neg = x < 0
    d = Decimal(abs(x)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    out = format(d, "f")
    return ("-" if neg else "") + out


def name_key(v):
    return s(v).casefold()
