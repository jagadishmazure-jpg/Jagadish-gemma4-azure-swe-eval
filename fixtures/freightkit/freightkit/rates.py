"""Price quotes for road freight."""

from decimal import ROUND_HALF_UP, Decimal

from .text import postcode_area

# (max chargeable kg, price per kg) by zone; the last band has no upper limit
BANDS = {
    1: [(10, Decimal("1.20")), (50, Decimal("0.95")), (None, Decimal("0.70"))],
    2: [(10, Decimal("1.60")), (50, Decimal("1.25")), (None, Decimal("0.90"))],
    3: [(10, Decimal("2.10")), (50, Decimal("1.70")), (None, Decimal("1.30"))],
}
MINIMUM_CHARGE = Decimal("15.00")
FUEL_SURCHARGE = Decimal("0.12")
REMOTE_AREAS = {"HS", "KW", "ZE"}
REMOTE_FEE = Decimal("25.00")


def zone_for(origin: str, dest: str) -> int:
    """1 = same area, 2 = same first letter, 3 = anywhere else."""
    a, b = postcode_area(origin), postcode_area(dest)
    if a == b:
        return 1
    if a[0] == b[0]:
        return 2
    return 3


def price_per_kg(zone: int, kg: float) -> Decimal:
    for limit, price in BANDS[zone]:
        if limit is None or kg <= limit:
            return price
    raise AssertionError("unreachable")


def quote(origin: str, dest: str, kg: float, contract_discount: float = 0.0) -> Decimal:
    """Total price in pounds, rounded half-up to pennies.

    Order: band price x weight, minimum charge, discount, fuel surcharge, then the remote-area fee
    (which is never discounted).
    """
    if kg <= 0:
        raise ValueError("weight must be positive")
    if not 0 <= contract_discount < 1:
        raise ValueError("discount must be in [0, 1)")
    zone = zone_for(origin, dest)
    price = price_per_kg(zone, kg) * Decimal(str(kg))
    price = max(price, MINIMUM_CHARGE)
    price = price * (1 - Decimal(str(contract_discount)))
    price = price * (1 + FUEL_SURCHARGE)
    if postcode_area(dest) in REMOTE_AREAS:
        price += REMOTE_FEE
    return price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
