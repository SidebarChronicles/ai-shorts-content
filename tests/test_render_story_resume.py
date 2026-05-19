"""Tests for scripts/render_story.py — focused on the step-1 validator and
the --from-step skip behavior.

These guard the surfaces that would let tomorrow's autonomous /morning
silently proceed with broken config or skip prereqs."""

import json

import pytest

import render_story
from render_story import StepValidationError, case_paths


def _make_case(tmp_path, case_id, config):
    """Write a script_config.json under tmp_path/output/scripts/<case>/."""
    case_dir = tmp_path / "output" / "scripts" / case_id
    case_dir.mkdir(parents=True)
    (case_dir / "script_config.json").write_text(json.dumps(config))
    return case_dir


def _paths_for(case_id, scripts_dir):
    case_dir = scripts_dir / case_id
    return {
        "case_dir": case_dir,
        "config": case_dir / "script_config.json",
    }


def test_step_1_validate_raises_when_config_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(render_story, "SCRIPTS_DIR", tmp_path / "output" / "scripts")
    p = _paths_for("SY_99_missing", render_story.SCRIPTS_DIR)
    with pytest.raises(StepValidationError, match="not found"):
        render_story.step_1_validate("SY_99_missing", p, dry_run=False, force=False)


def test_step_1_validate_raises_on_no_beats(tmp_path, monkeypatch):
    monkeypatch.setattr(render_story, "SCRIPTS_DIR", tmp_path / "output" / "scripts")
    _make_case(tmp_path, "SY_98_nobeat", {"case_id": "SY_98_nobeat", "beats": []})
    p = _paths_for("SY_98_nobeat", render_story.SCRIPTS_DIR)
    with pytest.raises(StepValidationError, match="no beats"):
        render_story.step_1_validate("SY_98_nobeat", p, dry_run=False, force=False)


def test_step_1_validate_raises_on_fill_in_placeholder(tmp_path, monkeypatch):
    monkeypatch.setattr(render_story, "SCRIPTS_DIR", tmp_path / "output" / "scripts")
    _make_case(tmp_path, "SY_97_fillin", {
        "case_id": "SY_97_fillin",
        "beats": [{"text": "[FILL IN beat 1]"}],
    })
    p = _paths_for("SY_97_fillin", render_story.SCRIPTS_DIR)
    with pytest.raises(StepValidationError, match="[Pp]laceholders"):
        render_story.step_1_validate("SY_97_fillin", p, dry_run=False, force=False)


def test_step_1_validate_raises_on_empty_text(tmp_path, monkeypatch):
    monkeypatch.setattr(render_story, "SCRIPTS_DIR", tmp_path / "output" / "scripts")
    _make_case(tmp_path, "SY_96_empty", {
        "case_id": "SY_96_empty",
        "beats": [{"text": "   "}],
    })
    p = _paths_for("SY_96_empty", render_story.SCRIPTS_DIR)
    with pytest.raises(StepValidationError, match="[Pp]laceholders"):
        render_story.step_1_validate("SY_96_empty", p, dry_run=False, force=False)


def test_step_1_validate_passes_on_filled_config(tmp_path, monkeypatch):
    monkeypatch.setattr(render_story, "SCRIPTS_DIR", tmp_path / "output" / "scripts")
    _make_case(tmp_path, "SY_95_ok", {
        "case_id": "SY_95_ok",
        "beats": [
            {
                "text": "Filled-in beat text.",
                "visual_brief": {"scene": "ok"},
                "sound_brief": {"mood": "ok"},
            }
        ],
    })
    p = _paths_for("SY_95_ok", render_story.SCRIPTS_DIR)
    # Should not raise
    render_story.step_1_validate("SY_95_ok", p, dry_run=False, force=False)


# ---------------------------------------------------------------------------
# render_one — --from-step skip behavior
# ---------------------------------------------------------------------------

def test_render_one_from_step_skips_earlier_steps(monkeypatch):
    """--from-step 4 should not call steps 1..3 but should attempt steps 4+."""
    called: list[str] = []

    def make_recorder(name):
        def _fn(case_id, p, *, dry_run, force):
            called.append(name)
        return _fn

    fake_steps = [(name, make_recorder(name)) for name, _ in render_story.STEPS]
    monkeypatch.setattr(render_story, "STEPS", fake_steps)

    ok = render_story.render_one(
        "SY_test_skip", dry_run=True, force=False, from_step=4, only_step=None
    )
    assert ok is True
    skipped = {name for name, _ in render_story.STEPS[:3]}
    ran = {name for name, _ in render_story.STEPS[3:]}
    assert not (skipped & set(called)), f"unexpectedly ran skipped steps: {skipped & set(called)}"
    assert ran.issubset(set(called)), f"missing expected steps: {ran - set(called)}"


def test_render_one_only_step_runs_just_one(monkeypatch):
    called: list[str] = []

    def make_recorder(name):
        def _fn(case_id, p, *, dry_run, force):
            called.append(name)
        return _fn

    fake_steps = [(name, make_recorder(name)) for name, _ in render_story.STEPS]
    monkeypatch.setattr(render_story, "STEPS", fake_steps)

    render_story.render_one(
        "SY_test_only", dry_run=True, force=False, from_step=1, only_step=11
    )
    assert called == [render_story.STEPS[10][0]]


# ---------------------------------------------------------------------------
# case_paths
# ---------------------------------------------------------------------------

def test_case_paths_keys_are_complete():
    """case_paths must return every key the steps reference."""
    p = case_paths("SY_test_paths")
    required = {
        "case_dir", "config", "narration", "alignment",
        "audio_mixed", "audio_mixed_alignment", "sound_design",
        "concat_list", "clips_manifest",
        "karaoke_filter", "top_title_filter", "hook_overlay_filter",
        "final_mp4",
    }
    assert required.issubset(p.keys()), f"missing keys: {required - set(p.keys())}"
