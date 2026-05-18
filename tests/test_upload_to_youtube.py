"""Smoke tests for scripts/upload_to_youtube.py — pure helpers."""
from datetime import datetime, timezone

import pytest


def test_build_body_publish_immediately():
    from upload_to_youtube import build_body
    meta = {"title": "t", "description": "d", "tags": ["a", "b"]}
    body = build_body(meta, publish_at=None, category_id="20")
    assert body["status"]["privacyStatus"] == "public"
    assert "publishAt" not in body["status"]
    assert body["status"]["containsSyntheticMedia"] is True
    assert body["snippet"]["categoryId"] == "20"


def test_build_body_scheduled():
    from upload_to_youtube import build_body
    meta = {"title": "t", "description": "d", "tags": []}
    dt = datetime(2026, 5, 20, 18, 0, 0, tzinfo=timezone.utc)
    body = build_body(meta, publish_at=dt, category_id="24")
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["publishAt"].endswith("Z")
    assert body["status"]["publishAt"].startswith("2026-05-20T18:00:00")


def test_parse_publish_at_naive():
    from upload_to_youtube import parse_publish_at
    dt = parse_publish_at("2026-05-20T18:00:00")
    # Result must be UTC
    assert dt.tzinfo is not None
    assert dt.tzinfo.utcoffset(dt).total_seconds() == 0


def test_parse_publish_at_aware():
    from upload_to_youtube import parse_publish_at
    dt = parse_publish_at("2026-05-20T18:00:00+04:00")
    # 18:00 +04 → 14:00 UTC
    assert dt.hour == 14


def test_compute_next_slot_is_at_least_24h_out():
    from upload_to_youtube import compute_next_slot
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    slot = compute_next_slot()
    delta = slot - now
    assert delta >= timedelta(hours=23, minutes=30), f"slot only {delta} from now"
    assert slot.tzinfo is timezone.utc


def test_compute_next_slot_targets_local_6pm():
    from upload_to_youtube import compute_next_slot
    slot_utc = compute_next_slot()
    slot_local = slot_utc.astimezone()
    assert slot_local.hour == 18
    assert slot_local.minute == 0
