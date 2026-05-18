#!/usr/bin/env python3
"""Schedule uploads for today's batch: TikTok now + YouTube prime slots.

For each picked case in output/daily/picks_YYYY-MM-DD.json:
  - TikTok: post_via_scheduler.py --case <id> --platforms tt
            PostFast posts immediately (~30s after invoke) — there's no
            scheduled-publish API, so "prime time for TikTok" = when /morning
            runs (typically 8 AM ET).
  - YouTube: upload_to_youtube.py --case <id> --publish-at <slot>
             Scheduled to publish at the next available prime slot in
             PRIME_SLOTS_ET (8:00 / 12:30 / 18:30 / 21:30 local).

Idempotent (PostFast tracks state in cross_post_status.json; upload_to_youtube
tracks in _posted.json — re-runs skip already-posted cases).

Usage:
    python scripts/schedule_uploads.py --batch output/daily/picks_2026-05-19.json
    python scripts/schedule_uploads.py --batch ... --dry-run
    python scripts/schedule_uploads.py --batch ... --platforms tt  # TT only
    python scripts/schedule_uploads.py --batch ... --platforms yt  # YT only
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

VENV_PY = PROJECT_ROOT / ".venv-upload" / "bin" / "python3"
PYTHON = str(VENV_PY) if VENV_PY.exists() else sys.executable

# Prime-time slots for YouTube --publish-at (local ET).
# Spread the day so the channel keeps fresh content visible.
PRIME_SLOTS_ET = [
    (8, 0),    # morning commute scroll
    (12, 30),  # lunch
    (18, 30),  # evening dinner
    (21, 30),  # pre-bed
]

ET = ZoneInfo("America/New_York")
STORY_VIDEOS_DIR = PROJECT_ROOT / "output" / "story_videos"


def next_prime_slots(num_needed: int) -> list[datetime]:
    """Return the next N prime slots starting from the next available one.

    Walks forward from now: today's remaining slots first, then tomorrow's,
    etc. Ensures each slot is ≥24h ahead of `now` (YouTube requires that
    for scheduled publishing).
    """
    now = datetime.now(ET)
    min_publish = now + timedelta(hours=24)
    slots: list[datetime] = []
    day_offset = 0
    while len(slots) < num_needed:
        candidate_date = (now + timedelta(days=day_offset)).date()
        for hh, mm in PRIME_SLOTS_ET:
            slot = datetime.combine(candidate_date, time(hh, mm), tzinfo=ET)
            if slot >= min_publish:
                slots.append(slot)
                if len(slots) >= num_needed:
                    break
        day_offset += 1
    return slots


def run_step(label: str, cmd: list[str], dry_run: bool) -> bool:
    """Run a subprocess. Returns True on success, False on failure. Doesn't raise."""
    print(f"    → {label}")
    if dry_run:
        print(f"        [dry-run] {' '.join(str(c) for c in cmd)}")
        return True
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"        ✗ FAIL (exit {result.returncode})", file=sys.stderr)
        if result.stderr:
            print(f"        stderr: {result.stderr.strip()[-300:]}", file=sys.stderr)
        return False
    if result.stdout:
        # Surface the most informative tail line (typically a URL or status)
        last = result.stdout.strip().splitlines()
        if last:
            print(f"        {last[-1][:120]}")
    return True


def schedule_tiktok(case_id: str, dry_run: bool) -> bool:
    return run_step(
        f"TikTok via PostFast (immediate)",
        [PYTHON, str(PROJECT_ROOT / "scripts" / "post_via_scheduler.py"),
         "--case", case_id, "--platforms", "tt"],
        dry_run,
    )


def schedule_youtube(case_id: str, publish_at: datetime, dry_run: bool) -> bool:
    # Confirm the mp4 exists before invoking the upload script
    mp4 = STORY_VIDEOS_DIR / f"{case_id}.mp4"
    if not mp4.exists():
        print(f"        ⚠  {mp4.relative_to(PROJECT_ROOT)} missing — skipping YouTube upload")
        return False
    # Format publish_at for the script: ISO 8601 local-naive (script appends TZ).
    publish_iso = publish_at.strftime("%Y-%m-%dT%H:%M:%S")
    return run_step(
        f"YouTube --publish-at {publish_at.strftime('%a %H:%M ET')}",
        [PYTHON, str(PROJECT_ROOT / "scripts" / "upload_to_youtube.py"),
         "--case", case_id,
         "--videos-dir", "output/story_videos",
         "--category", "24",
         "--publish-at", publish_iso],
        dry_run,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch", type=Path, required=True,
                    help="picks_YYYY-MM-DD.json from /pick-today")
    ap.add_argument("--platforms", default="both", choices=["tt", "yt", "both"],
                    help="Which platform(s) to schedule (default: both)")
    ap.add_argument("--dry-run", action="store_true", help="Print plan, don't invoke uploaders")
    args = ap.parse_args()

    if not args.batch.exists():
        print(f"ERROR: {args.batch} not found", file=sys.stderr)
        return 2
    try:
        payload = json.loads(args.batch.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"ERROR: {args.batch}: {e}", file=sys.stderr)
        return 2
    picks = payload.get("picks") or []
    if not picks:
        print("ERROR: batch file has no picks[]", file=sys.stderr)
        return 2

    print(f"── schedule_uploads: {len(picks)} case(s), platforms={args.platforms}")

    slots = next_prime_slots(len(picks)) if args.platforms in ("yt", "both") else []
    if slots:
        print("   YouTube prime slots assigned:")
        for pk, slot in zip(picks, slots):
            print(f"     {pk['case_id']:<40} → {slot.strftime('%a %Y-%m-%d %H:%M %Z')}")

    tt_results: list[tuple[str, bool]] = []
    yt_results: list[tuple[str, bool]] = []

    for i, pick in enumerate(picks):
        case_id = pick["case_id"]
        print(f"\n  [{i+1}/{len(picks)}] {case_id}")
        if args.platforms in ("tt", "both"):
            ok = schedule_tiktok(case_id, args.dry_run)
            tt_results.append((case_id, ok))
        if args.platforms in ("yt", "both"):
            ok = schedule_youtube(case_id, slots[i], args.dry_run)
            yt_results.append((case_id, ok))

    print(f"\n── schedule_uploads summary")
    if tt_results:
        ok_n = sum(1 for _, ok in tt_results if ok)
        print(f"  TikTok: {ok_n}/{len(tt_results)} posted")
    if yt_results:
        ok_n = sum(1 for _, ok in yt_results if ok)
        print(f"  YouTube: {ok_n}/{len(yt_results)} scheduled")

    fail_n = sum(1 for _, ok in tt_results if not ok) + sum(1 for _, ok in yt_results if not ok)
    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
