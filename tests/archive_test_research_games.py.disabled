"""Smoke tests for scripts/research_games.py — pure helpers."""
import pytest


def test_slugify_basic():
    from research_games import slugify
    assert slugify("007 First Light") == "007_first_light"


def test_slugify_strips_punctuation():
    from research_games import slugify
    out = slugify("Half-Life: Alyx 2")
    # Hyphen and colon stripped, words joined by underscore
    assert "_" in out
    assert ":" not in out
    assert "-" not in out


def test_slugify_lowercases():
    from research_games import slugify
    assert slugify("SUBNAUTICA 2") == "subnautica_2"


def test_slugify_caps_length():
    from research_games import slugify
    long_name = "A" * 200
    assert len(slugify(long_name)) <= 40


def test_next_queue_number_empty(tmp_path, monkeypatch):
    import research_games as rg
    monkeypatch.setattr(rg, "GAME_QUEUE_DIR", tmp_path)
    assert rg.next_queue_number() == 1


def test_next_queue_number_with_existing(tmp_path, monkeypatch):
    import research_games as rg
    monkeypatch.setattr(rg, "GAME_QUEUE_DIR", tmp_path)
    (tmp_path / "GG_01_foo.md").write_text("x")
    (tmp_path / "GG_07_bar.md").write_text("x")
    (tmp_path / "GG_03_baz.md").write_text("x")
    assert rg.next_queue_number() == 8


def test_next_queue_number_ignores_non_matching(tmp_path, monkeypatch):
    import research_games as rg
    monkeypatch.setattr(rg, "GAME_QUEUE_DIR", tmp_path)
    (tmp_path / "GG_TEMPLATE.md").write_text("x")
    (tmp_path / "README.md").write_text("x")
    # Has no numeric GG_NN_ files
    assert rg.next_queue_number() == 1
