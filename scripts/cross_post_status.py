#!/usr/bin/env python3
"""Cross-post status tracker for IG Reels + TikTok manual posting workflow.

Auto-pulls YouTube uploads from each vertical's `_posted.json` (the existing
ledger written by upload_to_youtube.py) and tracks IG + TikTok publish state
in `output/cross_post_status.json`. You manually mark videos as posted
after AirDropping + posting them from your phone.

Usage:
    # See everything pending
    python scripts/cross_post_status.py --pending

    # See pending on just IG
    python scripts/cross_post_status.py --pending ig

    # Mark a video as posted (after you tap "Post" on your phone)
    python scripts/cross_post_status.py --mark SY_01_S_lakecabin ig
    python scripts/cross_post_status.py --mark SY_01_S_lakecabin tt

    # Show the full status table
    python scripts/cross_post_status.py --list

    # Print the bundle paths for one case (MP4 + caption files) — for quick AirDrop
    python scripts/cross_post_status.py --airdrop SY_01_S_lakecabin

    # Refresh from posted ledgers (auto-detect newly-uploaded videos)
    python scripts/cross_post_status.py --refresh

Output structure (`output/cross_post_status.json`):
    {
      "SY_01_S_lakecabin": {
        "videos_dir": "output/story_videos",
        "youtube":   "2026-05-18T16:25:00-04:00",
        "instagram": null,
        "tiktok":    null
      },
      ...
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _atomic import atomic_write_json  # noqa: E402

STATUS_FILE = PROJECT_ROOT / "output" / "cross_post_status.json"

# Vertical-to-videos-dir map; mirrors upload_to_youtube.py + SKILL.md STEP 4
VIDEOS_DIRS = [
    "output/story_videos",
    "output/game_videos",
    "output/movie_videos",
    "output/mythology_videos",
    "output/mystery_videos",
    "output/topx_videos",
    "output/finance_videos",
    "output/videos",  # legacy cases
]

PLATFORM_NAMES = {
    "yt": "youtube",
    "youtube": "youtube",
    "ig": "instagram",
    "instagram": "instagram",
    "tt": "tiktok",
    "tiktok": "tiktok",
}


# ---------------------------------------------------------------------------
# State load / save
# ---------------------------------------------------------------------------

def load_status() -> dict[str, dict]:
    if not STATUS_FILE.exists():
        return {}
    try:
        return json.loads(STATUS_FILE.read_text())
    except json.JSONDecodeError:
        return {}


def save_status(data: dict[str, dict]) -> None:
    atomic_write_json(STATUS_FILE, data, indent=2, sort_keys=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Refresh from YouTube posted ledgers
# ---------------------------------------------------------------------------

def refresh_from_posted_ledgers(state: dict[str, dict]) -> int:
    """Scan each videos_dir's _posted.json and ensure every YouTube-posted case
    has a state entry. Returns count of newly-added cases."""
    added = 0
    for rel in VIDEOS_DIRS:
        videos_dir = PROJECT_ROOT / rel
        posted_path = videos_dir / "_posted.json"
        if not posted_path.exists():
            continue
        try:
            posted = json.loads(posted_path.read_text())
        except json.JSONDecodeError:
            continue
        # _posted.json shape varies slightly per vertical; both common shapes:
        #   {"cases": {"SY_01": {...}}, ...}  OR  {"SY_01": {"video_id": ...}, ...}
        cases = posted.get("cases") if isinstance(posted, dict) and "cases" in posted else posted
        if not isinstance(cases, dict):
            continue
        for case_id, info in cases.items():
            if case_id in state:
                # Already tracked; keep IG/TT timestamps intact
                continue
            state[case_id] = {
                "videos_dir": rel,
                "youtube":    info.get("uploaded_at") or info.get("published_at") or info.get("posted_at") or _now_iso(),
                "instagram":  None,
                "tiktok":     None,
            }
            added += 1
    return added


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_list(state: dict[str, dict]) -> None:
    if not state:
        print("(no videos tracked yet — run --refresh)")
        return
    # Sort by youtube timestamp descending (most recent first)
    items = sorted(state.items(),
                   key=lambda kv: kv[1].get("youtube") or "",
                   reverse=True)
    print(f"  {'case_id':<40}  {'YT':<5}  {'IG':<5}  {'TT':<5}")
    print(f"  {'-'*40}  {'-'*5}  {'-'*5}  {'-'*5}")
    for case_id, info in items:
        yt = "✓" if info.get("youtube") else "✗"
        ig = "✓" if info.get("instagram") else "✗"
        tt = "✓" if info.get("tiktok") else "✗"
        print(f"  {case_id:<40}  {yt:<5}  {ig:<5}  {tt:<5}")


def cmd_pending(state: dict[str, dict], platform_filter: str | None = None) -> None:
    """Show all cases pending on IG or TT (or both)."""
    targets = ["instagram", "tiktok"] if not platform_filter else [PLATFORM_NAMES[platform_filter]]
    pending: list[tuple[str, list[str]]] = []
    for case_id, info in sorted(state.items()):
        missing = [p for p in targets if not info.get(p)]
        if missing and info.get("youtube"):  # only show YT-posted cases pending elsewhere
            pending.append((case_id, missing))
    if not pending:
        target_str = " + ".join(targets)
        print(f"  ✓ No cases pending on {target_str}.")
        return
    print(f"  {'case_id':<40}  pending on")
    print(f"  {'-'*40}  -----------")
    for case_id, missing in pending:
        print(f"  {case_id:<40}  {', '.join(missing)}")


def cmd_mark(state: dict[str, dict], case_id: str, platform: str) -> None:
    if case_id not in state:
        sys.exit(f"ERROR: case '{case_id}' not in tracker. Run --refresh.")
    plat_key = PLATFORM_NAMES.get(platform)
    if not plat_key:
        sys.exit(f"ERROR: unknown platform '{platform}'. Use: yt | ig | tt")
    state[case_id][plat_key] = _now_iso()
    save_status(state)
    print(f"  ✓ Marked {case_id} → {plat_key} ({state[case_id][plat_key]})")


def cmd_airdrop(state: dict[str, dict], case_id: str) -> None:
    """Print the file paths a human needs to AirDrop / open from their Mac."""
    if case_id not in state:
        sys.exit(f"ERROR: case '{case_id}' not in tracker. Run --refresh.")
    info = state[case_id]
    videos_dir = PROJECT_ROOT / info["videos_dir"]
    mp4 = videos_dir / f"{case_id}.mp4"
    ig_cap = videos_dir / f"{case_id}.ig_caption.txt"
    tt_cap = videos_dir / f"{case_id}.tt_caption.txt"

    print(f"\n── Cross-post bundle for {case_id} ──")
    print(f"\n  📹 MP4 to AirDrop:")
    print(f"     {mp4}")
    if not mp4.exists():
        print(f"     ⚠  Not found! Was the YouTube upload successful?")

    print(f"\n  📝 Instagram caption (copy/paste):")
    if ig_cap.exists():
        print(f"     {ig_cap}")
        print()
        for line in ig_cap.read_text().splitlines():
            print(f"        {line}")
    else:
        print(f"     ✗ Not generated. Run: python scripts/build_captions.py --case {case_id}")

    print(f"\n  📝 TikTok caption (copy/paste):")
    if tt_cap.exists():
        print(f"     {tt_cap}")
        print()
        for line in tt_cap.read_text().splitlines():
            print(f"        {line}")
    else:
        print(f"     ✗ Not generated.")

    print()
    print(f"  After posting, mark done:")
    print(f"     python scripts/cross_post_status.py --mark {case_id} ig")
    print(f"     python scripts/cross_post_status.py --mark {case_id} tt")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true", help="Show all tracked videos + per-platform status")
    g.add_argument("--pending", nargs="?", const="all", default=None,
                   help="Show videos pending on ig, tt, or both (default: both)")
    g.add_argument("--mark", nargs=2, metavar=("CASE_ID", "PLATFORM"),
                   help="Mark a video as posted on a platform (yt|ig|tt)")
    g.add_argument("--airdrop", metavar="CASE_ID",
                   help="Print bundle paths (MP4 + captions) for quick AirDrop")
    g.add_argument("--refresh", action="store_true",
                   help="Scan _posted.json files and import any new YouTube uploads")
    args = parser.parse_args()

    state = load_status()
    n_added = refresh_from_posted_ledgers(state)
    if n_added > 0:
        save_status(state)

    if args.list:
        cmd_list(state)
    elif args.pending is not None:
        platform = None if args.pending == "all" else args.pending
        cmd_pending(state, platform)
    elif args.mark:
        cmd_mark(state, args.mark[0], args.mark[1])
    elif args.airdrop:
        cmd_airdrop(state, args.airdrop)
    elif args.refresh:
        print(f"  Refreshed tracker from {len(VIDEOS_DIRS)} videos_dir locations.")
        print(f"  +{n_added} new cases imported from _posted.json ledgers.")
        cmd_list(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
