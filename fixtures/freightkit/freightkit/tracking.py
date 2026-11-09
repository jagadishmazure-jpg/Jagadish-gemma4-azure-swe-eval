"""Consignment status and delivery dates."""

from datetime import date, timedelta

FLOW = {
    "booked": {"collected", "cancelled"},
    "collected": {"in_transit"},
    "in_transit": {"out_for_delivery", "held"},
    "held": {"in_transit", "returned"},
    "out_for_delivery": {"delivered", "held"},
    "delivered": set(),
    "cancelled": set(),
    "returned": set(),
}


def can_move(current: str, new: str) -> bool:
    if current not in FLOW:
        raise KeyError(current)
    return new in FLOW[current]


def apply_events(events: list[str], start: str = "booked") -> str:
    """Apply status events in order; raise ValueError on an illegal move."""
    state = start
    for e in events:
        if not can_move(state, e):
            raise ValueError(f"cannot go from {state} to {e}")
        state = e
    return state


def add_working_days(start: date, days: int) -> date:
    """Monday to Friday only."""
    d = start
    left = days
    while left > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            left -= 1
    return d


def promised_date(collected: date, priority: str) -> date:
    days = {"timed": 1, "express": 2, "standard": 4}[priority]
    return add_working_days(collected, days)


def is_late(collected: date, delivered: date, priority: str) -> bool:
    return delivered > promised_date(collected, priority)
