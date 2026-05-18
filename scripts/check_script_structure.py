#!/usr/bin/env python3
"""Lint script_config.json + alignment.json for retention-playbook compliance.

Checks (per the May 18 2026 Retention Playbook):

  HOOK
    - beat[0].text is ≤12 words
    - beat[0] spoken time is ≤2.5s (when alignment.json available)
    - hook does NOT start with forbidden filler ("Hey guys", "Did you know",
      "In this video", "What's up", "Welcome back", "So today")
    - hook is NOT a question that requires the rest of the video to answer
      (research shows declarative-with-payload outperforms question-hooks)

  MID-ANCHOR (only enforced on 7-beat structures)
    - beat[3] (the mid_anchor) starts in the 28-33s window
    - beat[3].text contains a numeric stat OR a strong contradiction marker
      ("but", "actually", "in reality", "the twist", percent, dollar amount)

  TOTAL
    - total spoken duration in 45-65s range
    - script has at minimum 4 beats (legacy) or 7 beats (new canon)

Usage:
    python scripts/check_script_structure.py              # lint ALL cases
    python scripts/check_script_structure.py --case GG_11 # one case
    python scripts/check_script_structure.py --fail-fast  # exit 1 on first fail
    python scripts/check_script_structure.py --strict     # demand 7-beat

Exit codes:
  0 — all checks passed
  1 — one or more cases failed at least one check
  2 — usage / I/O error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = PROJECT_ROOT / "assets" / "audio"
SCRIPTS_DIR = PROJECT_ROOT / "output" / "scripts"

# Thresholds (from the Retention Playbook)
HOOK_MAX_WORDS = 12
HOOK_MAX_SECONDS = 2.5
MID_ANCHOR_WINDOW = (28.0, 33.0)
TOTAL_DUR_RANGE = (45.0, 65.0)

FORBIDDEN_HOOK_PREFIXES = (
    "hey guys",
    "did you know",
    "in this video",
    "what's up",
    "welcome back",
    "welcome to",
    "so today",
    "today we",
    "let me tell you",
    "have you ever",
)

# Strong contradiction / stat markers we want to see in the mid_anchor beat
ANCHOR_MARKERS = (
    r"\b\d+%",            # percentages
    r"\$\d",              # dollar amounts
    r"\b\d{2,}\b",        # any two-or-more-digit number
    r"\bbut\b",
    r"\bactually\b",
    r"\bin reality\b",
    r"\bthe twist\b",
    r"\bhowever\b",
    r"\bexcept\b",
)


def _load_alignment(case_id: str):
    p = AUDIO_DIR / f"narration_{case_id}.alignment.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _load_config(case_id: str):
    for filename in ("script_config.json", "game_config.json"):
        p = SCRIPTS_DIR / case_id / filename
        if p.exists():
            try:
                return json.loads(p.read_text()), filename
            except (json.JSONDecodeError, OSError):
                pass
    return None, None


def _beat_start_seconds(alignment: dict, beat_text: str) -> float | None:
    """Best-effort: find where this beat starts in the alignment timeline."""
    if not alignment or not beat_text:
        return None
    spoken = "".join(alignment["characters"])
    starts = alignment["character_start_times_seconds"]
    # try exact, then first 30 chars, then first 15 chars
    for probe in (beat_text, beat_text[:30], beat_text[:15]):
        idx = spoken.find(probe)
        if idx >= 0:
            return float(starts[idx])
    return None


def _word_count(s: str) -> int:
    return len(re.findall(r"\b\w+\b", s.strip()))


def lint_case(case_id: str, *, strict: bool = False) -> tuple[bool, list[str], list[str]]:
    """Return (passed, errors, warnings). 'passed' is True only if no errors."""
    errors: list[str] = []
    warnings: list[str] = []

    cfg, source_name = _load_config(case_id)
    if cfg is None:
        return False, [f"no script_config.json or game_config.json under output/scripts/{case_id}/"], []

    beats = cfg.get("beats", [])
    if not beats:
        errors.append("config has no 'beats' array")
        return False, errors, warnings

    if strict and len(beats) < 7:
        errors.append(f"strict mode: expected 7-beat structure, got {len(beats)} beats")
    elif len(beats) < 4:
        errors.append(f"too few beats ({len(beats)}) — minimum 4")

    alignment = _load_alignment(case_id)

    # -- Hook checks --
    hook_text = beats[0].get("text", "")
    hook_words = _word_count(hook_text)
    if hook_words > HOOK_MAX_WORDS:
        errors.append(f"hook is {hook_words} words (max {HOOK_MAX_WORDS}): \"{hook_text[:60]}…\"")

    lower = hook_text.lower().lstrip()
    for forbidden in FORBIDDEN_HOOK_PREFIXES:
        if lower.startswith(forbidden):
            errors.append(f"hook starts with forbidden filler \"{forbidden}\"")
            break

    if hook_text.rstrip().endswith("?"):
        warnings.append(
            f"hook is a question — research shows declarative-with-payload retains better: \"{hook_text[:60]}…\""
        )

    if alignment:
        total_dur = alignment["character_end_times_seconds"][-1]
        # Hook duration ≈ start of beat[1] minus start of beat[0]
        if len(beats) >= 2:
            b1_start = _beat_start_seconds(alignment, beats[1].get("text", "")) or total_dur
            b0_start = _beat_start_seconds(alignment, hook_text) or 0.0
            hook_dur = b1_start - b0_start
            if hook_dur > HOOK_MAX_SECONDS:
                errors.append(
                    f"hook is {hook_dur:.2f}s (max {HOOK_MAX_SECONDS:.1f}s): "
                    f"\"{hook_text[:60]}…\""
                )

        # -- Total duration check --
        if not (TOTAL_DUR_RANGE[0] <= total_dur <= TOTAL_DUR_RANGE[1]):
            errors.append(
                f"total spoken duration {total_dur:.1f}s outside target "
                f"{TOTAL_DUR_RANGE[0]}-{TOTAL_DUR_RANGE[1]}s"
            )

        # -- Mid-anchor checks (7-beat only) --
        if len(beats) >= 7:
            ma_text = beats[3].get("text", "")
            ma_start = _beat_start_seconds(alignment, ma_text)
            if ma_start is None:
                warnings.append("mid_anchor beat could not be located in alignment")
            elif not (MID_ANCHOR_WINDOW[0] <= ma_start <= MID_ANCHOR_WINDOW[1]):
                errors.append(
                    f"mid_anchor starts at {ma_start:.1f}s, outside target "
                    f"{MID_ANCHOR_WINDOW[0]}-{MID_ANCHOR_WINDOW[1]}s window"
                )

            # Does mid_anchor carry a meaningful stat/contradiction?
            has_marker = any(re.search(pat, ma_text, re.IGNORECASE) for pat in ANCHOR_MARKERS)
            if not has_marker:
                warnings.append(
                    "mid_anchor lacks numeric stat or contradiction marker — "
                    "second-30 should be the biggest punch in the video"
                )
        elif strict:
            errors.append("strict mode: 7-beat structure required for mid_anchor compliance")
        else:
            warnings.append(
                f"legacy {len(beats)}-beat structure — new canon is 7 beats with explicit mid_anchor"
            )

    else:
        warnings.append("no alignment.json yet — duration checks skipped (run make_audio_elevenlabs first)")

    return (len(errors) == 0), errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default=None, help="Lint just this case id; otherwise lint all")
    parser.add_argument("--strict", action="store_true", help="Require 7-beat structure")
    parser.add_argument("--fail-fast", action="store_true", help="Exit on first failing case")
    parser.add_argument("--quiet", action="store_true", help="Only print failures")
    args = parser.parse_args()

    if args.case:
        cases = [args.case]
    else:
        if not SCRIPTS_DIR.exists():
            print(f"ERROR: {SCRIPTS_DIR} does not exist", file=sys.stderr)
            return 2
        cases = sorted(d.name for d in SCRIPTS_DIR.iterdir() if d.is_dir())

    n_total = len(cases)
    n_pass = 0
    n_fail = 0
    any_failed = False

    for case_id in cases:
        passed, errors, warnings = lint_case(case_id, strict=args.strict)
        if passed and not warnings and args.quiet:
            n_pass += 1
            continue
        if passed and not warnings:
            print(f"✓ {case_id}")
            n_pass += 1
            continue

        status = "✓" if passed else "✗"
        print(f"{status} {case_id}")
        for e in errors:
            print(f"    ERROR:   {e}")
        for w in warnings:
            print(f"    warn:    {w}")

        if passed:
            n_pass += 1
        else:
            n_fail += 1
            any_failed = True
            if args.fail_fast:
                break

    print(f"\n  {n_pass}/{n_total} passed, {n_fail} failed")
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
