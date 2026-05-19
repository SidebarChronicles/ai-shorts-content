#!/usr/bin/env python3
"""Pick today's 4 stubs to render. Ranks queue by mined_score + tweaks skew.

Ranking inputs:
  - Each stub's "Mined score: X/100" (from /research-stories stub generator)
  - suggest_tweaks file (if present) for sub-genre + voice skews
  - Sub-genre round-robin balance — hard cap of 3-of-4 in a single sub-genre
  - Excludes already RENDERED/DELIVERED

Output:
  output/daily/picks_YYYY-MM-DD.json

Usage:
    python scripts/pick_today.py                # interactive: prints + asks 'y' to write
    python scripts/pick_today.py --auto         # writes without prompting (used by /morning)
    python scripts/pick_today.py --dry-run      # prints picks, doesn't write
    python scripts/pick_today.py --count 6      # override default 4
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import load_dotenv  # noqa: E402
from _atomic import atomic_write_json  # noqa: E402
from _queue_scan import scan_queue  # noqa: E402  — shared scanner; see scripts/_queue_scan.py

load_dotenv(PROJECT_ROOT / ".env")

DAILY_DIR = PROJECT_ROOT / "output" / "daily"
ANALYTICS_DIR = PROJECT_ROOT / "output" / "analytics"

DEFAULT_COUNT = 4
SUBGENRE_CAP = 3  # max picks from a single sub-genre per day


# ---------------------------------------------------------------------------
# Tweaks file reader (for skews)
# ---------------------------------------------------------------------------

def read_tweaks_skews() -> dict:
    """Return {'preferred_subgenre': str|None, 'preferred_voices': [str]}."""
    if not ANALYTICS_DIR.exists():
        return {}
    today_iso = date.today().isoformat()
    tweaks_path = ANALYTICS_DIR / f"suggested_tweaks_{today_iso}.md"
    if not tweaks_path.exists():
        return {}
    text = tweaks_path.read_text()
    skews: dict = {}
    sub_m = re.search(r"Skew today's batch toward `(\w+)`", text)
    if sub_m:
        skews["preferred_subgenre"] = sub_m.group(1)
    voices_m = re.search(r"Prefer voices: (.+)", text)
    if voices_m:
        names = re.findall(r"`(\w+)`", voices_m.group(1))
        if names:
            skews["preferred_voices"] = names
    return skews


# ---------------------------------------------------------------------------
# Ranker
# ---------------------------------------------------------------------------

def rank_picks(queued: list[dict], count: int, skews: dict) -> list[dict]:
    """Return up to `count` picks with rationale, honoring sub-genre cap."""
    # Score each queued item: base = mined_score; bonuses for skew matches
    pref_sub = skews.get("preferred_subgenre")
    pref_voices = set(skews.get("preferred_voices") or [])

    def score_one(item: dict) -> float:
        s = item["mined_score"]
        if pref_sub and item["subgenre"] == pref_sub:
            s += 10  # sub-genre skew bonus
        if pref_voices and item["voice"] in pref_voices:
            s += 5  # voice skew bonus
        return s

    candidates = [(score_one(it), it) for it in queued]
    candidates.sort(key=lambda x: x[0], reverse=True)

    picks: list[dict] = []
    sub_counts: Counter = Counter()
    for s, it in candidates:
        if len(picks) >= count:
            break
        if sub_counts[it["subgenre"]] >= SUBGENRE_CAP:
            continue  # hard cap reached
        rationale_parts: list[str] = [f"mined_score={it['mined_score']:.1f}"]
        if pref_sub and it["subgenre"] == pref_sub:
            rationale_parts.append(f"+10 sub-genre skew (`{pref_sub}`)")
        if pref_voices and it["voice"] in pref_voices:
            rationale_parts.append(f"+5 voice skew (`{it['voice']}`)")
        picks.append({
            "case_id": it["case_id"],
            "subgenre": it["subgenre"],
            "voice": it["voice"],
            "gender": it["gender"],
            "score": round(s, 2),
            "rationale": "; ".join(rationale_parts),
        })
        sub_counts[it["subgenre"]] += 1
    return picks


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", type=int, default=DEFAULT_COUNT, help=f"How many to pick (default {DEFAULT_COUNT})")
    ap.add_argument("--auto", action="store_true", help="Non-interactive; write without confirm prompt")
    ap.add_argument("--dry-run", action="store_true", help="Print picks; don't write file")
    ap.add_argument("--date", default=None, help="Override output filename date (default: today)")
    args = ap.parse_args()

    items = scan_queue()
    queued = [it for it in items if it["status"] == "QUEUED"]
    if not queued:
        print("ERROR: no QUEUED stubs in story_queue/. Run /research-stories to top up.", file=sys.stderr)
        return 2

    skews = read_tweaks_skews()
    picks = rank_picks(queued, args.count, skews)
    if len(picks) < args.count:
        print(f"⚠  Only {len(picks)} picks possible (queue depth + sub-genre cap)")

    print(f"\n── Today's picks ({len(picks)}/{args.count}) ──")
    if skews:
        print(f"   skews applied: {skews}")
    for i, pk in enumerate(picks, 1):
        v = pk["voice"] or "?"
        g = pk["gender"] or "?"
        print(f"   {i}. [{pk['score']:5.1f}] {pk['case_id']}  ({pk['subgenre']}, voice={v}, gender={g})")
        print(f"      → {pk['rationale']}")
    print(f"\n   Queue depth after pick: {len(queued) - len(picks)}")
    print()

    if args.dry_run:
        print("[dry-run] no file written")
        return 0

    if not args.auto:
        try:
            ans = input("Write picks file? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nabort")
            return 1
        if ans != "y":
            print("aborted; no file written")
            return 1

    out_date = args.date or date.today().isoformat()
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DAILY_DIR / f"picks_{out_date}.json"
    payload = {
        "date": out_date,
        "count": len(picks),
        "skews_applied": skews,
        "picks": picks,
        "queue_depth_after": len(queued) - len(picks),
    }
    atomic_write_json(out_path, payload, indent=2)
    print(f"  ✓ wrote {out_path.relative_to(PROJECT_ROOT)}")
    print(f"  next: python scripts/render_story.py --batch {out_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
