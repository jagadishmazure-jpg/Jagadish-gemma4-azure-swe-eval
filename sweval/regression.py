'''Hidden regression suite: behaviour of the whole clean package (like PASS_TO_PASS tests).

The agent never sees these tests. Verification runs them after every patch, so a "fix" that makes
the issue's test pass by breaking something else (for example changing a shared constant) is not
counted as resolved. Every test passes on the clean package; scripts/validate_tasks.py checks that.
'''

SUITE = """
from datetime import date
from decimal import Decimal

import pytest

from freightkit import dock, manifest, rates, text, tracking, units


def test_units_round_trip():
    for x in (0.5, 1, 10, 123.4):
        assert units.lb_to_kg(units.kg_to_lb(x)) == pytest.approx(x)
    assert units.kg_to_lb(10) == pytest.approx(22.0462, abs=1e-4)
    assert units.lb_to_kg(10) == pytest.approx(4.5359, abs=1e-4)
    assert units.KG_PER_LB == pytest.approx(0.45359237)


def test_units_volume_and_dimensional():
    assert units.volume_m3(50, 40, 30) == pytest.approx(0.06)
    with pytest.raises(ValueError):
        units.volume_m3(10, 0, 10)
    with pytest.raises(ValueError):
        units.volume_m3(10, 10, -1)
    assert units.dimensional_weight(50, 40, 30) == pytest.approx(12.0)
    assert units.dimensional_weight(50, 40, 30, divisor=6000) == pytest.approx(10.0)


def test_units_chargeable_weight():
    assert units.chargeable_weight(3, 50, 40, 30) == 12.0
    assert units.chargeable_weight(20, 10, 10, 10) == 20.0
    assert units.chargeable_weight(20.2, 10, 10, 10) == 20.5
    assert units.chargeable_weight(20.5, 10, 10, 10) == 20.5
    assert units.chargeable_weight(20.6, 10, 10, 10) == 21.0


def test_text_helpers():
    assert text.normalize_postcode("  hs1\\t2ab ") == "HS12AB"
    assert text.postcode_area("kw15 1aa") == "KW"
    with pytest.raises(ValueError):
        text.postcode_area("123")
    assert text.sku_slug("  Tape -- Brown (48mm) ") == "tape-brown-48mm"
    assert [text.parse_bool(v) for v in ("Y", " yes ", "TRUE", "1")] == [True] * 4
    assert [text.parse_bool(v) for v in ("n", "No", "false", "0", "")] == [False] * 5
    with pytest.raises(ValueError):
        text.parse_bool("maybe")


def test_rates_zones_and_bands():
    assert rates.zone_for("AB1", "AB9") == 1
    assert rates.zone_for("AB1", "AL9") == 2
    assert rates.zone_for("AB1", "KW1") == 3
    assert rates.price_per_kg(1, 10) == Decimal("1.20")
    assert rates.price_per_kg(1, 10.5) == Decimal("0.95")
    assert rates.price_per_kg(2, 50) == Decimal("1.25")
    assert rates.price_per_kg(3, 51) == Decimal("1.30")


def test_rates_quotes():
    assert str(rates.quote("AB1 2CD", "AB3 4EF", 20)) == "21.28"
    assert str(rates.quote("AB1", "AB2", 1)) == "16.80"
    assert str(rates.quote("AB1", "AL2", 100)) == "100.80"
    assert str(rates.quote("AB1", "AB2", 20, contract_discount=0.1)) == "19.15"
    assert str(rates.quote("AB1", "KW1 1AA", 20)) == "63.08"
    assert str(rates.quote("KW1", "KW2", 20, contract_discount=0.5)) == "35.64"
    for bad in (0, -1):
        with pytest.raises(ValueError):
            rates.quote("AB1", "AB2", bad)
    for bad in (-0.1, 1, 1.5):
        with pytest.raises(ValueError):
            rates.quote("AB1", "AB2", 5, contract_discount=bad)


def test_manifest_parsing():
    c = manifest.parse_line(" X9 ; 2.5 ; ze1 0aa ; EXPRESS ")
    assert (c.cid, c.weight_kg, c.dest, c.priority) == ("X9", 2.5, "ZE10AA", "express")
    assert manifest.parse_line("X1;1;AB1;").priority == "standard"
    for bad in ("X1;1", "X1;1;AB1;fast", "X1;0;AB1", "X1;-2;AB1", "X1;1;AB1;timed;extra"):
        with pytest.raises(ValueError):
            manifest.parse_line(bad)


def test_manifest_load_rules():
    text_ = "# header\\nA1;5;AB1\\n\\n   # note\\nA2;1.25;AB2;timed\\nA1;6;AB1\\n"
    items = manifest.load(text_)
    assert [(c.cid, c.weight_kg) for c in items] == [("A1", 6.0), ("A2", 1.25)]
    assert manifest.total_weight(items) == 7.25
    assert manifest.total_weight([manifest.parse_line("B;0.1;AB1"), manifest.parse_line("C;0.2;AB1")]) == 0.3
    groups = manifest.by_priority(items)
    assert list(groups) == ["standard", "express", "timed"]
    assert [c.cid for c in groups["timed"]] == ["A2"] and groups["express"] == []


def test_dock_slots():
    assert dock.overlaps((60, 120), (119, 200)) and not dock.overlaps((60, 120), (120, 200))
    assert dock.next_free_slot([], 60) == (360, 420)
    assert dock.next_free_slot([(420, 480), (360, 400)], 20) == (400, 420)
    assert dock.next_free_slot([(360, 400)], 30, earliest=300) == (400, 430)
    assert dock.next_free_slot([], 30, earliest=1300) is None
    assert dock.next_free_slot([], 30, earliest=1290) == (1290, 1320)


def test_dock_utilization_and_format():
    assert dock.utilization([]) == 0.0
    assert dock.utilization([(360, 840), (600, 1320)]) == 1.0
    assert dock.utilization([(0, 420), (1300, 1440)]) == round(80 / 960, 4)
    assert dock.utilization([(400, 500), (450, 550)]) == round(150 / 960, 4)
    assert dock.fmt(0) == "00:00" and dock.fmt(545) == "09:05" and dock.fmt(1320) == "22:00"


def test_tracking_flow_rules():
    assert tracking.can_move("booked", "collected") and not tracking.can_move("booked", "delivered")
    with pytest.raises(KeyError):
        tracking.can_move("lost", "held")
    assert tracking.apply_events(["collected", "in_transit", "held", "returned"]) == "returned"
    assert tracking.apply_events([], start="held") == "held"
    with pytest.raises(ValueError):
        tracking.apply_events(["collected", "delivered"])
    assert tracking.apply_events(["cancelled"]) == "cancelled"


def test_tracking_dates():
    fri, mon = date(2026, 3, 6), date(2026, 3, 9)
    assert tracking.add_working_days(fri, 1) == mon
    assert tracking.add_working_days(fri, 0) == fri
    assert tracking.add_working_days(mon, 5) == date(2026, 3, 16)
    assert tracking.promised_date(fri, "timed") == mon
    assert tracking.promised_date(fri, "standard") == date(2026, 3, 12)
    assert not tracking.is_late(fri, date(2026, 3, 10), "express")
    assert tracking.is_late(fri, date(2026, 3, 11), "express")
"""
