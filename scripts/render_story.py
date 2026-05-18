#!/usr/bin/env python3
"""Render one story end-to-end. Chains the 11 manual steps from the SY_09 flow.

This is the orchestrator that replaces the deleted ~/.claude/scheduled-tasks/
daily-shorts-pipeline routine. The /morning workflow invokes this per case.

Steps (each idempotent — skipped if its output already exists, unless --force):
  1.  validate config + beats[].text populated (writer ran)
  2.  check_script_structure --fail-fast
  3.  make_audio_elevenlabs (per-beat mood mode auto-detected)
  4.  build_visuals_track (Flux + Pika)
  5.  build_sound_design (Freesound ambient + SFX)
  6.  copy alignment.json adjacent to audio_mixed.mp3 (renderer expectation)
  7.  add renderer-required field aliases (game_id, audio_file, etc.)
  8.  build_karaoke_filter + build_top_title_filter
  9.  render_game_video (builds filters + audio_mixed + prints encode cmd)
  10. mix narration + sound_design → audio_mixed.mp3 (overrides renderer's mix)
  11. final ffmpeg encode → output/story_videos/<case>.mp4
  12. story_orchestrator --mark-status <case> RENDERED

Usage:
    python scripts/render_story.py --case SY_09_H_a_wife_shouldn_t_argue_w
    python scripts/render_story.py --case SY_09 --dry-run
    python scripts/render_story.py --case SY_09 --from-step 4    # resume after a crash
    python scripts/render_story.py --case SY_09 --only-step 11   # re-encode only
    python scripts/render_story.py --batch output/daily/picks_2026-05-19.json

Exit codes:
    0  success
    1  one or more steps failed
    2  usage / I/O error
    3  budget guard tripped (no API calls made)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

SCRIPTS_DIR = PROJECT_ROOT / "output" / "scripts"
AUDIO_DIR = PROJECT_ROOT / "assets" / "audio"
STORY_VIDEOS_DIR = PROJECT_ROOT / "output" / "story_videos"
SOUND_DESIGN_DIR = PROJECT_ROOT / "output" / "audio"

VENV_PY = PROJECT_ROOT / ".venv-upload" / "bin" / "python3"
PYTHON = str(VENV_PY) if VENV_PY.exists() else sys.executable

# Per-call rough costs for the budget rollup (informational only).
ROUGH_COST_PER_CASE = 1.50  # ~$0.20 EL + ~$1.30 Replicate (Flux + Pika)

# Audio mix levels (in linear gain, applied via ffmpeg `volume` filter).
NARRATION_GAIN = 1.0   # narration sits at unity (anchor)
SOUND_BED_GAIN = 0.55  # sound design ducks under VO by ~-5dB

# Custom exception so a step's "user-facing exit" is distinguishable from
# subprocess failures (which raise CalledProcessError).
class StepValidationError(RuntimeError):
    """A step refuses to run because of bad config / missing inputs."""


# ---------------------------------------------------------------------------
# Step helpers
# ---------------------------------------------------------------------------

def run_step(label: str, cmd: list[str], dry_run: bool, env: dict | None = None) -> None:
    """Run a subprocess. On failure: raise CalledProcessError with stderr captured."""
    print(f"  → {label}")
    if dry_run:
        print(f"      [dry-run] {' '.join(str(c) for c in cmd)}")
        return
    result = subprocess.run(cmd, env=env or os.environ.copy(), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"      ✗ FAIL (exit {result.returncode})", file=sys.stderr)
        if result.stdout:
            print(f"      stdout: {result.stdout.strip()[-500:]}", file=sys.stderr)
        if result.stderr:
            print(f"      stderr: {result.stderr.strip()[-500:]}", file=sys.stderr)
        raise subprocess.CalledProcessError(result.returncode, cmd)


def case_paths(case_id: str) -> dict[str, Path]:
    case_dir = SCRIPTS_DIR / case_id
    return {
        "case_dir": case_dir,
        "config": case_dir / "script_config.json",
        "narration": AUDIO_DIR / f"narration_{case_id}.mp3",
        "alignment": AUDIO_DIR / f"narration_{case_id}.alignment.json",
        "audio_mixed": case_dir / "audio_mixed.mp3",
        "audio_mixed_alignment": case_dir / "audio_mixed.alignment.json",
        "sound_design": SOUND_DESIGN_DIR / case_id / "sound_design.wav",
        "concat_list": case_dir / "bg_clips_concat.txt",
        "clips_manifest": case_dir / "clips_manifest.json",
        "karaoke_filter": case_dir / "karaoke.filter",
        "top_title_filter": case_dir / "top_title.filter",
        "hook_overlay_filter": case_dir / "hook_overlay.filter",
        "final_mp4": STORY_VIDEOS_DIR / f"{case_id}.mp4",
    }


# ---------------------------------------------------------------------------
# Step implementations
#
# All steps share signature: step(case_id, p, *, dry_run, force) -> None
# Steps that don't need `force` accept it for signature uniformity (avoids
# reflection-based dispatch). They MAY raise StepValidationError to signal
# bad config or CalledProcessError to signal subprocess failure.
# ---------------------------------------------------------------------------

def step_1_validate(case_id: str, p: dict[str, Path], *, dry_run: bool, force: bool) -> None:
    """Verify script_config.json exists + beats[].text + briefs are populated."""
    if not p["config"].exists():
        raise StepValidationError(
            f"{p['config']} not found. Run story_script_writer.py --case {case_id} first."
        )
    cfg = json.loads(p["config"].read_text())
    beats = cfg.get("beats", [])
    if not beats:
        raise StepValidationError(f"{p['config']} has no beats[].")
    placeholders: list[str] = []
    for i, b in enumerate(beats):
        text = (b.get("text") or "").strip()
        if not text or text.startswith("[FILL IN") or text.startswith("[fill in"):
            placeholders.append(f"beats[{i}].text")
        if (b.get("visual_brief") or {}).get("_FILL_IN"):
            placeholders.append(f"beats[{i}].visual_brief")
        if (b.get("sound_brief") or {}).get("_FILL_IN"):
            placeholders.append(f"beats[{i}].sound_brief")
    if placeholders:
        raise StepValidationError(
            f"writer hasn't filled all briefs/text. Placeholders at: {placeholders}. "
            f"Fill them per scripts/story_writer_prompt.md, then re-run."
        )


def step_2_check_structure(case_id: str, p: dict[str, Path], *, dry_run: bool, force: bool) -> None:
    run_step(
        "check_script_structure",
        [PYTHON, str(PROJECT_ROOT / "scripts" / "check_script_structure.py"),
         "--case", case_id, "--fail-fast"],
        dry_run,
    )


def step_3_make_audio(case_id: str, p: dict[str, Path], *, dry_run: bool, force: bool) -> None:
    if not force and p["narration"].exists() and p["alignment"].exists():
        print(f"  → make_audio_elevenlabs [skip — narration + alignment already exist]")
        return
    run_step(
        "make_audio_elevenlabs (per-beat mood mode)",
        [PYTHON, str(PROJECT_ROOT / "scripts" / "make_audio_elevenlabs.py"),
         "--case", case_id],
        dry_run,
    )


def step_4_visuals(case_id: str, p: dict[str, Path], *, dry_run: bool, force: bool) -> None:
    if not force and p["concat_list"].exists() and p["clips_manifest"].exists():
        print(f"  → build_visuals_track [skip — clips already exist]")
        return
    run_step(
        "build_visuals_track (Flux + Pika)",
        [PYTHON, str(PROJECT_ROOT / "scripts" / "build_visuals_track.py"),
         "--case", case_id],
        dry_run,
    )


def step_5_sound_design(case_id: str, p: dict[str, Path], *, dry_run: bool, force: bool) -> None:
    if not force and p["sound_design"].exists():
        print(f"  → build_sound_design [skip — sound_design.wav exists]")
        return
    # sound_design is graceful — failure falls through to narration-only audio at mix time.
    try:
        run_step(
            "build_sound_design (Freesound ambient + SFX)",
            [PYTHON, str(PROJECT_ROOT / "scripts" / "build_sound_design.py"),
             "--case", case_id],
            dry_run,
        )
    except subprocess.CalledProcessError:
        print(f"      ⚠  sound_design failed — render will continue with narration-only audio")


def step_6_copy_alignment(case_id: str, p: dict[str, Path], *, dry_run: bool, force: bool) -> None:
    """Renderer expects alignment.json adjacent to audio_mixed.mp3."""
    print(f"  → copy alignment for renderer lookup")
    if dry_run:
        print(f"      [dry-run] cp {p['alignment'].name} → {p['audio_mixed_alignment'].name}")
        return
    if not p["alignment"].exists():
        print(f"      ⚠  no alignment.json at {p['alignment']} — skipping (karaoke will be empty)")
        return
    p["case_dir"].mkdir(parents=True, exist_ok=True)
    shutil.copy2(p["alignment"], p["audio_mixed_alignment"])


def step_7_renderer_aliases(case_id: str, p: dict[str, Path], *, dry_run: bool, force: bool) -> None:
    """render_game_video.py expects game_id/audio_file/clips_manifest fields."""
    print(f"  → add renderer-required aliases to script_config.json")
    if dry_run:
        print(f"      [dry-run] would setdefault game_id/game_title/audio_file/clips_manifest")
        return
    cfg = json.loads(p["config"].read_text())
    cfg.setdefault("game_id", cfg["case_id"])
    cfg.setdefault("game_title", cfg.get("title", "") or cfg["case_id"])
    cfg.setdefault("audio_file", f"output/scripts/{cfg['case_id']}/audio_mixed.mp3")
    cfg.setdefault("clips_manifest", f"output/scripts/{cfg['case_id']}/clips_manifest.json")
    p["config"].write_text(json.dumps(cfg, indent=2))


def step_8_filters(case_id: str, p: dict[str, Path], *, dry_run: bool, force: bool) -> None:
    if not force and p["karaoke_filter"].exists() and p["top_title_filter"].exists():
        print(f"  → build_*_filter [skip — both filters exist]")
        return
    if not p["alignment"].exists():
        print(f"      ⚠  no alignment — skipping karaoke build (top_title still attempts)")
    else:
        run_step(
            "build_karaoke_filter",
            [PYTHON, str(PROJECT_ROOT / "scripts" / "build_karaoke_filter.py"),
             "--alignment", str(p["alignment"]),
             "--output", str(p["karaoke_filter"])],
            dry_run,
        )
    run_step(
        "build_top_title_filter",
        [PYTHON, str(PROJECT_ROOT / "scripts" / "build_top_title_filter.py"),
         "--config", str(p["config"]),
         "--alignment", str(p["alignment"]),
         "--output", str(p["top_title_filter"])],
        dry_run,
    )


def step_9_render_game_video(case_id: str, p: dict[str, Path], *, dry_run: bool, force: bool) -> None:
    """Invoke the existing game-short renderer. Builds hook_overlay.filter + concat list.

    The renderer also rebuilds audio_mixed.mp3 from its own pipeline — step 10
    overrides with our narration+sound_design mix.
    """
    run_step(
        "render_game_video (builds hook_overlay + concat + renderer audio)",
        [PYTHON, str(PROJECT_ROOT / "skill" / "game-short" / "render_game_video.py"),
         str(p["config"])],
        dry_run,
    )


def step_10_override_audio_mix(case_id: str, p: dict[str, Path], *, dry_run: bool, force: bool) -> None:
    """OVERWRITES the renderer's audio_mixed.mp3 with our narration + sound_design mix.

    The renderer (`render_game_video.py`) rebuilds audio_mixed from its own
    narration + music + SFX chain. For the story vertical we prefer the
    storyboard-first sound_design.wav (per-beat ambient + SFX + music brief),
    so we mix narration + sound_design AFTER the renderer runs, before
    final encode.
    """
    if not p["sound_design"].exists():
        print(f"  → audio mix override [skip — no sound_design.wav; renderer's audio_mixed kept]")
        return
    print(f"  → audio mix override (narration + sound_design → audio_mixed.mp3)")
    if dry_run:
        print(f"      [dry-run] ffmpeg amix narration + sound_design")
        return
    subprocess.run(
        ["ffmpeg", "-y",
         "-i", str(p["narration"]),
         "-i", str(p["sound_design"]),
         "-filter_complex",
         f"[1:a]volume={SOUND_BED_GAIN}[bg];[0:a]volume={NARRATION_GAIN}[vo];"
         f"[vo][bg]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[out]",
         "-map", "[out]",
         "-c:a", "libmp3lame", "-q:a", "2", "-ar", "44100",
         str(p["audio_mixed"])],
        check=True, capture_output=True,
    )


def step_11_final_encode(case_id: str, p: dict[str, Path], *, dry_run: bool, force: bool) -> None:
    if not force and p["final_mp4"].exists():
        print(f"  → final encode [skip — {p['final_mp4'].name} exists; use --force to re-encode]")
        return
    print(f"  → final encode → {p['final_mp4'].relative_to(PROJECT_ROOT)}")
    if dry_run:
        print(f"      [dry-run] ffmpeg concat + filters + audio_mixed → final mp4")
        return

    # Assemble vf chain from whichever filter files actually exist + non-empty
    vf_parts: list[str] = []
    for filt in (p["karaoke_filter"], p["top_title_filter"], p["hook_overlay_filter"]):
        if filt.exists() and filt.stat().st_size > 0:
            vf_parts.append(filt.read_text().strip())
    vf = ",".join(vf_parts) if vf_parts else "null"

    STORY_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "concat", "-safe", "0", "-i", str(p["concat_list"]),
         "-i", str(p["audio_mixed"]),
         "-vf", vf,
         "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "fast", "-crf", "22",
         "-c:a", "aac", "-b:a", "128k",
         "-shortest", "-movflags", "+faststart",
         str(p["final_mp4"])],
        check=True, capture_output=True,
    )


def step_12_mark_rendered(case_id: str, p: dict[str, Path], *, dry_run: bool, force: bool) -> None:
    run_step(
        "story_orchestrator --mark-status RENDERED",
        [PYTHON, str(PROJECT_ROOT / "scripts" / "story_orchestrator.py"),
         "--mark-status", case_id, "RENDERED"],
        dry_run,
    )


STEPS = [
    ("validate", step_1_validate),
    ("check_structure", step_2_check_structure),
    ("audio", step_3_make_audio),
    ("visuals", step_4_visuals),
    ("sound_design", step_5_sound_design),
    ("alignment_copy", step_6_copy_alignment),
    ("renderer_aliases", step_7_renderer_aliases),
    ("filters", step_8_filters),
    ("render_video", step_9_render_game_video),
    ("audio_mix_override", step_10_override_audio_mix),
    ("final_encode", step_11_final_encode),
    ("mark_rendered", step_12_mark_rendered),
]


# ---------------------------------------------------------------------------
# Budget guard
# ---------------------------------------------------------------------------

def budget_guard_ok(num_cases: int) -> tuple[bool, str]:
    """Check whether rendering N more cases would bust the EL monthly budget.

    Returns (ok, reason). Reads output/elevenlabs_usage.json populated by
    make_audio_elevenlabs.record_usage.
    """
    usage_file = PROJECT_ROOT / "output" / "elevenlabs_usage.json"
    if not usage_file.exists():
        return True, "no usage file yet — assuming first run"
    try:
        usage = json.loads(usage_file.read_text())
    except (json.JSONDecodeError, OSError):
        return True, "usage file unparseable — proceeding"
    month_key = date.today().strftime("%Y-%m")
    current_usd = usage.get(month_key, {}).get("usd", 0.0)
    budget = float(os.environ.get("ELEVENLABS_MONTHLY_BUDGET", "22.0"))
    projected = current_usd + (num_cases * 0.20)  # ~$0.20 EL per story
    if projected > budget:
        return False, (f"would project to ${projected:.2f} of ${budget:.2f} EL budget. "
                       f"Set ELEVENLABS_MONTHLY_BUDGET higher or wait.")
    return True, f"projected ${projected:.2f} of ${budget:.2f} EL budget — OK"


# ---------------------------------------------------------------------------
# Main per-case driver
# ---------------------------------------------------------------------------

def render_one(case_id: str, dry_run: bool, force: bool,
               from_step: int, only_step: int | None) -> bool:
    """Returns True on success, False on failure. Doesn't raise."""
    print(f"\n── Render: {case_id} ──")
    p = case_paths(case_id)
    t_start = time.time()

    try:
        for idx, (label, fn) in enumerate(STEPS, start=1):
            if only_step is not None and idx != only_step:
                continue
            if idx < from_step:
                print(f"  → {label} [skip — before --from-step {from_step}]")
                continue
            try:
                fn(case_id, p, dry_run=dry_run, force=force)
            except StepValidationError as e:
                print(f"      ✗ {label}: {e}", file=sys.stderr)
                return False
        elapsed = time.time() - t_start
        if not dry_run and p["final_mp4"].exists():
            size_mb = p["final_mp4"].stat().st_size / (1024 * 1024)
            print(f"\n  ✓ {case_id} rendered in {elapsed:.0f}s — "
                  f"{p['final_mp4'].relative_to(PROJECT_ROOT)} ({size_mb:.1f}MB)")
        return True
    except subprocess.CalledProcessError:
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--case", help="Single case id (SY_NN_X_slug)")
    g.add_argument("--batch", type=Path, help="picks_YYYY-MM-DD.json with picks[].case_id list")
    ap.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    ap.add_argument("--force", action="store_true", help="Re-run even if outputs exist")
    ap.add_argument("--from-step", type=int, default=1, help="Resume from step N (1-12)")
    ap.add_argument("--only-step", type=int, default=None, help="Run only step N")
    ap.add_argument("--skip-budget-check", action="store_true", help="Bypass EL budget guard")
    args = ap.parse_args()

    cases: list[str] = []
    if args.case:
        cases = [args.case]
    else:
        try:
            payload = json.loads(args.batch.read_text())
            cases = [pick["case_id"] for pick in payload.get("picks", [])]
        except (json.JSONDecodeError, OSError, KeyError) as e:
            print(f"ERROR: {args.batch}: {e}", file=sys.stderr)
            return 2
    if not cases:
        print("ERROR: no cases to render", file=sys.stderr)
        return 2

    # Budget guard (skipped on --dry-run or --skip-budget-check)
    if not args.dry_run and not args.skip_budget_check and args.from_step <= 3 and args.only_step != 11:
        ok, reason = budget_guard_ok(len(cases))
        print(f"── budget guard: {reason}")
        if not ok:
            return 3

    n_pass = 0
    n_fail = 0
    failed_cases: list[str] = []
    for case_id in cases:
        ok = render_one(case_id, args.dry_run, args.force, args.from_step, args.only_step)
        if ok:
            n_pass += 1
        else:
            n_fail += 1
            failed_cases.append(case_id)
            # Abort batch on first failure so we don't burn $$ on broken pipeline state
            if len(cases) > 1 and not args.dry_run:
                print(f"\n  ABORTING batch — {case_id} failed. Remaining cases not attempted.")
                break

    print(f"\n── render_story summary: {n_pass}/{len(cases)} succeeded, {n_fail} failed")
    if failed_cases:
        print(f"  failed: {', '.join(failed_cases)}")
    if not args.dry_run:
        est_spend = n_pass * ROUGH_COST_PER_CASE
        print(f"  estimated spend this run: ~${est_spend:.2f} ({n_pass} × ~${ROUGH_COST_PER_CASE:.2f})")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
