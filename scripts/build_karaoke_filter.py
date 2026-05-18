#!/usr/bin/env python3
"""Build a chained FFmpeg drawtext filter for word-by-word karaoke captions.

Reads an ElevenLabs alignment.json (per-character timing) and produces one
drawtext expression per spoken word, chained into a single -vf filter string.

Captions render at ~72% screen height (above YouTube's lower UI safe zone)
in yellow with a black outline. Each word appears only during its spoken
window; previously-spoken and upcoming words don't render at all.
"""

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FONT = PROJECT_ROOT / "assets" / "fonts" / "Poppins-Bold.ttf"

MIN_WORDS = 10  # below this, treat alignment as truncated and skip captions

FONT_SIZE = 84
FONT_COLOR = "yellow"
BORDER_COLOR = "black"
BORDER_WIDTH = 6
Y_POSITION = "h*0.72"  # above YouTube UI safe zone (bottom ~25%)


def extract_words(alignment: dict) -> list[tuple[str, float, float]]:
    """Group alignment characters into (word, start, end) tuples on whitespace.

    Post-processes to clamp each word's end time to the next word's start
    time (minus a small gap). Without this, words ending in sentence
    punctuation (e.g. "smiled.") whose `end` includes the period's duration
    overlap visually with the next word that begins before the period
    finishes — viewer sees two captions stacked.
    """
    chars = alignment["characters"]
    starts = alignment["character_start_times_seconds"]
    ends = alignment["character_end_times_seconds"]

    raw_words: list[tuple[str, float, float]] = []
    cur_chars: list[str] = []
    cur_start: float | None = None
    cur_end: float | None = None

    for i, ch in enumerate(chars):
        if ch.isspace():
            if cur_chars:
                raw_words.append(("".join(cur_chars), cur_start, cur_end))
                cur_chars = []
                cur_start = None
                cur_end = None
        else:
            if not cur_chars:
                cur_start = starts[i]
            cur_chars.append(ch)
            cur_end = ends[i]

    if cur_chars:
        raw_words.append(("".join(cur_chars), cur_start, cur_end))

    # Clamp each word's end to the next word's start with a 40ms safety gap
    # so two captions are never on screen simultaneously.
    CAPTION_GAP_SEC = 0.04
    clamped: list[tuple[str, float, float]] = []
    for idx, (w, s, e) in enumerate(raw_words):
        if idx + 1 < len(raw_words):
            next_start = raw_words[idx + 1][1]
            e = min(e, max(s, next_start - CAPTION_GAP_SEC))
        clamped.append((w, s, e))
    return clamped


def normalize_word(word: str) -> str:
    """Strip punctuation that breaks karaoke rhythm; uppercase.

    Removes ALL apostrophes (curly + straight) — "it's" → "ITS". Apostrophes
    inside drawtext `text='...'` values are fragile to escape across shell
    + filter-graph parsing layers, and word-flash captions read fine without
    them. Same for em-dashes and other non-letter punctuation.
    """
    # Normalize curly quotes to straight (so the strip below catches them)
    word = word.replace("’", "'").replace("‘", "'")
    word = word.replace("“", '"').replace("”", '"')
    # Drop ALL apostrophes from inside the word
    word = word.replace("'", "")
    # Drop ALL ASCII quotes
    word = word.replace('"', "")
    # Strip surrounding/internal sentence punctuation we don't want shown
    stripped = word.strip(".,;:!?()[]{}—–-")
    return stripped.upper()


def escape_drawtext(text: str) -> str:
    """Escape a word for inclusion in drawtext `text='...'`.

    After normalize_word, apostrophes and other shell-fragile chars are gone.
    Backslashes still need filter-graph escaping (rare in word text but safe).
    """
    return text.replace("\\", "\\\\")


def fmt_time(t: float) -> str:
    return f"{t:.3f}"


def build_chain(alignment_path: Path | str, font_path: Path | str = DEFAULT_FONT) -> str:
    """Build the drawtext filter chain. Empty string = skip captions."""
    alignment_path = Path(alignment_path)
    font_path = Path(font_path)

    if not alignment_path.exists():
        return ""

    try:
        alignment = json.loads(alignment_path.read_text())
    except (json.JSONDecodeError, OSError):
        return ""

    words = extract_words(alignment)
    if len(words) < MIN_WORDS:
        return ""

    if not font_path.exists():
        raise FileNotFoundError(f"Font not found: {font_path}")

    font_str = str(font_path.resolve())

    exprs = []
    for raw, start, end in words:
        word = normalize_word(raw)
        if not word:
            continue
        text = escape_drawtext(word)
        exprs.append(
            f"drawtext=fontfile='{font_str}'"
            f":text='{text}'"
            f":fontsize={FONT_SIZE}"
            f":fontcolor={FONT_COLOR}"
            f":bordercolor={BORDER_COLOR}"
            f":borderw={BORDER_WIDTH}"
            f":x=(w-text_w)/2"
            f":y={Y_POSITION}"
            f":enable='between(t,{fmt_time(start)},{fmt_time(end)})'"
        )

    return ",".join(exprs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alignment", required=True, type=Path,
                        help="Path to alignment.json from ElevenLabs")
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT,
                        help=f"Font file (default: {DEFAULT_FONT.name})")
    parser.add_argument("--output", type=Path, default=None,
                        help="Write chain to this file. Otherwise print to stdout.")
    args = parser.parse_args()

    chain = build_chain(args.alignment, args.font)
    if not chain:
        print("warning: karaoke chain empty (alignment missing or too few words)",
              file=sys.stderr)
        sys.exit(1)

    if args.output:
        args.output.write_text(chain)
        print(f"wrote {len(chain)} chars to {args.output}", file=sys.stderr)
    else:
        print(chain)


if __name__ == "__main__":
    main()
