from src.utils.number_format import fmt_num


def test_strips_trailing_zeros():
    assert fmt_num("1.0500000000") == "1.05"
    assert fmt_num("0.0300000000") == "0.03"
    assert fmt_num("64502.0000000000") == "64502"
    assert fmt_num("1.0000000000") == "1"


def test_keeps_meaningful_decimals():
    assert fmt_num("1.10005") == "1.10005"
    assert fmt_num("203.4") == "203.4"


def test_no_scientific_notation_for_large_round_numbers():
    assert fmt_num("100000.0000000000") == "100000"


def test_accepts_numbers_and_decimals():
    from decimal import Decimal
    assert fmt_num(1.05) == "1.05"
    assert fmt_num(3) == "3"
    assert fmt_num(Decimal("0.030")) == "0.03"


def test_zero_renders_as_zero_not_empty():
    assert fmt_num(0) == "0"
    assert fmt_num(0.0) == "0"
    assert fmt_num("0.0000000000") == "0"


def test_empty_and_none_and_unparsable():
    assert fmt_num(None) == ""
    assert fmt_num("") == ""
    assert fmt_num("n/a") == "n/a"
