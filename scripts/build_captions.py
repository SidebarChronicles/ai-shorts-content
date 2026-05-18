#!/usr/bin/env python3
"""Generate IG Reels + TikTok captions from a YouTube description.md sidecar.

Each video uploaded via `upload_to_youtube.py` already has a `<id>.description.md`
file under its `videos_dir/` with sections:

    ## Title         (one-line title)
    ## DESCRIPTION   (paragraphs + AI disclosure + music attribution + hashtags)
    ## Tags          (comma-separated keywords for the YouTube tags API)

This script reads that file and emits two per-platform caption sidecars:

    <id>.ig_caption.txt   Instagram Reels (100-300 chars, 5 hashtags, emoji-friendly)
    <id>.tt_caption.txt   TikTok          (80-150 chars, 3-5 hashtags, punchy)

Both include the same AI-content disclosure and music attribution required by
platform policy (IG + TikTok both require AI-disclosure on AI-narrated shorts
since 2024).

Usage:
    python scripts/build_captions.py --case SY_01_S_lakecabin
    python scripts/build_captions.py --videos-dir output/story_videos --all-pending
    python scripts/build_captions.py --case GG_07_marathon --videos-dir output/game_videos
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _atomic import atomic_write_text  # noqa: E402

# Per-platform tuning
IG_TARGET_CHAR_RANGE = (100, 300)
IG_HASHTAG_COUNT = 5
TT_TARGET_CHAR_RANGE = (80, 200)
TT_HASHTAG_COUNT = 5

# Standard AI / music disclosures (compact for caption use)
AI_DISCLOSURE = "⚠️ AI-narrated story"
MUSIC_DISCLOSURE = "🎵 Kevin MacLeod (CC-BY 4.0)"


# ---------------------------------------------------------------------------
# Description parser
# ---------------------------------------------------------------------------

def _extract_block(text: str, section: str) -> str:
    """Extract content inside ```...``` immediately under `## {section}`."""
    pattern = rf"##\s+{re.escape(section)}\s*\n+```\n(.*?)```"
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return ""
    return m.group(1).strip()


def parse_description(path: Path) -> dict:
    text = path.read_text()
    title = _extract_block(text, "Title")
    description = _extract_block(text, "DESCRIPTION")
    tags = _extract_block(text, "Tags")
    return {"title": title, "description": description, "tags": tags}


def _extract_hashtags(description_block: str) -> list[str]:
    """Pull hashtags from the description's #-prefixed line."""
    # Search any line that starts with whitespace + # + word
    tags: list[str] = []
    for line in description_block.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            tags.extend(re.findall(r"#\w+", stripped))
    return tags


def _extract_first_paragraph(description_block: str) -> str:
    """Return the first non-empty paragraph (used as the platform-caption opener)."""
    for paragraph in description_block.split("\n\n"):
        p = paragraph.strip()
        if p and not p.startswith("#") and not p.startswith("⚠") and not p.startswith("🎵"):
            return p
    return ""


# ---------------------------------------------------------------------------
# Per-platform formatters
# ---------------------------------------------------------------------------

def _normalize_tag(tag: str, platform: str) -> str:
    """Strip leading '#' and lowercase to a consistent form, then re-prepend."""
    raw = tag.lstrip("#")
    if platform == "tt":
        # TikTok hashtags are typically lowercase, single-word, no camelCase
        return "#" + raw.lower()
    # Instagram is fine with mixed-case hashtags
    return "#" + raw


def build_instagram_caption(parsed: dict) -> str:
    """Compose an IG-Reels-shaped caption from the parsed description fields."""
    description = parsed["description"]
    first_para = _extract_first_paragraph(description)
    # Pull hashtags from description block + tags block; merge + dedupe
    tags_from_desc = _extract_hashtags(description)
    tags_from_tags_block = [
        "#" + t.strip().replace(" ", "")
        for t in parsed["tags"].split(",")
        if t.strip()
    ]
    seen: set[str] = set()
    merged_tags: list[str] = []
    for raw in tags_from_desc + tags_from_tags_block:
        norm = _normalize_tag(raw, "ig")
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        merged_tags.append(norm)
    # Cap to IG_HASHTAG_COUNT (algorithm favors fewer-mixed-with-text over hashtag walls)
    merged_tags = merged_tags[:IG_HASHTAG_COUNT]

    # Tease line (the IG algorithm rewards a curiosity hook before the cut)
    tease = "What would you do? 👀"

    lines = [
        first_para,
        "",
        tease,
        "",
        f"Full story on YouTube — link in bio 🔗",
        f"{AI_DISCLOSURE} • {MUSIC_DISCLOSURE}",
        "",
        " ".join(merged_tags),
    ]
    caption = "\n".join(lines).strip()
    return caption


def build_tiktok_caption(parsed: dict) -> str:
    """Compose a TikTok-shaped caption (short, hashtags at end)."""
    description = parsed["description"]
    first_para = _extract_first_paragraph(description)
    # Take the FIRST sentence of the first paragraph for TT (punchier)
    first_sentence = re.split(r"(?<=[.!?])\s+", first_para, maxsplit=1)[0]

    tags_from_desc = _extract_hashtags(description)
    tags_from_tags_block = [
        "#" + t.strip().replace(" ", "")
        for t in parsed["tags"].split(",")
        if t.strip()
    ]
    seen: set[str] = set()
    merged_tags: list[str] = []
    for raw in tags_from_desc + tags_from_tags_block:
        norm = _normalize_tag(raw, "tt")
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        merged_tags.append(norm)
    merged_tags = merged_tags[:TT_HASHTAG_COUNT]

    # TT format: hook → AI disclosure inline → hashtags
    parts = [first_sentence, AI_DISCLOSURE, " ".join(merged_tags)]
    caption = " ".join(p for p in parts if p)
    return caption.strip()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def find_description_path(case_id: str, videos_dir: Path | None) -> Path | None:
    """Find the description.md for a case_id under videos_dir (or default search)."""
    if videos_dir:
        p = videos_dir / f"{case_id}.description.md"
        if p.exists():
            return p
        return None
    # Default: search all known videos_dir locations
    candidates = [
        "output/story_videos",
        "output/game_videos",
        "output/movie_videos",
        "output/mythology_videos",
        "output/mystery_videos",
        "output/topx_videos",
        "output/finance_videos",
        "output/videos",
    ]
    for c in candidates:
        p = PROJECT_ROOT / c / f"{case_id}.description.md"
        if p.exists():
            return p
    return None


def generate_for_case(case_id: str, videos_dir: Path | None,
                      dry_run: bool = False) -> tuple[Path, Path] | None:
    desc_path = find_description_path(case_id, videos_dir)
    if not desc_path:
        print(f"  ✗ {case_id}: no description.md found", file=sys.stderr)
        return None
    parsed = parse_description(desc_path)
    if not parsed["description"]:
        print(f"  ✗ {case_id}: empty DESCRIPTION block", file=sys.stderr)
        return None

    ig_caption = build_instagram_caption(parsed)
    tt_caption = build_tiktok_caption(parsed)

    ig_path = desc_path.parent / f"{case_id}.ig_caption.txt"
    tt_path = desc_path.parent / f"{case_id}.tt_caption.txt"

    if dry_run:
        print(f"\n── {case_id} (dry-run) ──")
        print(f"\n  IG ({len(ig_caption)} chars):")
        print("  " + ig_caption.replace("\n", "\n  "))
        print(f"\n  TT ({len(tt_caption)} chars):")
        print("  " + tt_caption.replace("\n", "\n  "))
    else:
        atomic_write_text(ig_path, ig_caption + "\n")
        atomic_write_text(tt_path, tt_caption + "\n")
        print(f"  ✓ {case_id}  →  IG ({len(ig_caption)}c) + TT ({len(tt_caption)}c)")

    # Caption-length sanity warnings
    if not (IG_TARGET_CHAR_RANGE[0] <= len(ig_caption) <= IG_TARGET_CHAR_RANGE[1]):
        print(f"    ⚠  IG caption {len(ig_caption)}c outside target "
              f"{IG_TARGET_CHAR_RANGE[0]}-{IG_TARGET_CHAR_RANGE[1]}",
              file=sys.stderr)
    if not (TT_TARGET_CHAR_RANGE[0] <= len(tt_caption) <= TT_TARGET_CHAR_RANGE[1]):
        print(f"    ⚠  TT caption {len(tt_caption)}c outside target "
              f"{TT_TARGET_CHAR_RANGE[0]}-{TT_TARGET_CHAR_RANGE[1]}",
              file=sys.stderr)

    return ig_path, tt_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--case", help="One case id (e.g. SY_01_S_lakecabin)")
    g.add_argument("--all-pending", action="store_true",
                   help="Generate captions for every case in --videos-dir that doesn't already have them")

    parser.add_argument("--videos-dir", type=Path, default=None,
                        help="Limit search to one videos dir (e.g. output/story_videos)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print captions to stdout instead of writing files")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate captions even if files already exist")
    args = parser.parse_args()

    if args.case:
        result = generate_for_case(args.case, args.videos_dir, dry_run=args.dry_run)
        return 0 if result else 1

    # --all-pending mode
    if not args.videos_dir:
        print("ERROR: --all-pending requires --videos-dir", file=sys.stderr)
        return 2
    if not args.videos_dir.exists():
        print(f"ERROR: {args.videos_dir} not found", file=sys.stderr)
        return 2

    n = 0
    for desc in sorted(args.videos_dir.glob("*.description.md")):
        case_id = desc.stem.removesuffix(".description")
        ig_path = desc.parent / f"{case_id}.ig_caption.txt"
        tt_path = desc.parent / f"{case_id}.tt_caption.txt"
        if not args.force and ig_path.exists() and tt_path.exists():
            print(f"  · skip {case_id}  (captions already exist; --force to regen)")
            continue
        generate_for_case(case_id, args.videos_dir, dry_run=args.dry_run)
        n += 1
    if args.dry_run:
        print(f"\n  [dry-run] would have generated for {n} cases")
    else:
        print(f"\n✓ Generated captions for {n} cases.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
