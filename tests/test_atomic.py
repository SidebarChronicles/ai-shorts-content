"""Smoke tests for scripts/_atomic.py — the foundation of every state-file write."""
import json

from _atomic import atomic_write_json, atomic_write_text


def test_atomic_write_text_creates_file(tmp_path):
    path = tmp_path / "out.txt"
    atomic_write_text(path, "hello world")
    assert path.read_text() == "hello world"


def test_atomic_write_text_overwrites_existing(tmp_path):
    path = tmp_path / "out.txt"
    path.write_text("old contents")
    atomic_write_text(path, "new contents")
    assert path.read_text() == "new contents"


def test_atomic_write_text_creates_parent_dirs(tmp_path):
    path = tmp_path / "nested" / "dir" / "out.txt"
    atomic_write_text(path, "data")
    assert path.read_text() == "data"


def test_atomic_write_text_no_orphan_tmp(tmp_path):
    path = tmp_path / "out.txt"
    atomic_write_text(path, "x")
    # After success, no .tmp files should remain alongside the dest.
    leftovers = list(tmp_path.glob(".*.tmp"))
    assert leftovers == [], f"orphan tmp files: {leftovers}"


def test_atomic_write_json_round_trip(tmp_path):
    path = tmp_path / "out.json"
    payload = {"a": 1, "b": [2, 3], "c": "hi"}
    atomic_write_json(path, payload)
    assert json.loads(path.read_text()) == payload


def test_atomic_write_json_sorted_keys(tmp_path):
    path = tmp_path / "out.json"
    atomic_write_json(path, {"z": 1, "a": 2})
    content = path.read_text()
    # 'a' should come before 'z' when sort_keys=True (default)
    assert content.index('"a"') < content.index('"z"')
