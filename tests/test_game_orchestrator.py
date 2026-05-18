"""Smoke tests for scripts/game_orchestrator.py — pure helpers + atomic mutations."""
from unittest.mock import patch

import pytest


@pytest.fixture
def queue_dir(tmp_path, monkeypatch):
    """Redirect GAME_QUEUE_DIR to a tmp dir for safe MD writes."""
    import game_orchestrator as go
    monkeypatch.setattr(go, "GAME_QUEUE_DIR", tmp_path)
    return tmp_path


def test_genre_tags_survival_exploration():
    from game_orchestrator import _genre_tags
    tags = _genre_tags("Survival / Exploration")
    assert "#SurvivalGame" in tags
    assert "#ExplorationGame" in tags
    assert len(tags) == 2


def test_genre_tags_caps_at_two():
    from game_orchestrator import _genre_tags
    tags = _genre_tags("Survival Open World Action RPG Indie")
    assert len(tags) == 2


def test_genre_tags_action_adventure_no_duplicates():
    from game_orchestrator import _genre_tags
    # "action" and "adventure" both map to #ActionAdventure — must not duplicate
    tags = _genre_tags("Stealth / Action-Adventure")
    assert tags.count("#ActionAdventure") <= 1


def test_genre_tags_empty_input():
    from game_orchestrator import _genre_tags
    assert _genre_tags("") == []


def test_platform_tags_pc_steam_xbox():
    from game_orchestrator import _platform_tags
    tags = _platform_tags("PC (Steam, Epic) / Xbox Series X|S")
    # Steam, PC, and Xbox are all in the keyword list; capped at 2
    assert len(tags) == 2
    assert any(t in tags for t in ["#Steam", "#PCGaming"])


def test_platform_tags_caps_at_two():
    from game_orchestrator import _platform_tags
    tags = _platform_tags("PC / Steam / Xbox / PS5 / Nintendo")
    assert len(tags) <= 2


def test_mark_queue_status_round_trip(queue_dir):
    from game_orchestrator import mark_queue_status, load_queue_status

    qf = queue_dir / "GG_99_test.md"
    qf.write_text(
        "# GG_99_test — Test\n\n"
        "**Status:** QUEUED\n"
        "**Platform(s):** PC\n\n"
        "## Hook\nSome hook text.\n"
    )

    mark_queue_status("GG_99_test", "DELIVERED")
    content = qf.read_text()
    assert "**Status:** DELIVERED" in content
    # Other lines must be preserved
    assert "**Platform(s):** PC" in content
    assert "## Hook" in content

    statuses = load_queue_status()
    assert statuses["GG_99_test"] == "DELIVERED"


def test_mark_queue_status_only_first_match(queue_dir):
    """The regex must only replace the frontmatter Status, not any in prose."""
    from game_orchestrator import mark_queue_status

    qf = queue_dir / "GG_99_test.md"
    qf.write_text(
        "# Test\n\n"
        "**Status:** QUEUED\n\n"
        "## Notes\n"
        "We previously had **Status:** SOMETHING in the description but...\n"
    )
    mark_queue_status("GG_99_test", "ACTIVE")
    content = qf.read_text()
    assert "**Status:** ACTIVE" in content
    # The second occurrence (in prose) must be untouched
    assert "**Status:** SOMETHING" in content


def test_mark_queue_status_atomic_no_temp_leak(queue_dir):
    """After a successful write, no orphan .tmp should remain."""
    from game_orchestrator import mark_queue_status

    qf = queue_dir / "GG_99_test.md"
    qf.write_text("**Status:** QUEUED\n")
    mark_queue_status("GG_99_test", "DELIVERED")
    temps = list(queue_dir.glob(".*.tmp"))
    assert temps == []


def test_mark_queue_status_missing_file_is_noop(queue_dir):
    from game_orchestrator import mark_queue_status
    # Should not raise
    mark_queue_status("GG_doesnt_exist", "DELIVERED")


def test_load_queue_status_skips_template(queue_dir):
    from game_orchestrator import load_queue_status

    (queue_dir / "GG_TEMPLATE.md").write_text("**Status:** QUEUED\n")
    (queue_dir / "GG_01_real.md").write_text("**Status:** QUEUED\n")
    statuses = load_queue_status()
    assert "GG_01_real" in statuses
    assert "GG_TEMPLATE" not in statuses


def test_load_queue_status_skips_unsafe_ids(queue_dir):
    """Game IDs with chars unsafe for FFmpeg paths must be excluded."""
    from game_orchestrator import load_queue_status

    (queue_dir / "GG_01_good.md").write_text("**Status:** QUEUED\n")
    (queue_dir / "GG_02_has space.md").write_text("**Status:** QUEUED\n")
    statuses = load_queue_status()
    assert "GG_01_good" in statuses
    assert "GG_02_has space" not in statuses


def test_retry_count_round_trip(queue_dir):
    from game_orchestrator import _read_retry_count, _bump_retry_count

    qf = queue_dir / "GG_99_retry.md"
    qf.write_text("**Status:** QUEUED\n## Hook\nFoo\n")
    assert _read_retry_count("GG_99_retry") == 0

    _bump_retry_count("GG_99_retry", 1)
    assert _read_retry_count("GG_99_retry") == 1

    _bump_retry_count("GG_99_retry", 2)
    assert _read_retry_count("GG_99_retry") == 2
    # The first bump inserts; the second must update in place, not duplicate
    assert qf.read_text().count("**Retries:**") == 1
