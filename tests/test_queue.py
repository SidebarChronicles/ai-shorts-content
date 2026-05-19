"""Tests for scripts/_queue.py — the shared queue scanner introduced during
the 2026-05-18 cleanup pass to dedupe pick_today + suggest_tweaks regexes.

These tests cover the public surface (scan_queue + load_queue_meta) at a
behavioral level: synthetic SY_*.md stubs in tmp_path, assert the parsed
dicts match expectations. No mocking — pure file I/O."""

import textwrap
from pathlib import Path

from _queue_scan import load_queue_meta, scan_queue


def _write_stub(dir_: Path, name: str, body: str) -> Path:
    p = dir_ / name
    p.write_text(textwrap.dedent(body).lstrip())
    return p


def test_scan_queue_returns_empty_when_dir_missing(tmp_path):
    assert scan_queue(tmp_path / "does_not_exist") == []


def test_scan_queue_returns_empty_when_dir_empty(tmp_path):
    assert scan_queue(tmp_path) == []


def test_scan_queue_parses_full_stub(tmp_path):
    _write_stub(tmp_path, "SY_01_test.md", """
        # Test stub
        **Status:** QUEUED
        **Subgenre:** Infidelity
        **Mined score**: 87.5
        **Voice:** Rachel
        **Narrator gender:** F
    """)
    items = scan_queue(tmp_path)
    assert len(items) == 1
    item = items[0]
    assert item["case_id"] == "SY_01_test"
    assert item["status"] == "QUEUED"
    assert item["subgenre"] == "Infidelity"
    assert item["mined_score"] == 87.5
    assert item["voice"] == "Rachel"
    assert item["gender"] == "F"


def test_scan_queue_excludes_template(tmp_path):
    _write_stub(tmp_path, "SY_TEMPLATE.md", "**Status:** QUEUED\n")
    _write_stub(tmp_path, "SY_TEMPLATE_archive.md", "**Status:** QUEUED\n")
    _write_stub(tmp_path, "SY_01_real.md", "**Status:** QUEUED\n")
    items = scan_queue(tmp_path)
    case_ids = [it["case_id"] for it in items]
    assert case_ids == ["SY_01_real"]


def test_scan_queue_defaults_when_fields_missing(tmp_path):
    _write_stub(tmp_path, "SY_02_bare.md", "# Just a heading, no metadata\n")
    items = scan_queue(tmp_path)
    assert len(items) == 1
    item = items[0]
    assert item["status"] == "UNKNOWN"
    assert item["subgenre"] == "unknown"
    assert item["mined_score"] == 0.0
    assert item["voice"] is None
    assert item["gender"] is None


def test_scan_queue_sorted_by_case_id(tmp_path):
    _write_stub(tmp_path, "SY_03_charlie.md", "**Status:** QUEUED\n")
    _write_stub(tmp_path, "SY_01_alpha.md", "**Status:** QUEUED\n")
    _write_stub(tmp_path, "SY_02_bravo.md", "**Status:** QUEUED\n")
    items = scan_queue(tmp_path)
    assert [it["case_id"] for it in items] == [
        "SY_01_alpha", "SY_02_bravo", "SY_03_charlie"
    ]


def test_load_queue_meta_dictifies_by_case_id(tmp_path):
    _write_stub(tmp_path, "SY_01_a.md", """
        **Status:** QUEUED
        **Subgenre:** Horror
        **Voice:** Bella
        **Narrator gender:** F
    """)
    _write_stub(tmp_path, "SY_02_b.md", """
        **Status:** QUEUED
        **Voice:** Adam
        **Narrator gender:** M
    """)
    meta = load_queue_meta(tmp_path)
    assert set(meta.keys()) == {"SY_01_a", "SY_02_b"}
    assert meta["SY_01_a"] == {"voice": "Bella", "gender": "F", "subgenre": "Horror"}
    # Subgenre None (not the string "unknown") preserves the legacy contract
    # so callers' "unknown" fallback still kicks in when other sources miss.
    assert meta["SY_02_b"] == {"voice": "Adam", "gender": "M", "subgenre": None}
