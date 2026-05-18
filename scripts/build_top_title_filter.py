#!/usr/bin/env python3
"""Build a top-of-screen title overlay FFmpeg drawtext filter chain.

Two modes:

  Singular video (default):
    A constant title is drawn at the top of the frame for the entire
    audio duration. Title text is read from the config's `game_title`
    field. Used for game/movie/case/mystery/etc. shorts where a single
    name should persist throughout.

  Top X / ranked (--mode topx):
    A different title is drawn during each beat's time window, matching
    the current ranked item. Each beat in the config must include a
    `top_title` field. Time windows are computed by string-matching each
    beat's `text` against the audio alignment characters.

Output: a single line of comma-separated drawtext expressions, suitable
to concatenate with the karaoke filter via:

    -vf "$(cat karaoke.filter),$(cat top_title.filter)"

Usage:
    python scripts/build_top_title_filter.py --config <path>
    python scripts/build_top_title_filter.py --config <path> --mode topx
    python scripts/build_top_title_filter.py --config <path> --output <path>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FONT = PROJECT_ROOT / "assets" / "fonts" / "Poppins-Bold.ttf"

# Render parameters — picked to complement the karaoke style at the bottom
TITLE_FONT_SIZE = 56
TITLE_FONT_COLOR = "white"
TITLE_BORDER_COLOR = "black"
TITLE_BORDER_WIDTH = 5
TITLE_Y = "h*0.06"  # 6% from the top


def _normalize_for_display(text: str) -> str:
    """Strip apostrophes + curly quotes (same convention as the karaoke filter
    to avoid the FFmpeg single-quote escape fragility)."""
    return (
        text.replace("’", "")
            .replace("‘", "")
            .replace("“", "")
            .replace("”", "")
            .replace("'", "")
            .replace('"', "")
    )


def _drawtext(text: str, start: float, end: float, font_path: Path) -> str:
    """One drawtext expression activated for [start, end]."""
    safe = _normalize_for_display(text).upper()
    return (
        f"drawtext=fontfile='{font_path}'"
        f":text='{safe}'"
        f":fontsize={TITLE_FONT_SIZE}"
        f":fontcolor={TITLE_FONT_COLOR}"
        f":bordercolor={TITLE_BORDER_COLOR}"
        f":borderw={TITLE_BORDER_WIDTH}"
        f":x=(w-text_w)/2"
        f":y={TITLE_Y}"
        f":enable='between(t,{start:.3f},{end:.3f})'"
    )


def build_singular_chain(title: str, audio_duration: float, font_path: Path) -> str:
    """One drawtext expression spanning the whole audio duration."""
    return _drawtext(title, 0.0, audio_duration, font_path)


def build_topx_chain(beats: list[dict], alignment: dict, font_path: Path) -> str:
    """One drawtext per beat. Each beat must have `top_title`.

    Time windows are derived from where each beat's `text` appears in the
    alignment's characters[] list (start of beat N+1 = end of beat N).
    """
    chars = alignment["characters"]
    starts = alignment["character_start_times_seconds"]
    ends = alignment["character_end_times_seconds"]
    spoken = "".join(chars)
    total_dur = ends[-1]

    # Locate each beat's start char
    position = 0
    beat_starts = []
    for b in beats:
        text = b.get("text", "")
        idx = spoken.find(text, position)
        if idx == -1:
            idx = spoken.find(text[:20], position)
        if idx == -1:
            raise SystemExit(f"top-title: beat text not found in spoken audio: {text[:40]!r}")
        beat_starts.append(starts[idx])
        position = idx + len(text)

    exprs = []
    for i, b in enumerate(beats):
        title = b.get("top_title")
        if not title:
            continue  # beats without top_title get no overlay during their window
        start_t = beat_starts[i]
        end_t = beat_starts[i + 1] if i + 1 < len(beats) else total_dur
        exprs.append(_drawtext(title, start_t, end_t, font_path))

    return ",".join(exprs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path,
                        help="Path to game_config.json or script_config.json")
    parser.add_argument("--mode", choices=["singular", "topx"], default=None,
                        help="Override auto-detection. Default: topx if any beat has `top_title`, else singular.")
    parser.add_argument("--alignment", type=Path, default=None,
                        help="Optional explicit alignment.json. Default: derive from config's audio_file.")
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT, help="Font file")
    parser.add_argument("--output", type=Path, default=None,
                        help="Write chain to this path. Otherwise print to stdout.")
    args = parser.parse_args()

    if not args.config.exists():
        sys.exit(f"ERROR: config not found: {args.config}")
    if not args.font.exists():
        sys.exit(f"ERROR: font not found: {args.font}")

    cfg = json.loads(args.config.read_text())

    # Locate alignment.json
    if args.alignment:
        align_path = args.alignment
    else:
        audio_file = PROJECT_ROOT / cfg["audio_file"]
        align_path = audio_file.parent / f"{audio_file.stem}.alignment.json"

    if not align_path.exists():
        sys.exit(f"ERROR: alignment file not found: {align_path}")
    alignment = json.loads(align_path.read_text())

    beats = cfg.get("beats", [])

    # Auto-detect mode
    if args.mode is None:
        has_top_titles = any(b.get("top_title") for b in beats)
        mode = "topx" if has_top_titles else "singular"
    else:
        mode = args.mode

    font_path = args.font.resolve()

    if mode == "topx":
        chain = build_topx_chain(beats, alignment, font_path)
    else:
        title = cfg.get("game_title") or cfg.get("case_title") or cfg.get("title")
        if not title:
            sys.exit("ERROR: singular mode requires `game_title`, `case_title`, or `title` in config")
        audio_dur = alignment["character_end_times_seconds"][-1]
        chain = build_singular_chain(title, audio_dur, font_path)

    if args.output:
        args.output.write_text(chain)
        print(f"wrote {len(chain)} chars to {args.output} (mode={mode})", file=sys.stderr)
    else:
        print(chain)


if __name__ == "__main__":
    main()
