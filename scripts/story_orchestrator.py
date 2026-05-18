#!/usr/bin/env python3
"""AI Stories short pipeline orchestrator — SY_NN_<subtype>_<slug> queue.

Non-trailer vertical that uses build_visuals_track.py with Flux (still) +
Pika (hero shots) for narrative AI-generated content. Rotates through
three sub-genres:

  - SY_NN_S_*  numbered survival/POV  → Charlie voice, action visuals
  - SY_NN_R_*  Reddit dramatization   → Brian voice, naturalistic visuals
  - SY_NN_H_*  horror micro-fiction   → Daniel voice, atmospheric visuals

State machine:
    QUEUED → (production) → RENDERED → (upload) → DELIVERED
                                                 ↘ BLOCKED

Usage:
    python scripts/story_orchestrator.py --list
    python scripts/story_orchestrator.py --next-queued [--subgenre S|R|H]
    python scripts/story_orchestrator.py --next-rendered
    python scripts/story_orchestrator.py --mark-status SY_01_S_x RENDERED
    python scripts/story_orchestrator.py --subgenre-counts   # show per-sub-genre counts
    python scripts/story_orchestrator.py --total-count       # for priority_until_count check
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import load_dotenv  # noqa: E402
from _atomic import atomic_write_text  # noqa: E402

# SY_NN_<sub>_<slug> where <sub> is S/R/H
SY_ID_RE = re.compile(r"^SY_\d{2,3}_[SRH]_[A-Za-z0-9_]+$")
SUBGENRE_LETTERS = {"S": "survival", "R": "reddit", "H": "horror"}
QUEUE_DIR = PROJECT_ROOT / "story_queue"
VALID_STATUSES = {"QUEUED", "RENDERED", "DELIVERED", "BLOCKED", "ACTIVE"}

load_dotenv(PROJECT_ROOT / ".env")


def extract_subgenre(story_id: str) -> str:
    """SY_01_S_foo → 'survival'. SY_03_H_bar → 'horror'. SY_05_R_baz → 'reddit'."""
    m = re.match(r"^SY_\d{2,3}_([SRH])_", story_id)
    if not m:
        return "unknown"
    return SUBGENRE_LETTERS.get(m.group(1), "unknown")


def load_queue_status() -> dict[str, str]:
    statuses = {}
    if not QUEUE_DIR.exists():
        return statuses
    for p in sorted(QUEUE_DIR.glob("SY_*.md")):
        if p.name.startswith("SY_TEMPLATE"):
            continue
        if not SY_ID_RE.match(p.stem):
            print(f"  [queue] skipping {p.name}: unsafe id", file=sys.stderr)
            continue
        m = re.search(r"\*\*Status:\*\*\s*([A-Z_]+)", p.read_text())
        statuses[p.stem] = m.group(1) if m else "UNKNOWN"
    return statuses


def next_by_status(status: str, subgenre_filter: str | None = None) -> str | None:
    """Return the next ID with the given status, optionally filtered by sub-genre letter (S/R/H).

    When subgenre_filter is None, rotates through sub-genres in order S → R → H so we
    don't bias production toward whichever entered the queue first.
    """
    candidates = [(sid, s) for sid, s in load_queue_status().items() if s == status]
    if not candidates:
        return None
    if subgenre_filter:
        for sid, _ in candidates:
            if f"_{subgenre_filter.upper()}_" in sid:
                return sid
        return None
    # Round-robin: pick whichever sub-genre has the fewest videos already past QUEUED
    # (i.e., starve-the-overshoots so production stays balanced across S/R/H)
    all_status = load_queue_status()
    produced_by_sub = Counter()
    for sid, st in all_status.items():
        if st in ("RENDERED", "DELIVERED"):
            produced_by_sub[extract_subgenre(sid)] += 1
    candidates.sort(key=lambda x: produced_by_sub[extract_subgenre(x[0])])
    return candidates[0][0]


def mark_queue_status(story_id: str, new_status: str) -> None:
    if not SY_ID_RE.match(story_id):
        sys.exit(f"ERROR: Unsafe id '{story_id}' — must match SY_NN_<S|R|H>_<slug>")
    if new_status not in VALID_STATUSES:
        sys.exit(f"ERROR: Invalid status '{new_status}'. Valid: {sorted(VALID_STATUSES)}")
    p = QUEUE_DIR / f"{story_id}.md"
    if not p.exists():
        sys.exit(f"ERROR: {p} not found")
    new_content, n = re.subn(r"(\*\*Status:\*\*\s*)[A-Z_]+", rf"\g<1>{new_status}", p.read_text(), count=1)
    if n == 0:
        sys.exit(f"ERROR: No Status line in {p}")
    atomic_write_text(p, new_content)
    print(f"Marked {story_id} → {new_status}")


def subgenre_counts() -> dict[str, dict[str, int]]:
    """Return {sub: {status: count}} for analytics."""
    result: dict[str, dict[str, int]] = {sub: {} for sub in SUBGENRE_LETTERS.values()}
    for sid, status in load_queue_status().items():
        sub = extract_subgenre(sid)
        if sub == "unknown":
            continue
        result[sub][status] = result[sub].get(status, 0) + 1
    return result


def total_count() -> int:
    """Sum of all SY_ entries in any status — used by priority_until_count check."""
    return len(load_queue_status())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--next-queued", action="store_true")
    g.add_argument("--next-rendered", action="store_true")
    g.add_argument("--mark-status", nargs=2, metavar=("SY_ID", "STATUS"))
    g.add_argument("--subgenre-counts", action="store_true")
    g.add_argument("--total-count", action="store_true")

    parser.add_argument("--subgenre", choices=["S", "R", "H"], default=None,
                        help="Filter --next-queued / --next-rendered by sub-genre letter")
    args = parser.parse_args()

    if args.list:
        s = load_queue_status()
        if not s:
            print("(story_queue/ is empty)")
            return
        for k, v in s.items():
            sub = extract_subgenre(k)
            print(f"  {v:<10} {sub:<9} {k}")
        return

    if args.next_queued:
        r = next_by_status("QUEUED", args.subgenre)
        if r: print(r)
        return

    if args.next_rendered:
        r = next_by_status("RENDERED", args.subgenre)
        if r: print(r)
        return

    if args.mark_status:
        mark_queue_status(args.mark_status[0], args.mark_status[1])
        return

    if args.subgenre_counts:
        counts = subgenre_counts()
        for sub, statuses in counts.items():
            total = sum(statuses.values())
            detail = ", ".join(f"{s}={n}" for s, n in sorted(statuses.items()))
            print(f"  {sub:<9} total={total}  ({detail})")
        return

    if args.total_count:
        print(total_count())
        return


if __name__ == "__main__":
    main()
