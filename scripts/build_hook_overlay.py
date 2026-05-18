#!/usr/bin/env python3
"""Build a centered HOOK text overlay FFmpeg drawtext filter.

After SY_01 + SY_03 hit a ~4-sec avg watch time on TikTok (~9% retention),
the diagnosis was: muted-autoplay viewers couldn't read the hook before
swiping. Fix: large centered text overlay during the first 2.5 seconds
with the hook's first sentence — readable even on silent autoplay.

Position: upper-third of frame (no conflict with karaoke at the bottom
or the persistent top-title at the very top).

Timing:
  t=0.00 → 0.20s   fade in
  t=0.20 → 2.20s   fully visible
  t=2.20 → 2.50s   fade out
  t≥2.50s          gone (handed off to karaoke)

Output: one line of FFmpeg drawtext expression, suitable to chain via:

    -vf "$(cat karaoke.filter),$(cat top_title.filter),$(cat hook_overlay.filter)"

Usage:
    python scripts/build_hook_overlay.py --config output/scripts/SY_05_H_basement/script_config.json
    python scripts/build_hook_overlay.py --config <path> --output <path>
    python scripts/build_hook_overlay.py --config <path> --text "Override text"

Reads the hook text from the FIRST sentence of beats[0].text in the
config. Caps at 50 chars (3-4 short lines on the screen). Override
with --text if you want manual control.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _atomic import atomic_write_text  # noqa: E402

# Render parameters
DEFAULT_FONT = PROJECT_ROOT / "assets" / "fonts" / "Poppins-Bold.ttf"
HOOK_FONT_SIZE = 90              # large — must be readable at thumbnail size
HOOK_FONT_COLOR = "white"
HOOK_BORDER_COLOR = "black"
HOOK_BORDER_WIDTH = 6            # thick black outline for legibility on any background
HOOK_BOX_COLOR = "black@0.5"     # translucent black box behind text (extra contrast)
HOOK_BOX_BORDER_WIDTH = 24       # padding inside the box
HOOK_Y_FRACTION = 0.30           # upper third (h*0.30 from top)
HOOK_START_S = 0.0
HOOK_END_S = 2.5
HOOK_FADE_IN_S = 0.2
HOOK_FADE_OUT_S = 0.3
MAX_CHARS = 50                   # truncate longer hooks to stay readable


MIN_HOOK_CHARS = 12  # Below this, first "sentence" is probably just a label ("Day 2"); roll into next sentence


def extract_hook_text(config_path: Path, override: str | None = None) -> str:
    """Pull the hook text from beats[0].text — usually the violation/threat sentence.

    If the first sentence is very short (e.g. "Day 2." — a label, not a hook),
    keep extending into subsequent sentences until we have a meaningful chunk
    or hit MAX_CHARS.
    """
    if override:
        return override
    cfg = json.loads(config_path.read_text())
    beats = cfg.get("beats", [])
    if not beats:
        sys.exit(f"ERROR: no beats[] in {config_path}")
    raw = (beats[0].get("text") or "").strip()
    if not raw:
        sys.exit(f"ERROR: beats[0].text is empty in {config_path}")

    # Split on sentence-end punctuation while preserving the joining whitespace
    sentences = re.split(r"(?<=[.!?])\s+", raw)
    accum = ""
    for sent in sentences:
        if accum:
            candidate = (accum + " " + sent).rstrip(".!?,;:").strip()
        else:
            candidate = sent.rstrip(".!?,;:").strip()
        # If adding the next sentence would blow past MAX_CHARS, stop here
        # — unless we haven't even hit MIN_HOOK_CHARS yet (then grab anyway,
        # truncating later)
        if accum and len(candidate) > MAX_CHARS and len(accum) >= MIN_HOOK_CHARS:
            break
        accum = candidate
        if len(accum) >= MIN_HOOK_CHARS and len(accum) <= MAX_CHARS:
            # Good enough — but keep going if we're a tiny bit short and have room
            if len(accum) < int(MAX_CHARS * 0.6):
                continue
            break

    if not accum:
        accum = raw[:MAX_CHARS]

    if len(accum) > MAX_CHARS:
        accum = accum[:MAX_CHARS].rstrip() + "..."
    return accum


def _escape_for_drawtext(text: str) -> str:
    """FFmpeg drawtext needs single quotes escaped + colons backslash-escaped."""
    text = text.replace("\\", "\\\\")
    text = text.replace("'", r"\\'")
    text = text.replace(":", r"\:")
    return text


def build_hook_overlay_filter(text: str, font: Path = DEFAULT_FONT) -> str:
    """Compose the FFmpeg drawtext expression for the hook overlay."""
    if not font.exists():
        sys.exit(f"ERROR: font not found: {font}")
    escaped = _escape_for_drawtext(text)
    # alpha expression: fade-in over HOOK_FADE_IN_S, full from FADE_IN end to FADE_OUT start, fade-out, then 0
    fade_out_start = HOOK_END_S - HOOK_FADE_OUT_S
    alpha = (
        f"if(lt(t,{HOOK_START_S}),0,"
        f"if(lt(t,{HOOK_START_S + HOOK_FADE_IN_S}),(t-{HOOK_START_S})/{HOOK_FADE_IN_S},"
        f"if(lt(t,{fade_out_start}),1,"
        f"if(lt(t,{HOOK_END_S}),({HOOK_END_S}-t)/{HOOK_FADE_OUT_S},0))))"
    )
    enable = f"between(t,{HOOK_START_S},{HOOK_END_S})"
    drawtext = (
        f"drawtext="
        f"fontfile='{font}':"
        f"text='{escaped}':"
        f"fontsize={HOOK_FONT_SIZE}:"
        f"fontcolor={HOOK_FONT_COLOR}:"
        f"bordercolor={HOOK_BORDER_COLOR}:"
        f"borderw={HOOK_BORDER_WIDTH}:"
        f"box=1:boxcolor={HOOK_BOX_COLOR}:boxborderw={HOOK_BOX_BORDER_WIDTH}:"
        f"x=(w-text_w)/2:"
        f"y=h*{HOOK_Y_FRACTION}:"
        f"line_spacing=14:"
        f"alpha='{alpha}':"
        f"enable='{enable}'"
    )
    return drawtext


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path,
                        help="Path to script_config.json")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output path for the filter file (default: alongside config as hook_overlay.filter)")
    parser.add_argument("--text", default=None,
                        help="Override the auto-extracted hook text")
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT,
                        help="Font file path (default: Poppins-Bold)")
    args = parser.parse_args()

    if not args.config.exists():
        sys.exit(f"ERROR: config not found: {args.config}")

    text = extract_hook_text(args.config, args.text)
    drawtext = build_hook_overlay_filter(text, args.font.resolve())

    out_path = args.output or (args.config.parent / "hook_overlay.filter")
    atomic_write_text(out_path, drawtext + "\n")
    print(f"  ✓ {out_path.relative_to(PROJECT_ROOT) if out_path.is_relative_to(PROJECT_ROOT) else out_path}")
    print(f"    text=\"{text}\" ({len(text)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
