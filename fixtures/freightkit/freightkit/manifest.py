"""Load manifests: one consignment per line, 'ID;weight_kg;dest_postcode;priority'."""

from dataclasses import dataclass

from .text import normalize_postcode

PRIORITIES = ("standard", "express", "timed")


@dataclass(frozen=True)
class Consignment:
    cid: str
    weight_kg: float
    dest: str
    priority: str = "standard"


def parse_line(line: str) -> Consignment:
    parts = [p.strip() for p in line.split(";")]
    if len(parts) not in (3, 4):
        raise ValueError(f"expected 3 or 4 fields: {line!r}")
    cid, weight, dest = parts[:3]
    priority = parts[3].lower() if len(parts) == 4 and parts[3] else "standard"
    if priority not in PRIORITIES:
        raise ValueError(f"unknown priority {priority!r}")
    w = float(weight)
    if w <= 0:
        raise ValueError("weight must be positive")
    return Consignment(cid, w, normalize_postcode(dest), priority)


def load(text: str) -> list[Consignment]:
    """Parse a manifest. Blank lines and lines starting with '#' are skipped.
    A repeated ID replaces the earlier line (corrections are appended)."""
    by_id: dict[str, Consignment] = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        c = parse_line(line)
        by_id[c.cid] = c
    return list(by_id.values())


def total_weight(items: list[Consignment]) -> float:
    return round(sum(c.weight_kg for c in items), 3)


def by_priority(items: list[Consignment]) -> dict[str, list[Consignment]]:
    out: dict[str, list[Consignment]] = {p: [] for p in PRIORITIES}
    for c in items:
        out[c.priority].append(c)
    return out
