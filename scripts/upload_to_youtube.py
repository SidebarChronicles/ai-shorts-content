#!/usr/bin/env python3
"""Upload a TrueCrime or Game Short to YouTube via the YouTube Data API v3.

Designed for Claude Code on a Mac (Path C in the build plan). Reads the
description.md sidecar to populate title + description + tags, sets the
AI synthetic content disclosure flag, schedules the video as private →
public-at-timestamp, and tracks posted state in _posted.json.

Usage (from the project root):

    # Upload the next case that hasn't been posted yet
    python scripts/upload_to_youtube.py --next

    # Upload a specific case
    python scripts/upload_to_youtube.py --case 02

    # Upload a game short (different videos dir + Gaming category)
    python scripts/upload_to_youtube.py --case GG_01_elden_ring --videos-dir output/game_videos --category 20

    # Preview without uploading (no network calls beyond auth refresh)
    python scripts/upload_to_youtube.py --case 02 --dry-run

    # Pick a custom publish time (default: next 6 PM local at least 24h out)
    python scripts/upload_to_youtube.py --next --publish-at "2026-05-20T18:00:00"

Requires (one-time):
  1. Google Cloud project with YouTube Data API v3 enabled
  2. OAuth 2.0 Client ID of type "Desktop application"
  3. client_secret.json downloaded to project root
  4. `python scripts/youtube_oauth_setup.py` run once to generate token.json

See README_UPLOAD_SETUP.md for the full one-time setup walkthrough.
"""

from __future__ import annotations
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# ---------------------------------------------------------------------------
# Paths / constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOKEN_PATH = PROJECT_ROOT / "token.json"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]

DEFAULT_CATEGORY_ID = "24"   # Entertainment (truecrime)
GAMING_CATEGORY_ID = "20"    # Gaming


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def load_credentials() -> Credentials:
    if not TOKEN_PATH.exists():
        sys.exit(
            f"[FATAL] No token.json at {TOKEN_PATH}.\n"
            f"        Run: python scripts/youtube_oauth_setup.py"
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
        print("  (refreshed access token)")
    return creds


# ---------------------------------------------------------------------------
# Description parsing
# ---------------------------------------------------------------------------

_BLOCK_PATTERN_TPL = r"##\s*{section}[^\n]*\n+```[^\n]*\n(.*?)\n```"


def _extract_block(text: str, section: str) -> str:
    pattern = _BLOCK_PATTERN_TPL.format(section=re.escape(section))
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if not m:
        raise ValueError(f"Could not find '## {section}' code block in description.md")
    return m.group(1).strip()


def parse_description(md_path: Path) -> dict:
    text = md_path.read_text()
    title = _extract_block(text, "Title").strip()
    description = _extract_block(text, "DESCRIPTION")
    tags_raw = _extract_block(text, "Tags")
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    if len(title) > 100:
        raise ValueError(f"Title too long ({len(title)} > 100): {title!r}")
    return {"title": title, "description": description, "tags": tags}


# ---------------------------------------------------------------------------
# Posted-state tracking
# ---------------------------------------------------------------------------

def load_posted(posted_path: Path) -> dict:
    if not posted_path.exists():
        return {}
    return json.loads(posted_path.read_text())


def save_posted(state: dict, posted_path: Path) -> None:
    posted_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def mark_posted(case_id: str, video_id: str, scheduled_for: str, posted_path: Path) -> None:
    state = load_posted(posted_path)
    state[case_id] = {
        "video_id": video_id,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "scheduled_publish": scheduled_for,
        "watch_url": f"https://www.youtube.com/watch?v={video_id}",
    }
    save_posted(state, posted_path)


# ---------------------------------------------------------------------------
# Case discovery
# ---------------------------------------------------------------------------

def discover_cases(videos_dir: Path) -> list[str]:
    """Return sorted list of case_id strings that have an mp4 + description."""
    cases = []
    for mp4 in sorted(videos_dir.glob("*.mp4")):
        case_id = mp4.stem
        desc = videos_dir / f"{case_id}.description.md"
        if desc.exists():
            cases.append(case_id)
    return cases


def next_unposted(videos_dir: Path, posted_path: Path) -> str | None:
    posted = load_posted(posted_path)
    for case_id in discover_cases(videos_dir):
        if case_id not in posted:
            return case_id
    return None


def resolve_case(arg: str, videos_dir: Path) -> str:
    """Accept '02' or '02_ransomware_negotiator' — return full case_id."""
    cases = discover_cases(videos_dir)
    for c in cases:
        if c == arg or c.startswith(arg + "_") or c.startswith(arg):
            return c
    sys.exit(f"[FATAL] No case matches {arg!r}. Available: {cases}")


# ---------------------------------------------------------------------------
# Publish slot calculation
# ---------------------------------------------------------------------------

def compute_next_slot(hour_local: int = 18, min_offset_hours: int = 24) -> datetime:
    """Next H:00 local time that's at least `min_offset_hours` from now."""
    now = datetime.now().astimezone()
    target = now.replace(hour=hour_local, minute=0, second=0, microsecond=0)
    earliest = now + timedelta(hours=min_offset_hours)
    while target < earliest:
        target += timedelta(days=1)
    return target.astimezone(timezone.utc)


def parse_publish_at(s: str) -> datetime:
    """Parse user-supplied --publish-at into a UTC datetime."""
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def build_body(meta: dict, publish_at: datetime, category_id: str) -> dict:
    return {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": publish_at.isoformat().replace("+00:00", "Z"),
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,  # ⚠ REQUIRED for AI narration
        },
    }


def upload_one(case_id: str, publish_at: datetime, dry_run: bool,
               videos_dir: Path, posted_path: Path, category_id: str) -> None:
    mp4 = videos_dir / f"{case_id}.mp4"
    desc_md = videos_dir / f"{case_id}.description.md"
    if not mp4.exists():
        sys.exit(f"[FATAL] Missing mp4: {mp4}")
    if not desc_md.exists():
        sys.exit(f"[FATAL] Missing description sidecar: {desc_md}")

    meta = parse_description(desc_md)
    body = build_body(meta, publish_at, category_id)

    print(f"\n── Upload plan: {case_id} ──")
    print(f"  Title:       {meta['title']}")
    print(f"  Tags:        {', '.join(meta['tags'])}")
    print(f"  File:        {mp4.relative_to(PROJECT_ROOT)}  ({mp4.stat().st_size // 1024} KB)")
    print(f"  Scheduled:   {publish_at.isoformat()}")
    print(f"  Category ID: {category_id}")
    print(f"  Made for kids:           False")
    print(f"  Contains synthetic:      True  ⚠")

    if dry_run:
        print("\n  DRY RUN — no upload performed.")
        return

    print("\n  Authenticating…")
    creds = load_credentials()
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    media = MediaFileUpload(str(mp4), chunksize=1024 * 1024 * 4,
                            resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
        notifySubscribers=False,
    )

    print("  Uploading…")
    response = None
    last_pct = -1
    while response is None:
        try:
            status, response = request.next_chunk()
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504):
                print(f"  Transient {e.resp.status}, retrying…")
                continue
            raise
        if status:
            pct = int(status.progress() * 100)
            if pct != last_pct:
                print(f"    {pct}%")
                last_pct = pct

    video_id = response["id"]
    print(f"\n  ✓ Uploaded as video_id={video_id}")
    print(f"  ✓ Will publish at {publish_at.isoformat()}")
    print(f"  ✓ Watch URL: https://www.youtube.com/watch?v={video_id}")

    mark_posted(case_id, video_id, publish_at.isoformat(), posted_path)
    print(f"  ✓ Marked posted in {posted_path.relative_to(PROJECT_ROOT)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a TrueCrime or Game Short to YouTube.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--next", action="store_true",
                       help="Upload the next case that hasn't been posted yet.")
    group.add_argument("--case", metavar="ID", type=str,
                       help="Upload a specific case (e.g. '02', 'GG_01_elden_ring').")
    group.add_argument("--list", action="store_true",
                       help="List discovered cases + their posted status.")
    parser.add_argument("--videos-dir", metavar="PATH", default=None,
                        help="Directory containing mp4s + description.md sidecars "
                             "(default: output/videos/; use output/game_videos/ for game shorts).")
    parser.add_argument("--category", metavar="ID", default=None,
                        help=f"YouTube category ID (default: {DEFAULT_CATEGORY_ID} Entertainment; "
                             f"use {GAMING_CATEGORY_ID} for gaming).")
    parser.add_argument("--publish-at", type=str, default=None,
                        help="ISO datetime override (default: next 6 PM local, ≥24h out).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show the upload plan without contacting YouTube.")
    args = parser.parse_args()

    # Resolve videos directory and posted tracking file
    if args.videos_dir:
        videos_dir = PROJECT_ROOT / args.videos_dir if not Path(args.videos_dir).is_absolute() else Path(args.videos_dir)
    else:
        videos_dir = PROJECT_ROOT / "output" / "videos"

    posted_path = videos_dir / "_posted.json"

    # Resolve category ID
    category_id = args.category if args.category else DEFAULT_CATEGORY_ID

    if args.list:
        posted = load_posted(posted_path)
        cases = discover_cases(videos_dir)
        if not cases:
            print(f"No mp4s + description sidecars found in {videos_dir.relative_to(PROJECT_ROOT)}")
            return
        for c in cases:
            mark = "POSTED" if c in posted else "READY"
            extra = f"  watch={posted[c]['watch_url']}" if c in posted else ""
            print(f"  [{mark:6s}] {c}{extra}")
        return

    if args.next:
        case_id = next_unposted(videos_dir, posted_path)
        if case_id is None:
            print("All cases have been posted. Add a new one, or use --case to repost.")
            return
    else:
        case_id = resolve_case(args.case, videos_dir)

    publish_at = parse_publish_at(args.publish_at) if args.publish_at else compute_next_slot()
    upload_one(case_id, publish_at, args.dry_run, videos_dir, posted_path, category_id)


if __name__ == "__main__":
    main()
