"""Smoke tests for scripts/make_audio_elevenlabs.py — text extraction paths."""
import json

import pytest


def test_extract_from_game_config(tmp_path, monkeypatch):
    import make_audio_elevenlabs as mae

    monkeypatch.setattr(mae, "SCRIPTS_DIR", tmp_path)
    game_dir = tmp_path / "GG_99_test"
    game_dir.mkdir()
    (game_dir / "game_config.json").write_text(json.dumps({
        "game_id": "GG_99_test",
        "spoken_text": "Hello world from game config.",
    }))

    text = mae.extract_spoken_text("GG_99_test")
    assert text == "Hello world from game config."


def test_extract_from_script_md_blockquote(tmp_path, monkeypatch):
    """Truecrime path: script.md with '## Script (spoken)' section + > markers."""
    import make_audio_elevenlabs as mae

    monkeypatch.setattr(mae, "SCRIPTS_DIR", tmp_path)
    case_dir = tmp_path / "07_test_case"
    case_dir.mkdir()
    (case_dir / "script.md").write_text(
        "# Case\n\n"
        "## Script (spoken — clean)\n\n"
        "> First sentence.\n"
        "> Second sentence.\n"
        "\n---\n\n"
        "## Other section\n"
    )

    text = mae.extract_spoken_text("07_test_case")
    # Blockquote markers stripped, lines joined
    assert ">" not in text
    assert "First sentence." in text
    assert "Second sentence." in text


def test_game_config_takes_precedence(tmp_path, monkeypatch):
    """If both game_config.json AND script.md exist, prefer game_config.json."""
    import make_audio_elevenlabs as mae

    monkeypatch.setattr(mae, "SCRIPTS_DIR", tmp_path)
    game_dir = tmp_path / "GG_99_test"
    game_dir.mkdir()
    (game_dir / "game_config.json").write_text(json.dumps({"spoken_text": "from config"}))
    (game_dir / "script.md").write_text(
        "## Script (spoken)\n\n> from script md\n\n---\n"
    )

    text = mae.extract_spoken_text("GG_99_test")
    assert text == "from config"


def test_missing_both_exits(tmp_path, monkeypatch):
    import make_audio_elevenlabs as mae

    monkeypatch.setattr(mae, "SCRIPTS_DIR", tmp_path)
    with pytest.raises(SystemExit):
        mae.extract_spoken_text("doesnt_exist")
