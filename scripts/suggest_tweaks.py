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
from _queue_scan import load_queue_meta  # noqa: E402  # shared scanner; see scripts/_queue_scan.py

load_dotenv(PROJECT_ROOT / ".env")

ANALYTICS_DIR = PROJECT_ROOT / "output" / "analytics"
SCRIPTS_OUT_DIR = PROJECT_ROOT / "output" / "scripts"
QUEUE_DIR = PROJECT_ROOT / "story_queue"
CROSS_POST_PATH = PROJECT_ROOT / "output" / "cross_post_status.json"

MIN_VIEWS_FOR_SIGNAL = 100  # below this, treat as no-data

# TikTok blend: weight applied to median TT engagement when scoring voice/subgenre
# composite. Pure YT AVP when there's no TT data. Tune in 0.1 increments after
# a few weeks of cross-platform data — see docs/TIKTOK_ANALYTICS.md.
TT_WEIGHT = 0.3
TT_MIN_IMPRESSIONS = 100  # below this, TT engagement rate is noise — ignore


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

_YT_REPORT_STEM_RE = re.compile(r"^report_\d{4}-\d{2}-\d{2}$")


def load_latest_analytics() -> dict | None:
    """Return the most recent TrueCrime YouTube analytics report JSON, or None.

    Strictly matches `report_YYYY-MM-DD.json` (the TrueCrime story pipeline's
    output). Excludes sibling variants written to the same dir by other
    pipelines: `report_*_tiktok.json` (TT analytics) and `report_*_game.json`
    (game pipeline's --game mode).
    """
    if not ANALYTICS_DIR.exists():
        return None
    reports = sorted(
        (p for p in ANALYTICS_DIR.glob("report_*.json")
         if _YT_REPORT_STEM_RE.match(p.stem)),
        reverse=True,
    )
    if not reports:
        return None
    try:
        return json.loads(reports[0].read_text())
    except (json.JSONDecodeError, OSError):
        return None


def load_latest_tiktok_analytics() -> dict | None:
    """Return the most recent TikTok analytics report JSON, or None."""
    if not ANALYTICS_DIR.exists():
        return None
    reports = sorted(ANALYTICS_DIR.glob("report_*_tiktok.json"), reverse=True)
    if not reports:
        return None
    try:
        return json.loads(reports[0].read_text())
    except (json.JSONDecodeError, OSError):
        return None


def tt_engagement(metrics: dict | None) -> float | None:
    """Return (likes+comments+shares) / impressions for a TT post, or None.

    Returns None when metrics are missing or impressions are below the noise
    floor (TT_MIN_IMPRESSIONS).
    """
    if not metrics:
        return None
    imps = metrics.get("impressions") or 0
    if imps < TT_MIN_IMPRESSIONS:
        return None
    interactions = (
        (metrics.get("likes") or 0)
        + (metrics.get("comments") or 0)
        + (metrics.get("shares") or 0)
    )
    return interactions / imps


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


# load_queue_meta lives in scripts/_queue_scan.py - imported above.


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def aggregate_by(
    yt_report: dict,
    tt_report: dict | None,
    queue_meta: dict,
    key: str,
) -> dict[str, dict[str, list[float]]]:
    """Group YT-eligible videos by dimension → {group: {"yt_avp": [...], "tt_eng": [...]}}.

    Iterates the YT report's videos (filtered by MIN_VIEWS_FOR_SIGNAL). For
    each surviving case, if the same case_id also appears in tt_report with
    enough impressions, the TT engagement rate is appended to that group's
    tt_eng list. Groups always carry yt_avp; tt_eng may be empty.
    """
    tt_videos: dict = (tt_report or {}).get("videos", {}) if tt_report else {}
    groups: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"yt_avp": [], "tt_eng": []}
    )
    for case_id, video in (yt_report.get("videos") or {}).items():
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
        groups[k]["yt_avp"].append(float(avp))
        tt_case = tt_videos.get(case_id)
        if tt_case:
            eng = tt_engagement(tt_case.get("metrics"))
            if eng is not None:
                groups[k]["tt_eng"].append(eng)
    return dict(groups)


def median_or_none(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _signal_range(groups: dict[str, dict[str, list[float]]], signal: str) -> tuple[float, float] | None:
    """Return (min, max) of medians across groups for the given signal, or None."""
    medians = [statistics.median(g[signal]) for g in groups.values() if g[signal]]
    if not medians:
        return None
    return min(medians), max(medians)


def _normalize(value: float, rng: tuple[float, float] | None) -> float:
    """Min-max normalize to [0, 1]. Degenerate range (one group) → 1.0."""
    if rng is None:
        return 0.0
    lo, hi = rng
    if hi <= lo:
        return 1.0
    return (value - lo) / (hi - lo)


def composite_score(
    yt_med: float,
    tt_med: float | None,
    yt_range: tuple[float, float] | None,
    tt_range: tuple[float, float] | None,
    weight: float,
) -> float:
    """Blend normalized YT AVP and TT engagement into a 0-1 composite.

    Falls back to pure normalized YT when tt_med is None (no TT data for this
    group). Both signals are min-max normalized using the report-wide range
    passed in, so the composite is comparable across groups within one run.
    """
    yt_norm = _normalize(yt_med, yt_range)
    if tt_med is None:
        return yt_norm
    tt_norm = _normalize(tt_med, tt_range)
    return (1.0 - weight) * yt_norm + weight * tt_norm


def rank_groups(
    groups: dict[str, dict[str, list[float]]],
) -> list[tuple[str, float, float | None, float, int]]:
    """Return [(name, yt_med, tt_med_or_None, composite, n), ...] sorted by composite desc."""
    yt_range = _signal_range(groups, "yt_avp")
    tt_range = _signal_range(groups, "tt_eng")
    ranked: list[tuple[str, float, float | None, float, int]] = []
    for name, sigs in groups.items():
        yt_med = median_or_none(sigs["yt_avp"])
        if yt_med is None:
            continue
        tt_med = median_or_none(sigs["tt_eng"])
        comp = composite_score(yt_med, tt_med, yt_range, tt_range, weight=TT_WEIGHT)
        ranked.append((name, yt_med, tt_med, comp, len(sigs["yt_avp"])))
    ranked.sort(key=lambda x: x[3], reverse=True)
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


def write_full_report(
    out_path: Path,
    report: dict,
    tt_report: dict | None,
    queue_meta: dict,
) -> None:
    lines: list[str] = []
    lines.append(f"# Suggested tweaks — {date.today().isoformat()}")
    lines.append("")

    # Yesterday at a glance
    rollup = report.get("channel_rollup", {})
    n_videos = len([v for v in (report.get("videos") or {}).values()
                    if v.get("metrics", {}).get("views", 0) >= MIN_VIEWS_FOR_SIGNAL])
    lines.append("## Yesterday at a glance")
    lines.append(f"- Videos analyzed (YT): {n_videos} (≥{MIN_VIEWS_FOR_SIGNAL} views threshold)")
    lines.append(f"- Total channel views (30d): {rollup.get('views', 0):,}")
    lines.append(f"- Channel avg view %: {rollup.get('averageViewPercentage', 0):.1f}%")
    lines.append(f"- Subs gained (30d): {rollup.get('subscribersGained', 0)}")
    tt_totals = (tt_report or {}).get("totals") if tt_report else None
    if tt_totals:
        tt_imps = tt_totals.get("impressions", 0) or 0
        tt_likes = tt_totals.get("likes", 0) or 0
        tt_comments = tt_totals.get("comments", 0) or 0
        tt_shares = tt_totals.get("shares", 0) or 0
        tt_eng_rate = ((tt_likes + tt_comments + tt_shares) / tt_imps) if tt_imps else 0.0
        lines.append(f"- TT impressions (window): {tt_imps:,} | engagement rate: {tt_eng_rate*100:.2f}%")
    elif tt_report:
        lines.append("- TT: report present but no metrics yet (posts <24h old or Starter tier)")
    else:
        lines.append("- TT: no report — run `/tiktok-analytics` or wait for tomorrow's `/morning`")
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
    has_any_tt = bool(tt_report and (tt_report.get("totals") or {}).get("impressions"))
    blend_note = (
        f" — ordering blends YT AVP and TT engagement (TT weight: {int(TT_WEIGHT*100)}%)"
        if has_any_tt else ""
    )
    lines.append(f"## Patterns (per dimension{blend_note})")
    lines.append("")

    for dim_label, key in (("Voice", "voice"), ("Sub-genre", "subgenre"),
                           ("Hook formula", "hook_formula"), ("Narrator gender", "gender")):
        groups = aggregate_by(report, tt_report, queue_meta, key)
        ranked = rank_groups(groups)
        if not ranked:
            continue
        lines.append(f"### By {dim_label}")
        lines.append("| Value | Median YT AVP | Median TT engagement | N |")
        lines.append("|---|---|---|---|")
        for name, yt_med, tt_med, _comp, n in ranked:
            tt_cell = "—" if tt_med is None else f"{tt_med*100:.2f}%"
            lines.append(f"| `{name}` | **{yt_med:.1f}%** | {tt_cell} | {n} |")
        if len(ranked) >= 2:
            top = ranked[0]
            bot = ranked[-1]
            yt_gap = top[1] - bot[1]
            if yt_gap >= 5.0:
                lines.append("")
                lines.append(f"→ **Recommendation:** prefer `{top[0]}` "
                             f"(+{yt_gap:.1f} pts YT AVP over `{bot[0]}`)")
        lines.append("")

    # Today's recommended skews
    lines.append("## Today's recommended skews")
    lines.append("")
    voice_groups = aggregate_by(report, tt_report, queue_meta, "voice")
    sub_groups = aggregate_by(report, tt_report, queue_meta, "subgenre")
    voice_ranked = rank_groups(voice_groups)
    sub_ranked = rank_groups(sub_groups)
    if voice_ranked:
        lines.append(f"- Prefer voices: {', '.join(f'`{v}`' for v, _, _, _, _ in voice_ranked[:3])}")
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

    tt_report = load_latest_tiktok_analytics()
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

    write_full_report(out_path, report, tt_report, queue_meta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
