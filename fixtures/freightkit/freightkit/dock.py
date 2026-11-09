"""Loading-dock slot booking. Times are minutes after midnight; a slot is [start, end)."""

OPEN, CLOSE = 6 * 60, 22 * 60


def overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def next_free_slot(bookings: list[tuple[int, int]], duration: int, earliest: int = OPEN) -> tuple[int, int] | None:
    """First slot of `duration` minutes at or after `earliest` that fits before CLOSE."""
    start = max(earliest, OPEN)
    for b in sorted(bookings):
        if start + duration <= b[0]:
            break
        start = max(start, b[1])
    if start + duration > CLOSE:
        return None
    return (start, start + duration)


def utilization(bookings: list[tuple[int, int]]) -> float:
    """Share of opening hours that are booked (overlaps counted once)."""
    merged: list[list[int]] = []
    for s, e in sorted(bookings):
        s, e = max(s, OPEN), min(e, CLOSE)
        if s >= e:
            continue
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return round(sum(e - s for s, e in merged) / (CLOSE - OPEN), 4)


def fmt(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
