#!/usr/bin/env python3
"""Daily hygiene — archive stale outputs, prune leaked temp files.

Runs at the start of every /morning invocation (Step 0). Safe by default:
NEVER deletes — only moves to <dir>/archive/. The user can delete archives
manually when comfortable.

Rules (v1):
  - output/daily/picks_*.json          keep latest 7; older → archive/
  - output/research/candidates_*.{md,json}  keep latest date only; older → archive/
  - output/analytics/report_*.{md,json}     keep latest 14; older → archive/
  - output/scripts/<case>/              if DELIVERED > 30d ago → archive/
  - .part files anywhere in output/ + assets/audio/  → rm (these are leaked
    half-written atomic-rename files)
  - /var/folders/.../el_perbeat_*       → rm (leaked EL temp dirs)
  - empty output/audio/<case>/sound_assets/ → prune

Usage:
    python scripts/morning_cleanup.py             # dry-run, prints plan
    python scripts/morning_cleanup.py --apply     # actually move/delete
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DAILY_DIR = PROJECT_ROOT / "output" / "daily"
RESEARCH_DIR = PROJECT_ROOT / "output" / "research"
ANALYTICS_DIR = PROJECT_ROOT / "output" / "analytics"
SCRIPTS_OUT_DIR = PROJECT_ROOT / "output" / "scripts"
AUDIO_DIR = PROJECT_ROOT / "assets" / "audio"
SOUND_DESIGN_DIR = PROJECT_ROOT / "output" / "audio"

DAILY_KEEP = 7
ANALYTICS_KEEP = 14
SCRIPTS_DELIVERED_AGE_DAYS = 30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_date_from_filename(name: str) -> date | None:
    """Extract YYYY-MM-DD from a filename like 'picks_2026-05-19.json'."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def archive_path(orig: Path) -> Path:
    """Compute the archive destination for a file: <parent>/archive/<name>."""
    return orig.parent / "archive" / orig.name


def do_move(src: Path, dst: Path, apply: bool, log: list[tuple[str, Path, Path | None]]) -> int:
    """Move src → dst. Returns bytes freed (informational)."""
    size = src.stat().st_size if src.is_file() else sum(f.stat().st_size for f in src.rglob("*") if f.is_file())
    log.append(("archive", src, dst))
    if apply:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    return size


def do_remove(src: Path, apply: bool, log: list[tuple[str, Path, Path | None]]) -> int:
    """Remove src (file or dir). Returns bytes freed."""
    if src.is_file():
        size = src.stat().st_size
    else:
        size = sum(f.stat().st_size for f in src.rglob("*") if f.is_file())
    log.append(("remove", src, None))
    if apply:
        if src.is_dir():
            shutil.rmtree(src)
        else:
            src.unlink()
    return size


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def rule_archive_dated(dir_: Path, glob: str, keep_n: int | None, keep_latest: bool,
                       apply: bool, log: list) -> int:
    """Archive dated files under `dir_/glob`. Keep latest N (or just the latest date)."""
    if not dir_.exists():
        return 0
    files = sorted(
        (p for p in dir_.glob(glob) if p.is_file()),
        key=lambda p: (parse_date_from_filename(p.name) or date.min, p.name),
        reverse=True,
    )
    if not files:
        return 0

    if keep_latest:
        latest_date = parse_date_from_filename(files[0].name)
        to_archive = [f for f in files if parse_date_from_filename(f.name) != latest_date]
    elif keep_n is not None:
        to_archive = files[keep_n:]
    else:
        to_archive = []

    total = 0
    for f in to_archive:
        total += do_move(f, archive_path(f), apply, log)
    return total


def rule_archive_old_delivered_cases(apply: bool, log: list) -> int:
    """Move output/scripts/<case>/ to archive/ if the case has been DELIVERED >30d ago."""
    if not SCRIPTS_OUT_DIR.exists():
        return 0

    # Read each vertical's _posted.json if it exists
    posted_files = list((PROJECT_ROOT / "output").glob("*/_posted.json"))
    delivered_old: dict[str, datetime] = {}
    cutoff = datetime.now(timezone.utc).timestamp() - SCRIPTS_DELIVERED_AGE_DAYS * 86400

    for pf in posted_files:
        try:
            data = json.loads(pf.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        for case_id, info in data.items():
            uploaded = info.get("uploaded_at", "")
            try:
                t = datetime.fromisoformat(uploaded.replace("Z", "+00:00")).timestamp()
            except (ValueError, AttributeError):
                continue
            if t < cutoff:
                delivered_old[case_id] = t

    total = 0
    for case_id in delivered_old:
        case_dir = SCRIPTS_OUT_DIR / case_id
        if case_dir.exists() and case_dir.is_dir():
            dst = SCRIPTS_OUT_DIR / "archive" / case_id
            total += do_move(case_dir, dst, apply, log)
    return total


def rule_prune_part_files(apply: bool, log: list) -> int:
    """Remove leaked .part files (atomic-rename half-writes that didn't complete)."""
    total = 0
    for root in (PROJECT_ROOT / "output", AUDIO_DIR):
        if not root.exists():
            continue
        for f in root.rglob("*.part"):
            if f.is_file():
                total += do_remove(f, apply, log)
    return total


def rule_prune_temp_el_dirs(apply: bool, log: list) -> int:
    """Remove leaked /var/folders/.../el_perbeat_* temp dirs (macOS).

    De-duplicates via resolved path: $TMPDIR symlinks into /var/folders/...
    on macOS, so a naive scan double-counts.
    """
    total = 0
    seen: set[Path] = set()
    candidates = []
    tmp_root = os.environ.get("TMPDIR", "/tmp")
    if tmp_root:
        candidates.append(Path(tmp_root))
    var_folders = Path("/var/folders")
    if var_folders.exists():
        candidates.append(var_folders)

    for root in candidates:
        try:
            for d in list(root.glob("*/*/T/el_perbeat_*")) + list(root.glob("el_perbeat_*")):
                if not d.is_dir():
                    continue
                resolved = d.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                total += do_remove(d, apply, log)
        except (PermissionError, OSError):
            continue
    return total


def rule_prune_empty_sound_assets(apply: bool, log: list) -> int:
    """Remove empty output/audio/<case>/sound_assets/ dirs."""
    total = 0
    if not SOUND_DESIGN_DIR.exists():
        return 0
    for case_dir in SOUND_DESIGN_DIR.iterdir():
        if not case_dir.is_dir():
            continue
        assets = case_dir / "sound_assets"
        if assets.exists() and assets.is_dir() and not any(assets.iterdir()):
            total += do_remove(assets, apply, log)
    return total


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="Actually move/delete. Default is dry-run (prints plan only).")
    ap.add_argument("--quiet", action="store_true", help="Only print summary line.")
    args = ap.parse_args()

    apply = args.apply
    log: list[tuple[str, Path, Path | None]] = []

    bytes_freed = 0
    bytes_freed += rule_archive_dated(DAILY_DIR, "picks_*.json", keep_n=DAILY_KEEP,
                                       keep_latest=False, apply=apply, log=log)
    bytes_freed += rule_archive_dated(RESEARCH_DIR, "candidates_*.md", keep_n=None,
                                       keep_latest=True, apply=apply, log=log)
    bytes_freed += rule_archive_dated(RESEARCH_DIR, "candidates_*.json", keep_n=None,
                                       keep_latest=True, apply=apply, log=log)
    bytes_freed += rule_archive_dated(ANALYTICS_DIR, "report_*.md", keep_n=ANALYTICS_KEEP,
                                       keep_latest=False, apply=apply, log=log)
    bytes_freed += rule_archive_dated(ANALYTICS_DIR, "report_*.json", keep_n=ANALYTICS_KEEP,
                                       keep_latest=False, apply=apply, log=log)
    bytes_freed += rule_archive_old_delivered_cases(apply, log)
    bytes_freed += rule_prune_part_files(apply, log)
    bytes_freed += rule_prune_temp_el_dirs(apply, log)
    bytes_freed += rule_prune_empty_sound_assets(apply, log)

    if not args.quiet:
        if not log:
            print(f"cleanup: 0 items {'moved' if apply else 'to move'} — repo already tidy")
        else:
            n_archive = sum(1 for action, _, _ in log if action == "archive")
            n_remove = sum(1 for action, _, _ in log if action == "remove")
            if not apply:
                print(f"cleanup [DRY-RUN]: would archive {n_archive}, remove {n_remove}, free ~{bytes_freed/1024/1024:.1f}MB")
                for action, src, dst in log:
                    rel = src.relative_to(PROJECT_ROOT) if src.is_relative_to(PROJECT_ROOT) else src
                    if action == "archive":
                        print(f"  → archive: {rel}")
                    else:
                        print(f"  → remove:  {rel}")
                print("\n  Re-run with --apply to actually move/delete.")
            else:
                print(f"cleanup: archived {n_archive}, removed {n_remove}, freed ~{bytes_freed/1024/1024:.1f}MB")

    # Compact one-liner for the morning skill's summary aggregator
    if args.quiet:
        n_archive = sum(1 for action, _, _ in log if action == "archive")
        n_remove = sum(1 for action, _, _ in log if action == "remove")
        verb = "archived" if apply else "would archive"
        print(f"cleanup: {verb} {n_archive}, {'removed' if apply else 'would remove'} {n_remove}, "
              f"~{bytes_freed/1024/1024:.1f}MB")

    return 0


if __name__ == "__main__":
    sys.exit(main())
