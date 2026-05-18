#!/usr/bin/env python3
"""Read previous day's analytics + emit suggested production tweaks for today.

Reads:
  - output/analytics/report_*.json  (latest, YouTube only for v1)
  - output/cross_post_status.json   (which videos posted to TT/IG/YT + gate %)
  - output/scripts/<case>/script_config.json  (for voice/hook_formula per video)
  - story_queue/SY_*.md             (Voice + Narrator gender per stub)

Writes:
  - output/analytics/suggested_tweaks_YYYY-MM-DD.md

The output is REVIEW MATERIAL for the human running /morning — never
auto-applies to queue stubs. /pick-today consumes the same data to skew
today's batch toward winning patterns.

When there's <100 views across all posted videos (current pre-launch state),
this script writes a "no data yet — pick by hand" placeholder and exits 0.

Usage:
    python scripts/suggest_tweaks.py
    python scripts/suggest_tweaks.py --date 2026-05-19
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import load_dotenv  # noqa: E402
from _atomic import atomic_write_text  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

ANALYTICS_DIR = PROJECT_ROOT / "output" / "analytics"
SCRIPTS_OUT_DIR = PROJECT_ROOT / "output" / "scripts"
QUEUE_DIR = PROJECT_ROOT / "story_queue"
CROSS_POST_PATH = PROJECT_ROOT / "output" / "cross_post_status.json"

MIN_VIEWS_FOR_SIGNAL = 100  # below this, treat as no-data


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_latest_analytics() -> dict | None:
    """Return the most recent analytics report JSON, or None."""
    if not ANALYTICS_DIR.exists():
        return None
    reports = sorted(ANALYTICS_DIR.glob("report_*.json"), reverse=True)
    if not reports:
        return None
    try:
        return json.loads(reports[0].read_text())
    except (json.JSONDecodeError, OSError):
        return None


def load_cross_post() -> dict:
    if not CROSS_POST_PATH.exists():
        return {}
    try:
        return json.loads(CROSS_POST_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def load_case_config(case_id: str) -> dict | None:
    p = SCRIPTS_OUT_DIR / case_id / "script_config.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def load_queue_meta() -> dict[str, dict]:
    """Return {sy_id: {voice, gender, subgenre}} for every queue stub."""
    out: dict[str, dict] = {}
    if not QUEUE_DIR.exists():
        return out
    voice_re = re.compile(r"\*\*Voice:\*\*\s*([A-Za-z]+)")
    gender_re = re.compile(r"\*\*Narrator gender:\*\*\s*([MF])", re.IGNORECASE)
    sub_re = re.compile(r"\*\*Subgenre:\*\*\s*(\w+)")
    for p in QUEUE_DIR.glob("SY_*.md"):
        if p.name.startswith("SY_TEMPLATE"):
            continue
        text = p.read_text()
        vm = voice_re.search(text)
        gm = gender_re.search(text)
        sm = sub_re.search(text)
        out[p.stem] = {
            "voice": vm.group(1) if vm else None,
            "gender": gm.group(1).upper() if gm else None,
            "subgenre": sm.group(1) if sm else None,
        }
    return out


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def aggregate_by(report: dict, queue_meta: dict, key: str) -> dict[str, list[float]]:
    """Group videos by (voice|subgenre|hook_formula|gender) → list of avg_view_pct."""
    groups: dict[str, list[float]] = defaultdict(list)
    for case_id, video in (report.get("videos") or {}).items():
        metrics = video.get("metrics", {})
        views = metrics.get("views", 0)
        avp = metrics.get("averageViewPercentage", 0)
        if views < MIN_VIEWS_FOR_SIGNAL:
            continue
        cfg = load_case_config(case_id) or {}
        meta = queue_meta.get(case_id, {})
        if key == "voice":
            k = cfg.get("voice_name") or meta.get("voice") or "unknown"
        elif key == "subgenre":
            k = cfg.get("subgenre") or meta.get("subgenre") or "unknown"
        elif key == "hook_formula":
            k = cfg.get("hook_formula") or "unknown"
        elif key == "gender":
            k = meta.get("gender") or "unknown"
        else:
            continue
        groups[k].append(float(avp))
    return dict(groups)


def median_or_none(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def rank_groups(groups: dict[str, list[float]]) -> list[tuple[str, float, int]]:
    """Return [(name, median_avp, n), ...] sorted by median desc."""
    ranked: list[tuple[str, float, int]] = []
    for name, vals in groups.items():
        m = median_or_none(vals)
        if m is None:
            continue
        ranked.append((name, m, len(vals)))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_no_data_report(out_path: Path, reason: str) -> None:
    body = f"""# Suggested tweaks — {date.today().isoformat()}

## Not enough data yet

{reason}

**Today's recommendation:** pick by hand using `/pick-today` or
`python scripts/story_orchestrator.py --next-queued`.

Re-run `/suggest-tweaks` once you have:
- ≥3 videos with ≥{MIN_VIEWS_FOR_SIGNAL} views each, OR
- TikTok eyeball-entered retention data (manual-entry tracker is a follow-up)
"""
    atomic_write_text(out_path, body)
    print(f"  ✓ wrote no-data placeholder to {out_path.relative_to(PROJECT_ROOT)}")


def write_full_report(out_path: Path, report: dict, queue_meta: dict) -> None:
    lines: list[str] = []
    lines.append(f"# Suggested tweaks — {date.today().isoformat()}")
    lines.append("")

    # Yesterday at a glance
    rollup = report.get("channel_rollup", {})
    n_videos = len([v for v in (report.get("videos") or {}).values()
                    if v.get("metrics", {}).get("views", 0) >= MIN_VIEWS_FOR_SIGNAL])
    lines.append("## Yesterday at a glance")
    lines.append(f"- Videos analyzed: {n_videos} (≥{MIN_VIEWS_FOR_SIGNAL} views threshold)")
    lines.append(f"- Total channel views (30d): {rollup.get('views', 0):,}")
    lines.append(f"- Channel avg view %: {rollup.get('averageViewPercentage', 0):.1f}%")
    lines.append(f"- Subs gained (30d): {rollup.get('subscribersGained', 0)}")
    lines.append("")

    # Best + worst single videos
    videos = sorted(
        ((cid, v.get("metrics", {})) for cid, v in (report.get("videos") or {}).items()),
        key=lambda x: x[1].get("averageViewPercentage", 0), reverse=True,
    )
    eligible = [(cid, m) for cid, m in videos if m.get("views", 0) >= MIN_VIEWS_FOR_SIGNAL]
    if eligible:
        best = eligible[0]
        worst = eligible[-1]
        lines.append(f"- **Best**: `{best[0]}` — {best[1].get('averageViewPercentage', 0):.1f}% AVP, "
                     f"{best[1].get('views', 0)} views")
        lines.append(f"- **Worst**: `{worst[0]}` — {worst[1].get('averageViewPercentage', 0):.1f}% AVP, "
                     f"{worst[1].get('views', 0)} views")
        lines.append("")

    # Patterns
    lines.append("## Patterns (median AVP per dimension)")
    lines.append("")

    for dim_label, key in (("Voice", "voice"), ("Sub-genre", "subgenre"),
                           ("Hook formula", "hook_formula"), ("Narrator gender", "gender")):
        groups = aggregate_by(report, queue_meta, key)
        ranked = rank_groups(groups)
        if not ranked:
            continue
        lines.append(f"### By {dim_label}")
        lines.append("| Value | Median AVP | N |")
        lines.append("|---|---|---|")
        for name, med, n in ranked:
            lines.append(f"| `{name}` | **{med:.1f}%** | {n} |")
        if len(ranked) >= 2:
            top = ranked[0]
            bot = ranked[-1]
            gap = top[1] - bot[1]
            if gap >= 5.0:
                lines.append("")
                lines.append(f"→ **Recommendation:** prefer `{top[0]}` (+{gap:.1f} pts over `{bot[0]}`)")
        lines.append("")

    # Today's recommended skews
    lines.append("## Today's recommended skews")
    lines.append("")
    voice_groups = aggregate_by(report, queue_meta, "voice")
    sub_groups = aggregate_by(report, queue_meta, "subgenre")
    voice_ranked = rank_groups(voice_groups)
    sub_ranked = rank_groups(sub_groups)
    if voice_ranked:
        lines.append(f"- Prefer voices: {', '.join(f'`{v}`' for v, _, _ in voice_ranked[:3])}")
    if sub_ranked:
        top_sub = sub_ranked[0][0]
        lines.append(f"- Skew today's batch toward `{top_sub}` (best-performing sub-genre)")
    if not voice_ranked and not sub_ranked:
        lines.append("- No clear winners yet — keep default rotation")
    lines.append("")

    # Hooks that retained well (verbatim, for the writer to study)
    lines.append("## Top-retaining hooks (verbatim)")
    lines.append("")
    if eligible:
        for cid, m in eligible[:5]:
            cfg = load_case_config(cid)
            if not cfg:
                continue
            beats = cfg.get("beats", [])
            hook = (beats[0].get("text") if beats else "") or "(hook not found)"
            lines.append(f"- **{m.get('averageViewPercentage', 0):.1f}% AVP** `{cid}` — \"{hook}\"")
    else:
        lines.append("- (none yet)")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"Generated by `scripts/suggest_tweaks.py`. Review this file before "
                 f"running `/pick-today` — the picker reads it for skew hints.")

    atomic_write_text(out_path, "\n".join(lines))
    print(f"  ✓ wrote analytics-driven tweaks to {out_path.relative_to(PROJECT_ROOT)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default=None, help="Date stamp for output filename (default: today)")
    args = ap.parse_args()

    out_date = args.date or date.today().isoformat()
    out_path = ANALYTICS_DIR / f"suggested_tweaks_{out_date}.md"
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"── suggest_tweaks → {out_path.relative_to(PROJECT_ROOT)}")

    report = load_latest_analytics()
    if not report:
        write_no_data_report(out_path,
                             "No analytics report found under `output/analytics/`. "
                             "Run `/analytics` first.")
        return 0

    queue_meta = load_queue_meta()

    # Count videos with usable signal
    n_signal = sum(1 for v in (report.get("videos") or {}).values()
                   if v.get("metrics", {}).get("views", 0) >= MIN_VIEWS_FOR_SIGNAL)
    if n_signal < 3:
        write_no_data_report(out_path,
                             f"Only {n_signal} video(s) have ≥{MIN_VIEWS_FOR_SIGNAL} views in "
                             f"the latest analytics window. Need at least 3 for meaningful "
                             f"medians.")
        return 0

    write_full_report(out_path, report, queue_meta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
