"""The task suite: real bugs planted in freightkit, each with an issue report and hidden tests.

Each task starts from the clean fixture (fixtures/freightkit), applies `edits` (correct text ->
buggy text) and commits the result. The agent sees the buggy repository and the issue only. Hidden
tests are added after the agent submits; the task is resolved when they pass. Every task is checked
by `scripts/validate_tasks.py`: hidden tests fail on the buggy repo and pass on the clean one.

kind: "named"   the issue names the function to fix
      "symptom" the issue describes behaviour only
      "multi"   the fix needs edits in two places
"""

from __future__ import annotations

import hashlib

T = "from datetime import date\n\nimport pytest\n\nfrom freightkit import dock, manifest, rates, text, tracking, units\n\n\n"

TASKS: list[dict] = [
    # ---- units -------------------------------------------------------------------------------------
    {"id": "units-kg-to-lb", "kind": "named",
     "edits": [("freightkit/units.py", "return kg / KG_PER_LB", "return kg * KG_PER_LB")],
     "issue": "kg_to_lb(10) returns 4.54. Ten kilograms is about 22.05 pounds.",
     "tests": T + "def test_kg_to_lb():\n    assert round(units.kg_to_lb(10), 2) == 22.05\n"},
    {"id": "units-lb-to-kg", "kind": "named",
     "edits": [("freightkit/units.py", "return lb * KG_PER_LB", "return lb / KG_PER_LB")],
     "issue": "lb_to_kg(100) gives 220.46. 100 lb should be 45.36 kg.",
     "tests": T + "def test_lb_to_kg():\n    assert round(units.lb_to_kg(100), 2) == 45.36\n"},
    {"id": "units-zero-dimension", "kind": "symptom",
     "edits": [("freightkit/units.py", "if min(length_cm, width_cm, height_cm) <= 0:",
                "if min(length_cm, width_cm, height_cm) < 0:")],
     "issue": "A box entered as 0 x 40 x 40 cm gets a volume of 0.0 m3 and is booked. A zero dimension "
              "must be rejected with ValueError, the same as a negative one.",
     "tests": T + "def test_zero_dimension_rejected():\n    with pytest.raises(ValueError):\n"
                  "        units.volume_m3(0, 40, 40)\n"},
    {"id": "units-dim-divisor", "kind": "symptom",
     "edits": [("freightkit/units.py", "divisor: int = DIM_DIVISOR", "divisor: int = 6000")],
     "issue": "Volumetric weights look about 17% too low. A 50 x 50 x 40 cm box should weigh 20 kg "
              "volumetrically (our divisor is 5000 cm3 per kg) but we get 16.67.",
     "tests": T + "def test_dimensional_weight_uses_5000():\n"
                  "    assert units.dimensional_weight(50, 50, 40) == 20\n"},
    {"id": "units-chargeable-max", "kind": "symptom",
     "edits": [("freightkit/units.py", "w = max(actual_kg, dimensional_weight", "w = min(actual_kg, dimensional_weight")],
     "issue": "A light but bulky parcel (2 kg, 60 x 40 x 40 cm) is billed at 2 kg. We bill the larger of "
              "actual and volumetric weight, so it should be 19.5 kg.",
     "tests": T + "def test_bulky_parcel_billed_on_volume():\n"
                  "    assert units.chargeable_weight(2, 60, 40, 40) == 19.5\n"
                  "    assert units.chargeable_weight(30, 10, 10, 10) == 30\n"},
    {"id": "units-half-kg-rounding", "kind": "symptom",
     "edits": [("freightkit/units.py", "(0.5 if frac <= 0.5 else 1.0)", "(0.5 if frac < 0.5 else 1.0)")],
     "issue": "A parcel weighing exactly 10.5 kg is billed as 11 kg. We round UP to the next half "
              "kilogram, so 10.5 should stay 10.5 (and 10.2 becomes 10.5).",
     "tests": T + "def test_exact_half_kg_not_rounded_up():\n"
                  "    assert units.chargeable_weight(10.5, 1, 1, 1) == 10.5\n"
                  "    assert units.chargeable_weight(10.2, 1, 1, 1) == 10.5\n"},
    # ---- text --------------------------------------------------------------------------------------
    {"id": "text-postcode-upper", "kind": "symptom",
     "edits": [("freightkit/text.py", 'return re.sub(r"\\s+", "", code).upper()',
                'return re.sub(r"\\s+", "", code).lower()')],
     "issue": "Quotes fail with \"no area in postcode\" for every address since the last release. "
              "Postcodes should be stored in capitals without spaces, e.g. ' ab1 2cd ' -> 'AB12CD'.",
     "tests": T + "def test_postcode_normalised_upper():\n"
                  "    assert text.normalize_postcode(' ab1 2cd ') == 'AB12CD'\n"
                  "    assert text.postcode_area('ab1 2cd') == 'AB'\n"},
    {"id": "text-postcode-inner-space", "kind": "named",
     "edits": [("freightkit/text.py", 'return re.sub(r"\\s+", "", code).upper()', "return code.strip().upper()")],
     "issue": "normalize_postcode('AB1 2CD') returns 'AB1 2CD'. All whitespace must be removed, "
              "including inside the code.",
     "tests": T + "def test_inner_space_removed():\n    assert text.normalize_postcode('AB1 2CD') == 'AB12CD'\n"
                  "    assert text.normalize_postcode('ab1\\t2cd') == 'AB12CD'\n"},
    {"id": "text-sku-digits", "kind": "named",
     "edits": [("freightkit/text.py", 're.findall(r"[a-z0-9]+", name.lower())', 're.findall(r"[a-z]+", name.lower())')],
     "issue": "sku_slug('Pallet Wrap, 500mm') returns 'pallet-wrap-mm'. Digits must be kept.",
     "tests": T + "def test_sku_keeps_digits():\n    assert text.sku_slug('Pallet Wrap, 500mm') == 'pallet-wrap-500mm'\n"
                  "    assert text.sku_slug('Strap 2') == 'strap-2'\n"},
    {"id": "text-bool-digits", "kind": "symptom",
     "edits": [("freightkit/text.py", 'if v in ("y", "yes", "true", "1"):', 'if v in ("y", "yes", "true"):'),
               ("freightkit/text.py", 'if v in ("n", "no", "false", "0", ""):', 'if v in ("n", "no", "false", ""):')],
     "issue": "Spreadsheet exports use 1 and 0 for yes/no columns, and importing them fails with "
              "\"not a yes/no value: '1'\".",
     "tests": T + "def test_one_and_zero():\n    assert text.parse_bool('1') is True\n    assert text.parse_bool(' 0 ') is False\n"},
    {"id": "text-postcode-area", "kind": "named",
     "edits": [("freightkit/text.py", 'm = re.match(r"[A-Z]+", normalize_postcode(code))',
                'm = re.match(r"[A-Z]", normalize_postcode(code))')],
     "issue": "postcode_area('AB12CD') returns 'A'. The area is all leading letters: 'AB'.",
     "tests": T + "def test_area_is_all_letters():\n    assert text.postcode_area('AB12CD') == 'AB'\n"
                  "    assert text.postcode_area('g1 1aa') == 'G'\n"},
    # ---- rates -------------------------------------------------------------------------------------
    {"id": "rates-zone-first-letter", "kind": "symptom",
     "edits": [("freightkit/rates.py", "if a[0] == b[0]:", "if a[-1] == b[-1]:")],
     "issue": "A job from AB (Aberdeen) to AL (St Albans) is priced as zone 3. Areas that share a first "
              "letter are zone 2.",
     "tests": T + "def test_same_first_letter_is_zone_2():\n    assert rates.zone_for('AB1 2CD', 'AL1 1AA') == 2\n"
                  "    assert rates.zone_for('AB1 2CD', 'CB1 1AA') == 3\n"},
    {"id": "rates-band-inclusive", "kind": "symptom",
     "edits": [("freightkit/rates.py", "if limit is None or kg <= limit:", "if limit is None or kg < limit:")],
     "issue": "A 10 kg parcel in zone 1 is charged 0.95 per kg. Band limits are inclusive: up to and "
              "including 10 kg is the 1.20 band.",
     "tests": T + "from decimal import Decimal\n\n\ndef test_band_limit_inclusive():\n"
                  "    assert rates.price_per_kg(1, 10) == Decimal('1.20')\n"
                  "    assert rates.price_per_kg(2, 50) == Decimal('1.25')\n"},
    {"id": "rates-minimum-charge", "kind": "symptom",
     "edits": [("freightkit/rates.py", "price = max(price, MINIMUM_CHARGE)", "price = min(price, MINIMUM_CHARGE)")],
     "issue": "Every quote above the minimum now comes out at 16.80 (15.00 plus fuel), even for 200 kg. "
              "The 15.00 minimum should only lift small jobs.",
     "tests": T + "def test_minimum_only_lifts_small_jobs():\n"
                  "    assert str(rates.quote('AB1 2CD', 'AB3 4EF', 200)) == '156.80'\n"
                  "    assert str(rates.quote('AB1 2CD', 'AB3 4EF', 1)) == '16.80'\n"},
    {"id": "rates-remote-fee-discounted", "kind": "multi",
     "edits": [("freightkit/rates.py",
                ("    price = price * (1 - Decimal(str(contract_discount)))\n    price = price * (1 + FUEL_SURCHARGE)\n"
                 "    if postcode_area(dest) in REMOTE_AREAS:\n        price += REMOTE_FEE\n"),
                ("    if postcode_area(dest) in REMOTE_AREAS:\n        price += REMOTE_FEE\n"
                 "    price = price * (1 - Decimal(str(contract_discount)))\n    price = price * (1 + FUEL_SURCHARGE)\n"))],
     "issue": "Contract customers get their discount and fuel surcharge applied to the 25.00 remote-area "
              "fee. The fee is fixed: it is added last and never discounted or surcharged.",
     "tests": T + "def test_remote_fee_added_last():\n"
                  "    assert str(rates.quote('ZE1 0AA', 'ZE2 9XX', 20, 0.5)) == '35.64'\n"},
    {"id": "rates-half-up", "kind": "multi",
     "edits": [("freightkit/rates.py", "from decimal import ROUND_HALF_UP, Decimal",
                "from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal"),
               ("freightkit/rates.py", 'rounding=ROUND_HALF_UP)', 'rounding=ROUND_DOWN)')],
     "issue": "Quotes are a penny short when the third decimal is 5 or more (finance found 20.22 where "
              "the rate card gives 20.23 for 19.01 kg in zone 1). Round half-up to pennies.",
     "tests": T + "def test_half_up():\n    assert str(rates.quote('AB1 2CD', 'AB3 4EF', 19.01)) == '20.23'\n"},
    {"id": "rates-fuel-rate", "kind": "named",
     "edits": [("freightkit/rates.py", 'FUEL_SURCHARGE = Decimal("0.12")', 'FUEL_SURCHARGE = Decimal("0.21")')],
     "issue": "Quotes are about 8% too high. The rate card fuel surcharge is 12%.",
     "tests": T + "def test_fuel_twelve_percent():\n    assert str(rates.quote('AB1 2CD', 'AB3 4EF', 20)) == '21.28'\n"},
    {"id": "rates-remote-dest-only", "kind": "symptom",
     "edits": [("freightkit/rates.py", "if postcode_area(dest) in REMOTE_AREAS:", "if postcode_area(origin) in REMOTE_AREAS:")],
     "issue": "Collections FROM Shetland (ZE) to Aberdeen are charged the remote-area fee, and deliveries "
              "TO Shetland are not. The fee depends on where we deliver.",
     "tests": T + "def test_fee_on_destination():\n"
                  "    assert str(rates.quote('ZE1 0AA', 'AB1 2CD', 20)) == '38.08'\n"
                  "    assert str(rates.quote('AB1 2CD', 'ZE1 0AA', 20)) == '63.08'\n"},
    {"id": "rates-full-discount", "kind": "named",
     "edits": [("freightkit/rates.py", "if not 0 <= contract_discount < 1:", "if not 0 <= contract_discount <= 1:")],
     "issue": "quote(..., contract_discount=1.0) is accepted and returns 0.00. Discounts must be below 1; "
              "1.0 should raise ValueError.",
     "tests": T + "def test_full_discount_rejected():\n    with pytest.raises(ValueError):\n"
                  "        rates.quote('AB1 2CD', 'AB3 4EF', 20, 1.0)\n"},
    # ---- manifest ----------------------------------------------------------------------------------
    {"id": "manifest-priority-case", "kind": "symptom",
     "edits": [("freightkit/manifest.py", 'priority = parts[3].lower() if len(parts) == 4 and parts[3] else "standard"',
                'priority = parts[3] if len(parts) == 4 and parts[3] else "standard"')],
     "issue": "Depot files with 'EXPRESS' in the priority column are rejected with unknown priority "
              "'EXPRESS'. Priority should be case-insensitive.",
     "tests": T + "def test_priority_case_insensitive():\n"
                  "    assert manifest.parse_line('A1;5;AB1;EXPRESS').priority == 'express'\n"},
    {"id": "manifest-indented-comment", "kind": "symptom",
     "edits": [("freightkit/manifest.py", 'if not line.strip() or line.lstrip().startswith("#"):',
                'if not line.strip() or line.startswith("#"):')],
     "issue": "A manifest with an indented comment line ('   # late additions') fails to load with "
              "'expected 3 or 4 fields'. Comment lines may be indented.",
     "tests": T + "def test_indented_comment_skipped():\n"
                  "    assert len(manifest.load('A1;5;AB1\\n   # late additions\\nA2;3;AB2\\n')) == 2\n"},
    {"id": "manifest-last-wins", "kind": "symptom",
     "edits": [("freightkit/manifest.py", "by_id[c.cid] = c", "by_id.setdefault(c.cid, c)")],
     "issue": "Corrections appended at the end of a manifest are ignored: if A1 appears twice, the first "
              "weight is used. The later line must replace the earlier one.",
     "tests": T + "def test_later_line_wins():\n    items = manifest.load('A1;5;AB1\\nA1;7;AB1\\n')\n"
                  "    assert len(items) == 1 and items[0].weight_kg == 7\n"},
    {"id": "manifest-total-grams", "kind": "named",
     "edits": [("freightkit/manifest.py", "return round(sum(c.weight_kg for c in items), 3)",
                "return round(sum(c.weight_kg for c in items), 1)")],
     "issue": "total_weight rounds to 0.1 kg. Customs declarations need grams (3 decimals).",
     "tests": T + "def test_total_in_grams():\n"
                  "    assert manifest.total_weight(manifest.load('A1;1.234;AB1\\nA2;2.001;AB1\\n')) == 3.235\n"},
    {"id": "manifest-zero-weight", "kind": "symptom",
     "edits": [("freightkit/manifest.py", "if w <= 0:", "if w < 0:")],
     "issue": "Lines with a weight of 0 are accepted and break the fuel calculation later. Weights must "
              "be positive.",
     "tests": T + "def test_zero_weight_rejected():\n    with pytest.raises(ValueError):\n"
                  "        manifest.parse_line('A1;0;AB1')\n"},
    {"id": "manifest-trailing-semicolon", "kind": "symptom",
     "edits": [("freightkit/manifest.py", 'priority = parts[3].lower() if len(parts) == 4 and parts[3] else "standard"',
                'priority = parts[3].lower() if len(parts) == 4 else "standard"')],
     "issue": "'A1;5;AB1;' (trailing semicolon, empty priority) fails with unknown priority ''. An empty "
              "priority means standard.",
     "tests": T + "def test_empty_priority_is_standard():\n"
                  "    assert manifest.parse_line('A1;5;AB1;').priority == 'standard'\n"},
    {"id": "manifest-by-priority-keys", "kind": "named",
     "edits": [("freightkit/manifest.py", "out: dict[str, list[Consignment]] = {p: [] for p in PRIORITIES}",
                "out: dict[str, list[Consignment]] = {}")],
     "issue": "by_priority raises KeyError: 'standard' on any manifest. It should return every priority "
              "as a key, with an empty list when there are none.",
     "tests": T + "def test_by_priority():\n    out = manifest.by_priority(manifest.load('A1;5;AB1;express\\n'))\n"
                  "    assert set(out) == {'standard', 'express', 'timed'} and len(out['express']) == 1\n"},
    # ---- dock --------------------------------------------------------------------------------------
    {"id": "dock-touching-slots", "kind": "symptom",
     "edits": [("freightkit/dock.py", "return a[0] < b[1] and b[0] < a[1]", "return a[0] <= b[1] and b[0] <= a[1]")],
     "issue": "Back-to-back bookings 08:00-09:00 and 09:00-10:00 are reported as overlapping. Slots are "
              "half-open, so touching slots do not overlap.",
     "tests": T + "def test_touching_do_not_overlap():\n    assert not dock.overlaps((480, 540), (540, 600))\n"
                  "    assert dock.overlaps((480, 541), (540, 600))\n"},
    {"id": "dock-exact-gap", "kind": "symptom",
     "edits": [("freightkit/dock.py", "if start + duration <= b[0]:", "if start + duration < b[0]:")],
     "issue": "A 30-minute booking is not offered in a gap of exactly 30 minutes (07:00-07:30 between two "
              "bookings); the system jumps to the end of the day.",
     "tests": T + "def test_exact_gap_used():\n"
                  "    assert dock.next_free_slot([(360, 420), (450, 1300)], 30) == (420, 450)\n"},
    {"id": "dock-close-boundary", "kind": "symptom",
     "edits": [("freightkit/dock.py", "if start + duration > CLOSE:", "if start + duration >= CLOSE:")],
     "issue": "The last slot of the day (21:00-22:00) is never offered even when free. The dock closes at "
              "22:00, so a slot may end exactly then.",
     "tests": T + "def test_last_slot_offered():\n    assert dock.next_free_slot([(360, 1260)], 60) == (1260, 1320)\n"},
    {"id": "dock-before-open", "kind": "named",
     "edits": [("freightkit/dock.py", "start = max(earliest, OPEN)", "start = earliest")],
     "issue": "next_free_slot(..., earliest=300) offers 05:00, before the dock opens at 06:00.",
     "tests": T + "def test_not_before_open():\n    assert dock.next_free_slot([], 30, earliest=300) == (360, 390)\n"},
    {"id": "dock-utilization-clip", "kind": "symptom",
     "edits": [("freightkit/dock.py", "        s, e = max(s, OPEN), min(e, CLOSE)\n", "")],
     "issue": "Dock utilization shows 106% on days with a night booking (21:00-23:00). Only time inside "
              "opening hours (06:00-22:00) should count.",
     "tests": T + "def test_utilization_clipped():\n"
                  "    assert dock.utilization([(360, 1320), (1260, 1380)]) == 1.0\n"},
    {"id": "dock-fmt-padding", "kind": "named",
     "edits": [("freightkit/dock.py", 'return f"{minutes // 60:02d}:{minutes % 60:02d}"',
                'return f"{minutes // 60}:{minutes % 60:02d}"')],
     "issue": "fmt(485) returns '8:05'. Screens expect two-digit hours: '08:05'.",
     "tests": T + "def test_fmt_padded():\n    assert dock.fmt(485) == '08:05'\n"},
    # ---- tracking ----------------------------------------------------------------------------------
    {"id": "tracking-hold-in-transit", "kind": "symptom",
     "edits": [("freightkit/tracking.py", '"in_transit": {"out_for_delivery", "held"},', '"in_transit": {"out_for_delivery"},')],
     "issue": "Depots cannot put a consignment on hold while it is in transit: in_transit -> held is "
              "rejected. That move is allowed.",
     "tests": T + "def test_hold_in_transit():\n    assert tracking.can_move('in_transit', 'held')\n"},
    {"id": "tracking-weekend", "kind": "symptom",
     "edits": [("freightkit/tracking.py", "if d.weekday() < 5:", "if d.weekday() < 6:")],
     "issue": "Express jobs collected on Friday 6 March 2026 are promised for Monday 9 March. Two working "
              "days from Friday is Tuesday; Saturday is not a working day.",
     "tests": T + "def test_weekend_skipped():\n"
                  "    assert tracking.promised_date(date(2026, 3, 6), 'express') == date(2026, 3, 10)\n"},
    {"id": "tracking-standard-days", "kind": "named",
     "edits": [("freightkit/tracking.py", '"standard": 4}', '"standard": 5}')],
     "issue": "promised_date gives standard service 5 working days. The service level is 4.",
     "tests": T + "def test_standard_four_days():\n"
                  "    assert tracking.promised_date(date(2026, 3, 2), 'standard') == date(2026, 3, 6)\n"},
    {"id": "tracking-late-on-day", "kind": "symptom",
     "edits": [("freightkit/tracking.py", "return delivered > promised_date(collected, priority)",
                "return delivered >= promised_date(collected, priority)")],
     "issue": "Deliveries made on the promised date are counted as late in the service report.",
     "tests": T + "def test_on_time_not_late():\n"
                  "    assert not tracking.is_late(date(2026, 3, 2), date(2026, 3, 6), 'standard')\n"
                  "    assert tracking.is_late(date(2026, 3, 2), date(2026, 3, 9), 'standard')\n"},
    {"id": "tracking-state-update", "kind": "symptom",
     "edits": [("freightkit/tracking.py", "            raise ValueError(f\"cannot go from {state} to {e}\")\n        state = e\n",
                "            raise ValueError(f\"cannot go from {state} to {e}\")\n")],
     "issue": "apply_events(['collected', 'in_transit']) raises 'cannot go from booked to in_transit'. "
              "Each event should move the consignment on.",
     "tests": T + "def test_events_chain():\n"
                  "    assert tracking.apply_events(['collected', 'in_transit', 'held']) == 'held'\n"},
    {"id": "tracking-unknown-state", "kind": "named",
     "edits": [("freightkit/tracking.py", "        raise KeyError(current)\n", "        return False\n")],
     "issue": "can_move('in_trnasit', 'held') silently returns False. An unknown current state is a bug "
              "in the caller and must raise KeyError.",
     "tests": T + "def test_unknown_state_raises():\n    with pytest.raises(KeyError):\n"
                  "        tracking.can_move('in_trnasit', 'held')\n"},
    # ---- two files ---------------------------------------------------------------------------------
    {"id": "timed-service", "kind": "multi",
     "edits": [("freightkit/manifest.py", 'PRIORITIES = ("standard", "express", "timed")', 'PRIORITIES = ("standard", "express")'),
               ("freightkit/tracking.py", 'days = {"timed": 1, "express": 2, "standard": 4}[priority]',
                'days = {"express": 2, "standard": 4}[priority]')],
     "issue": "The new 'timed' service (next working day) is rejected by the manifest loader, and "
              "promised_date fails for it too. Support 'timed' end to end.",
     "tests": T + "def test_timed_service():\n    assert manifest.parse_line('A1;5;AB1;timed').priority == 'timed'\n"
                  "    assert tracking.promised_date(date(2026, 3, 6), 'timed') == date(2026, 3, 9)\n"},
]


def split(task_id: str) -> str:
    """Fixed split by hash of the ID: about a quarter of tasks for dev (prompt work), the rest for test."""
    return "dev" if int(hashlib.sha256(task_id.encode()).hexdigest(), 16) % 4 == 0 else "test"


def get(task_id: str) -> dict:
    for t in TASKS:
        if t["id"] == task_id:
            return t
    raise KeyError(task_id)
