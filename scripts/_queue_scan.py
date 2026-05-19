"""Shared queue scanner for story_queue/SY_*.md stubs.

Centralizes the regex set that was previously duplicated between
`pick_today.py` and `suggest_tweaks.py`. Both consumers now read from here so
the two regex sets cannot drift independently.

Public API:
    scan_queue(queue_dir?)        -> list[dict]
    load_queue_meta(queue_dir?)   -> dict[str, dict]
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUEUE_DIR = PROJECT_ROOT / "story_queue"

STATUS_RE = re.compile(r"\*\*Status:\*\*\s*([A-Z_]+)")
SUBGENRE_RE = re.compile(r"\*\*Subgenre:\*\*\s*(\w+)")
SCORE_RE = re.compile(r"\*\*Mined score\*\*:\s*([\d.]+)")
VOICE_RE = re.compile(r"\*\*Voice:\*\*\s*([A-Za-z]+)")
GENDER_RE = re.compile(r"\*\*Narrator gender:\*\*\s*([MF])", re.IGNORECASE)


def scan_queue(queue_dir: Path = DEFAULT_QUEUE_DIR) -> list[dict]:
    """Return stub metadata for every SY_*.md in `queue_dir`.

    Excludes `SY_TEMPLATE*` files. Returns `[]` if the directory does not exist.

    Each dict:
        case_id      : str   (file stem, e.g. "SY_09_H_a_wife_shouldn_t_argue_w")
        status       : str   ("QUEUED" | "RENDERED" | "DELIVERED" | "UNKNOWN")
        subgenre     : str   ("Infidelity" | "Horror" | ... | "unknown")
        mined_score  : float (0.0 when missing)
        voice        : str | None
        gender       : "M" | "F" | None
    """
    items: list[dict] = []
    if not queue_dir.exists():
        return items
    for p in sorted(queue_dir.glob("SY_*.md")):
        if p.name.startswith("SY_TEMPLATE"):
            continue
        text = p.read_text()
        sm = STATUS_RE.search(text)
        gm = SUBGENRE_RE.search(text)
        sc = SCORE_RE.search(text)
        vm = VOICE_RE.search(text)
        gn = GENDER_RE.search(text)
        items.append({
            "case_id": p.stem,
            "status": sm.group(1) if sm else "UNKNOWN",
            "subgenre": gm.group(1) if gm else "unknown",
            "mined_score": float(sc.group(1)) if sc else 0.0,
            "voice": vm.group(1) if vm else None,
            "gender": gn.group(1).upper() if gn else None,
        })
    return items


def load_queue_meta(queue_dir: Path = DEFAULT_QUEUE_DIR) -> dict[str, dict]:
    """Return `{case_id: {voice, gender, subgenre}}` for every stub.

    Subgenre is normalized to `None` when missing (matches the pre-refactor
    behavior of `suggest_tweaks.load_queue_meta` so the `"unknown"` fallback in
    callers still kicks in when other sources also miss).
    """
    return {
        it["case_id"]: {
            "voice": it["voice"],
            "gender": it["gender"],
            "subgenre": it["subgenre"] if it["subgenre"] != "unknown" else None,
        }
        for it in scan_queue(queue_dir)
    }
