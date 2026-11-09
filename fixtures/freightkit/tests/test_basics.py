from datetime import date

from freightkit import dock, manifest, rates, text, tracking, units


def test_units():
    assert round(units.kg_to_lb(1), 3) == 2.205
    assert units.volume_m3(100, 100, 100) == 1.0


def test_text():
    assert text.normalize_postcode(" ab1 2cd ") == "AB12CD"
    assert text.sku_slug("Pallet Wrap, 500mm") == "pallet-wrap-500mm"


def test_quote_same_area():
    assert str(rates.quote("AB1 2CD", "AB3 4EF", 20)) == "21.28"


def test_manifest_load():
    items = manifest.load("A1;5;ab1 2cd\nA2;7;AB3 4EF;express\n")
    assert [c.cid for c in items] == ["A1", "A2"] and items[1].priority == "express"


def test_dock_free_slot():
    assert dock.next_free_slot([(360, 420)], 30) == (420, 450)


def test_tracking_flow():
    assert tracking.apply_events(["collected", "in_transit", "out_for_delivery", "delivered"]) == "delivered"
    assert tracking.promised_date(date(2026, 3, 6), "express") == date(2026, 3, 10)
