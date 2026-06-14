"""Human-friendly numeric formatting for logs and UI.

Display-only: strips trailing zeros so prices/sizes read like the broker chart
(1.0500000000 -> '1.05', 64502.0000000000 -> '64502') instead of padded decimals.
Never used to compute values sent to MT5 — only for rendering.
"""
from decimal import Decimal, InvalidOperation


def fmt_num(value) -> str:
    """Return a clean string for a price/size: no trailing zeros, no sci-notation.

    1.0500000000 -> '1.05', 1.0000000000 -> '1', 64502.0000000000 -> '64502',
    0.0300000000 -> '0.03', 1.10005 -> '1.10005'. None/'' -> '', unparsable -> str(value).
    """
    if value is None or value == "":
        return ""
    try:
        d = Decimal(str(value)).normalize()
    except (InvalidOperation, ValueError, TypeError):
        return str(value)
    return format(d, "f")
