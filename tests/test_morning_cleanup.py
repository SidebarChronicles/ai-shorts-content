"""Tests for scripts/morning_cleanup.py — guards the dry-run vs --apply
boundary that nearly bit us when /morning was running without --apply.

These exercise rule_archive_dated and rule_prune_part_files directly on
synthetic file trees in tmp_path; no subprocess or real filesystem touches."""

import morning_cleanup


def test_rule_archive_dated_no_op_when_under_keep_n(tmp_path):
    for i in range(3):
        (tmp_path / f"picks_2026-05-{i+1:02d}.json").write_text("{}")
    log: list = []
    bytes_freed = morning_cleanup.rule_archive_dated(
        tmp_path, "picks_*.json", keep_n=7, keep_latest=False, apply=False, log=log
    )
    assert log == []
    assert bytes_freed == 0


def test_rule_archive_dated_dry_run_does_not_move(tmp_path):
    files = [tmp_path / f"picks_2026-05-{i+1:02d}.json" for i in range(10)]
    for f in files:
        f.write_text("{}")
    log: list = []
    morning_cleanup.rule_archive_dated(
        tmp_path, "picks_*.json", keep_n=7, keep_latest=False, apply=False, log=log
    )
    assert len(log) == 3  # 10 - 7
    for f in files:
        assert f.exists()
    assert not (tmp_path / "archive").exists()


def test_rule_archive_dated_apply_moves_oldest_files(tmp_path):
    files = [tmp_path / f"picks_2026-05-{i+1:02d}.json" for i in range(10)]
    for f in files:
        f.write_text("{}")
    log: list = []
    morning_cleanup.rule_archive_dated(
        tmp_path, "picks_*.json", keep_n=7, keep_latest=False, apply=True, log=log
    )
    archive_dir = tmp_path / "archive"
    assert archive_dir.exists()
    for f in files[:3]:
        assert not f.exists()
        assert (archive_dir / f.name).exists()
    for f in files[3:]:
        assert f.exists()


def test_rule_archive_dated_keep_latest_keeps_only_newest_date(tmp_path):
    files = [tmp_path / f"candidates_2026-05-{i:02d}.md" for i in (17, 18, 19)]
    for f in files:
        f.write_text("body")
    log: list = []
    morning_cleanup.rule_archive_dated(
        tmp_path, "candidates_*.md", keep_n=None, keep_latest=True, apply=True, log=log
    )
    assert files[2].exists()
    assert not files[0].exists()
    assert not files[1].exists()
    assert (tmp_path / "archive" / files[0].name).exists()
    assert (tmp_path / "archive" / files[1].name).exists()


def test_rule_archive_dated_missing_dir_is_no_op(tmp_path):
    log: list = []
    morning_cleanup.rule_archive_dated(
        tmp_path / "missing", "picks_*.json", keep_n=7, keep_latest=False,
        apply=True, log=log,
    )
    assert log == []


def test_rule_prune_part_files_dry_run_leaves_parts(tmp_path, monkeypatch):
    monkeypatch.setattr(morning_cleanup, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(morning_cleanup, "AUDIO_DIR", tmp_path / "assets" / "audio")
    (tmp_path / "output").mkdir()
    parts = [tmp_path / "output" / "foo.part", tmp_path / "output" / "bar.part"]
    for p in parts:
        p.write_text("partial")
    log: list = []
    morning_cleanup.rule_prune_part_files(apply=False, log=log)
    assert len(log) == 2
    for p in parts:
        assert p.exists()  # dry-run must NOT delete


def test_rule_prune_part_files_apply_deletes_parts(tmp_path, monkeypatch):
    monkeypatch.setattr(morning_cleanup, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(morning_cleanup, "AUDIO_DIR", tmp_path / "assets" / "audio")
    (tmp_path / "output").mkdir()
    leftover = tmp_path / "output" / "narration_SY_01.mp3.part"
    leftover.write_text("partial")
    log: list = []
    morning_cleanup.rule_prune_part_files(apply=True, log=log)
    assert not leftover.exists()
    assert len(log) == 1
    assert log[0][0] == "remove"


def test_rule_prune_part_files_no_match_is_no_op(tmp_path, monkeypatch):
    monkeypatch.setattr(morning_cleanup, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(morning_cleanup, "AUDIO_DIR", tmp_path / "assets" / "audio")
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "regular.mp3").write_text("ok")
    log: list = []
    morning_cleanup.rule_prune_part_files(apply=True, log=log)
    assert log == []
    assert (tmp_path / "output" / "regular.mp3").exists()


def test_parse_date_from_filename_handles_iso_date():
    assert morning_cleanup.parse_date_from_filename("picks_2026-05-19.json") is not None
    assert morning_cleanup.parse_date_from_filename("report_2026-12-31.md") is not None


def test_parse_date_from_filename_returns_none_when_absent():
    assert morning_cleanup.parse_date_from_filename("no_date_here.json") is None


def test_archive_path_under_sibling_archive_dir(tmp_path):
    src = tmp_path / "sub" / "foo.json"
    src.parent.mkdir()
    src.write_text("{}")
    assert morning_cleanup.archive_path(src) == tmp_path / "sub" / "archive" / "foo.json"
