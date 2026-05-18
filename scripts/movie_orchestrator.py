#!/usr/bin/env python3
"""Movie short pipeline orchestrator — manages the MV_NN_<slug> queue.

Mirrors game_orchestrator.py for the movies vertical. Production steps
(fetch_trailer, select_clips, make_audio_elevenlabs, render_game_video,
upload_to_youtube) are shared with games — this script just owns the
queue state machine and per-movie CLI surface.

State machine:
    QUEUED → (production) → RENDERED → (upload) → DELIVERED
                                                 ↘ BLOCKED

Usage:
    python scripts/movie_orchestrator.py --list
    python scripts/movie_orchestrator.py --next-queued      # print next QUEUED slug
    python scripts/movie_orchestrator.py --next-rendered    # print next RENDERED slug
    python scripts/movie_orchestrator.py --mark-status MV_01_xxx RENDERED
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import load_dotenv  # noqa: E402
from _atomic import atomic_write_text  # noqa: E402

# Movie IDs must be safe for FFmpeg filtergraph syntax
MOVIE_ID_RE = re.compile(r"^MV_[A-Za-z0-9_]+$")

MOVIE_QUEUE_DIR = PROJECT_ROOT / "movie_queue"
SCRIPTS_DIR = PROJECT_ROOT / "output" / "scripts"
MOVIE_VIDEOS_DIR = PROJECT_ROOT / "output" / "movie_videos"

VALID_STATUSES = {"QUEUED", "RENDERED", "DELIVERED", "BLOCKED", "ACTIVE"}

load_dotenv(PROJECT_ROOT / ".env")


# ---------------------------------------------------------------------------
# Queue helpers
# ---------------------------------------------------------------------------

def load_queue_status() -> dict[str, str]:
    """Return {movie_id: status} from all queue files (only safe MV_ ids)."""
    statuses = {}
    if not MOVIE_QUEUE_DIR.exists():
        return statuses
    for p in sorted(MOVIE_QUEUE_DIR.glob("MV_*.md")):
        if p.name.startswith("MV_TEMPLATE"):
            continue
        if not MOVIE_ID_RE.match(p.stem):
            print(f"  [queue] skipping {p.name}: unsafe movie_id for FFmpeg paths",
                  file=sys.stderr)
            continue
        content = p.read_text()
        m = re.search(r"\*\*Status:\*\*\s*([A-Z_]+)", content)
        statuses[p.stem] = m.group(1) if m else "UNKNOWN"
    return statuses


def next_movie_by_status(status: str) -> str | None:
    for movie_id, s in load_queue_status().items():
        if s == status:
            return movie_id
    return None


def queue_file(movie_id: str) -> Path:
    if not MOVIE_ID_RE.match(movie_id):
        sys.exit(f"ERROR: Unsafe movie_id '{movie_id}' (must match {MOVIE_ID_RE.pattern})")
    return MOVIE_QUEUE_DIR / f"{movie_id}.md"


def mark_queue_status(movie_id: str, new_status: str) -> None:
    if new_status not in VALID_STATUSES:
        sys.exit(f"ERROR: Invalid status '{new_status}'. Valid: {sorted(VALID_STATUSES)}")

    p = queue_file(movie_id)
    if not p.exists():
        sys.exit(f"ERROR: Queue file not found: {p}")

    content = p.read_text()
    new_content, n = re.subn(
        r"(\*\*Status:\*\*\s*)[A-Z_]+",
        rf"\g<1>{new_status}",
        content,
        count=1,
    )
    if n == 0:
        sys.exit(f"ERROR: Could not find Status line in {p}")
    atomic_write_text(p, new_content)
    print(f"Marked {movie_id} → {new_status}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true", help="Show all movies + statuses")
    g.add_argument("--next-queued", action="store_true",
                   help="Print the slug of the next QUEUED movie (empty if none)")
    g.add_argument("--next-rendered", action="store_true",
                   help="Print the slug of the next RENDERED movie (ready to upload)")
    g.add_argument("--mark-status", nargs=2, metavar=("MOVIE_ID", "STATUS"),
                   help="Set queue file status (QUEUED|RENDERED|DELIVERED|BLOCKED|ACTIVE)")
    args = parser.parse_args()

    if args.list:
        statuses = load_queue_status()
        if not statuses:
            print("(movie_queue/ is empty — add MV_NN_<slug>.md files)")
            return
        for movie_id, status in statuses.items():
            print(f"  {status:<10} {movie_id}")
        return

    if args.next_queued:
        result = next_movie_by_status("QUEUED")
        if result:
            print(result)
        return

    if args.next_rendered:
        result = next_movie_by_status("RENDERED")
        if result:
            print(result)
        return

    if args.mark_status:
        movie_id, status = args.mark_status
        mark_queue_status(movie_id, status)
        return


if __name__ == "__main__":
    main()
