#!/usr/bin/env python3
"""Mythology / History short pipeline orchestrator — MY_NN_<slug> queue.

Non-trailer vertical: uses build_visuals_track.py for AI/stock images +
Ken Burns motion. Brian voice + eleven_multilingual_v2 model (slower
documentary tone).

State machine:
    QUEUED → (production) → RENDERED → (upload) → DELIVERED
                                                 ↘ BLOCKED

Usage:
    python scripts/mythology_orchestrator.py --list
    python scripts/mythology_orchestrator.py --next-queued
    python scripts/mythology_orchestrator.py --next-rendered
    python scripts/mythology_orchestrator.py --mark-status MY_01_x RENDERED
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import load_dotenv  # noqa: E402
from _atomic import atomic_write_text  # noqa: E402

MY_ID_RE = re.compile(r"^MY_[A-Za-z0-9_]+$")
QUEUE_DIR = PROJECT_ROOT / "mythology_queue"
VALID_STATUSES = {"QUEUED", "RENDERED", "DELIVERED", "BLOCKED", "ACTIVE"}

load_dotenv(PROJECT_ROOT / ".env")


def load_queue_status() -> dict[str, str]:
    statuses = {}
    if not QUEUE_DIR.exists():
        return statuses
    for p in sorted(QUEUE_DIR.glob("MY_*.md")):
        if p.name.startswith("MY_TEMPLATE"):
            continue
        if not MY_ID_RE.match(p.stem):
            print(f"  [queue] skipping {p.name}: unsafe id", file=sys.stderr)
            continue
        m = re.search(r"\*\*Status:\*\*\s*([A-Z_]+)", p.read_text())
        statuses[p.stem] = m.group(1) if m else "UNKNOWN"
    return statuses


def next_by_status(status: str) -> str | None:
    for myth_id, s in load_queue_status().items():
        if s == status:
            return myth_id
    return None


def mark_queue_status(myth_id: str, new_status: str) -> None:
    if not MY_ID_RE.match(myth_id):
        sys.exit(f"ERROR: Unsafe id '{myth_id}'")
    if new_status not in VALID_STATUSES:
        sys.exit(f"ERROR: Invalid status '{new_status}'. Valid: {sorted(VALID_STATUSES)}")
    p = QUEUE_DIR / f"{myth_id}.md"
    if not p.exists():
        sys.exit(f"ERROR: {p} not found")
    new_content, n = re.subn(r"(\*\*Status:\*\*\s*)[A-Z_]+", rf"\g<1>{new_status}", p.read_text(), count=1)
    if n == 0:
        sys.exit(f"ERROR: No Status line in {p}")
    atomic_write_text(p, new_content)
    print(f"Marked {myth_id} → {new_status}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--next-queued", action="store_true")
    g.add_argument("--next-rendered", action="store_true")
    g.add_argument("--mark-status", nargs=2, metavar=("MY_ID", "STATUS"))
    args = parser.parse_args()
    if args.list:
        s = load_queue_status()
        if not s:
            print("(mythology_queue/ is empty)")
            return
        for k, v in s.items():
            print(f"  {v:<10} {k}")
        return
    if args.next_queued:
        r = next_by_status("QUEUED")
        if r: print(r)
        return
    if args.next_rendered:
        r = next_by_status("RENDERED")
        if r: print(r)
        return
    if args.mark_status:
        mark_queue_status(args.mark_status[0], args.mark_status[1])


if __name__ == "__main__":
    main()
