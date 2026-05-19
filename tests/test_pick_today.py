"""Tests for scripts/pick_today.py — the /morning hot-path ranker.

Covers the surfaces that would silently degrade tomorrow's autonomous batch
if they regressed: ranking by mined_score, tweaks skew bonus, subgenre cap,
deterministic tie-break, and the tweaks-file reader."""

from datetime import date

import pick_today


def _stub(case_id, subgenre, score, voice=None, gender="F", status="QUEUED"):
    return {
        "case_id": case_id,
        "status": status,
        "subgenre": subgenre,
        "mined_score": score,
        "voice": voice,
        "gender": gender,
    }


# ---------------------------------------------------------------------------
# rank_picks
# ---------------------------------------------------------------------------

def test_rank_picks_orders_by_mined_score():
    items = [
        _stub("SY_low", "A", 50.0),
        _stub("SY_high", "B", 90.0),
        _stub("SY_mid", "C", 70.0),
    ]
    picks = pick_today.rank_picks(items, count=3, skews={})
    assert [p["case_id"] for p in picks] == ["SY_high", "SY_mid", "SY_low"]


def test_rank_picks_subgenre_skew_adds_10():
    items = [
        _stub("SY_A_80", "A", 80.0),
        _stub("SY_B_75", "B", 75.0),
    ]
    picks = pick_today.rank_picks(items, count=2, skews={"preferred_subgenre": "B"})
    # +10 on B → 85 beats A's 80
    assert picks[0]["case_id"] == "SY_B_75"
    assert picks[0]["score"] == 85.0


def test_rank_picks_voice_skew_adds_5():
    items = [
        _stub("SY_A_80", "A", 80.0, voice="Adam"),
        _stub("SY_B_78", "B", 78.0, voice="Rachel"),
    ]
    picks = pick_today.rank_picks(
        items, count=2, skews={"preferred_voices": ["Rachel"]}
    )
    # +5 on Rachel → 83 beats Adam's 80
    assert picks[0]["case_id"] == "SY_B_78"
    assert picks[0]["score"] == 83.0


def test_rank_picks_subgenre_cap_caps_at_3():
    items = [_stub(f"SY_{i}", "Horror", 90.0 - i) for i in range(5)]
    picks = pick_today.rank_picks(items, count=4, skews={})
    assert len(picks) == 3
    assert all(p["subgenre"] == "Horror" for p in picks)


def test_rank_picks_deterministic_tie_break():
    items = [
        _stub("SY_one", "A", 80.0),
        _stub("SY_two", "A", 80.0),
    ]
    first = pick_today.rank_picks(items, count=2, skews={})
    second = pick_today.rank_picks(items, count=2, skews={})
    assert [p["case_id"] for p in first] == [p["case_id"] for p in second]


def test_rank_picks_empty_queue_returns_empty():
    assert pick_today.rank_picks([], count=4, skews={}) == []


def test_rank_picks_count_short_when_cap_blocks():
    items = [
        _stub("SY_h1", "Horror", 90.0),
        _stub("SY_h2", "Horror", 85.0),
        _stub("SY_h3", "Horror", 80.0),
        _stub("SY_h4", "Horror", 75.0),
    ]
    picks = pick_today.rank_picks(items, count=5, skews={})
    assert len(picks) == 3


def test_rank_picks_rationale_includes_skew_when_applied():
    items = [_stub("SY_x", "Infidelity", 80.0, voice="Rachel")]
    picks = pick_today.rank_picks(
        items, count=1,
        skews={"preferred_subgenre": "Infidelity", "preferred_voices": ["Rachel"]},
    )
    assert "+10 sub-genre skew" in picks[0]["rationale"]
    assert "+5 voice skew" in picks[0]["rationale"]


# ---------------------------------------------------------------------------
# read_tweaks_skews — consumer of suggest_tweaks output
# ---------------------------------------------------------------------------

def test_read_tweaks_skews_missing_dir_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(pick_today, "ANALYTICS_DIR", tmp_path / "missing")
    assert pick_today.read_tweaks_skews() == {}


def test_read_tweaks_skews_missing_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(pick_today, "ANALYTICS_DIR", tmp_path)
    assert pick_today.read_tweaks_skews() == {}


def test_read_tweaks_skews_parses_subgenre_and_voices(monkeypatch, tmp_path):
    monkeypatch.setattr(pick_today, "ANALYTICS_DIR", tmp_path)
    tweaks = tmp_path / f"suggested_tweaks_{date.today().isoformat()}.md"
    tweaks.write_text(
        "- Skew today's batch toward `Infidelity`\n"
        "- Prefer voices: `Rachel`, `Bella`, `Domi`\n"
    )
    skews = pick_today.read_tweaks_skews()
    assert skews["preferred_subgenre"] == "Infidelity"
    assert skews["preferred_voices"] == ["Rachel", "Bella", "Domi"]


def test_read_tweaks_skews_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(pick_today, "ANALYTICS_DIR", tmp_path)
    tweaks = tmp_path / f"suggested_tweaks_{date.today().isoformat()}.md"
    tweaks.write_text("- Skew today's batch toward `Horror`\n")
    first = pick_today.read_tweaks_skews()
    second = pick_today.read_tweaks_skews()
    assert first == second


def test_read_tweaks_skews_ignores_unrelated_lines(monkeypatch, tmp_path):
    monkeypatch.setattr(pick_today, "ANALYTICS_DIR", tmp_path)
    tweaks = tmp_path / f"suggested_tweaks_{date.today().isoformat()}.md"
    tweaks.write_text(
        "# Suggested tweaks — today\n\n"
        "## Yesterday at a glance\n"
        "- Videos analyzed: 5\n"
        "- Some future directive: xyz\n"
        "- Skew today's batch toward `Mystery`\n"
    )
    skews = pick_today.read_tweaks_skews()
    assert skews == {"preferred_subgenre": "Mystery"}
