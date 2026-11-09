"""Text clean-up for codes typed by customers and depot staff."""

import re


def normalize_postcode(code: str) -> str:
    """'  ab1 2cd ' -> 'AB12CD'."""
    return re.sub(r"\s+", "", code).upper()


def postcode_area(code: str) -> str:
    """Leading letters of a postcode: 'AB12CD' -> 'AB'."""
    m = re.match(r"[A-Z]+", normalize_postcode(code))
    if not m:
        raise ValueError(f"no area in postcode {code!r}")
    return m.group(0)


def sku_slug(name: str) -> str:
    """'Pallet Wrap, 500mm' -> 'pallet-wrap-500mm'."""
    words = re.findall(r"[a-z0-9]+", name.lower())
    return "-".join(words)


def parse_bool(value: str) -> bool:
    v = value.strip().lower()
    if v in ("y", "yes", "true", "1"):
        return True
    if v in ("n", "no", "false", "0", ""):
        return False
    raise ValueError(f"not a yes/no value: {value!r}")
