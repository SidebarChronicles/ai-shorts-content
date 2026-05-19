"""Tests for scripts/schedule_uploads.next_prime_slots.

Uses the `_now` injection seam (added during the 2026-05-18 cleanup pass)
for deterministic results without monkeypatching `datetime`."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from schedule_uploads import PRIME_SLOTS_ET, next_prime_slots

ET = ZoneInfo("America/New_York")


def test_prime_slots_are_in_approved_set():
    slots = next_prime_slots(8)
    approved = {(h, m) for h, m in PRIME_SLOTS_ET}
    assert approved == {(8, 0), (12, 30), (18, 30), (21, 30)}
    for s in slots:
        assert (s.hour, s.minute) in approved


def test_prime_slots_count_matches_requested():
    assert len(next_prime_slots(1)) == 1
    assert len(next_prime_slots(4)) == 4
    assert len(next_prime_slots(9)) == 9


def test_prime_slots_all_at_least_24h_out_at_dawn():
    now = datetime(2026, 5, 19, 5, 0, 0, tzinfo=ET)
    slots = next_prime_slots(4, _now=now)
    for s in slots:
        assert s >= now + timedelta(hours=24)


def test_prime_slots_all_at_least_24h_out_at_dusk():
    now = datetime(2026, 5, 19, 22, 0, 0, tzinfo=ET)
    slots = next_prime_slots(4, _now=now)
    for s in slots:
        assert s >= now + timedelta(hours=24)


def test_prime_slots_wraps_to_tomorrow_when_today_is_done():
    now = datetime(2026, 5, 19, 22, 0, 0, tzinfo=ET)
    slots = next_prime_slots(4, _now=now)
    assert all(s.date() >= now.date() + timedelta(days=1) for s in slots)


def test_prime_slots_returns_earliest_available_slot_first():
    now = datetime(2026, 5, 19, 6, 0, 0, tzinfo=ET)
    slots = next_prime_slots(1, _now=now)
    # 24h from 06:00 ET on 5/19 = 06:00 ET on 5/20. Earliest prime ≥ that = 08:00 ET on 5/20.
    expected = datetime(2026, 5, 20, 8, 0, 0, tzinfo=ET)
    assert slots[0] == expected


def test_prime_slots_returned_in_ascending_order():
    now = datetime(2026, 5, 19, 6, 0, 0, tzinfo=ET)
    slots = next_prime_slots(8, _now=now)
    for a, b in zip(slots, slots[1:]):
        assert a < b


def test_prime_slots_two_days_yields_eight_distinct():
    now = datetime(2026, 5, 19, 6, 0, 0, tzinfo=ET)
    slots = next_prime_slots(8, _now=now)
    assert len(set(slots)) == 8
