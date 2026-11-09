"""Weight and size conversions."""

KG_PER_LB = 0.45359237
DIM_DIVISOR = 5000  # cm^3 per kg for road and air freight


def kg_to_lb(kg: float) -> float:
    return kg / KG_PER_LB


def lb_to_kg(lb: float) -> float:
    return lb * KG_PER_LB


def volume_m3(length_cm: float, width_cm: float, height_cm: float) -> float:
    """Volume of a box in cubic metres."""
    if min(length_cm, width_cm, height_cm) <= 0:
        raise ValueError("dimensions must be positive")
    return length_cm * width_cm * height_cm / 1_000_000


def dimensional_weight(length_cm: float, width_cm: float, height_cm: float, divisor: int = DIM_DIVISOR) -> float:
    """Volumetric weight in kg."""
    return length_cm * width_cm * height_cm / divisor


def chargeable_weight(actual_kg: float, length_cm: float, width_cm: float, height_cm: float) -> float:
    """The weight we bill: the larger of actual and dimensional weight, rounded up to 0.5 kg."""
    w = max(actual_kg, dimensional_weight(length_cm, width_cm, height_cm))
    return _round_up_half(w)


def _round_up_half(x: float) -> float:
    whole = int(x)
    frac = x - whole
    if frac == 0:
        return float(whole)
    return whole + (0.5 if frac <= 0.5 else 1.0)
