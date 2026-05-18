#!/usr/bin/env python3
"""Analytics-driven quality diagnosis for posted TrueCrime Shorts.

Reads the latest analytics JSON report, maps retention drops to named beats,
and produces an iteration report with concrete action items.

Usage:
    python scripts/quality_loop.py
    python scripts/quality_loop.py --report 2026-05-17   # specific date
    python scripts/quality_loop.py --threshold 60        # override weak threshold (default 50)
    python scripts/quality_loop.py --min-views 50        # override min views guard (default 100)

Outputs:
    output/analytics/iteration_report_YYYY-MM-DD.md
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANALYTICS_DIR = PROJECT_ROOT / "output" / "analytics"
SCRIPTS_DIR = PROJECT_ROOT / "output" / "scripts"

# Beat names in order — maps to 6-beat structure from writer_prompt.md
BEAT_NAMES = ["hook", "setup", "beat1", "beat2", "scale", "outcome"]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_latest_report(date_override: str | None = None) -> tuple[Path, dict]:
    if date_override:
        path = ANALYTICS_DIR / f"report_{date_override}.json"
        if not path.exists():
            raise FileNotFoundError(f"No report found at {path}")
        return path, json.loads(path.read_text())

    candidates = sorted(ANALYTICS_DIR.glob("report_*.json"), reverse=True)
    if not candidates:
        raise FileNotFoundError(
            f"No report_*.json files found in {ANALYTICS_DIR}.\n"
            "Run: python scripts/analyze_performance.py"
        )
    path = candidates[0]
    return path, json.loads(path.read_text())


def load_timeline(case_id: str) -> list[dict]:
    """Parse timeline.txt into [{name, start, end, duration}, ...].

    Timeline lines alternate: 'file ...<scene_name>.png' then 'duration N.NNN'
    Returns list sorted by start time.
    """
    for filename in ("timeline_baked.txt", "timeline.txt"):
        path = SCRIPTS_DIR / case_id / filename
        if path.exists():
            break
    else:
        return []

    content = path.read_text()
    segments = []
    current_file = None
    cumulative = 0.0

    for line in content.splitlines():
        line = line.strip()
        if line.startswith("file "):
            # Extract scene name from path
            raw = line[5:].strip().strip("'\"")
            stem = Path(raw).stem  # e.g. "01_hook", "02_setup"
            # Map to beat name by index or by stem
            match = re.match(r"^(\d+)_(.+)$", stem)
            if match:
                idx = int(match.group(1)) - 1
                label = BEAT_NAMES[idx] if idx < len(BEAT_NAMES) else match.group(2)
            else:
                label = stem
            current_file = label
        elif line.startswith("duration ") and current_file is not None:
            dur = float(line.split()[1])
            segments.append({
                "name": current_file,
                "start": cumulative,
                "end": cumulative + dur,
                "duration": dur,
            })
            cumulative += dur
            current_file = None  # reset (last duplicate file line has no duration)

    return segments


# ---------------------------------------------------------------------------
# Diagnosis
# ---------------------------------------------------------------------------

def compute_hook_drop(curve: list[list[float]]) -> float:
    """Return the retention drop percentage in the first 10% of video runtime."""
    if not curve:
        return 0.0
    # curve = [[elapsed_ratio, watch_ratio], ...]
    first_point = curve[0][1] if curve else 1.0
    ten_pct_point = next(
        (r for e, r in curve if e >= 0.1),
        curve[-1][1] if curve else first_point
    )
    return (first_point - ten_pct_point) * 100


def find_drop_beat(curve: list[list[float]], timeline: list[dict]) -> str | None:
    """Find the beat where the largest single-step retention drop occurs."""
    if not curve or not timeline:
        return None

    # Find biggest drop in retention curve
    max_drop = 0.0
    drop_elapsed = None
    for i in range(1, len(curve)):
        drop = curve[i - 1][1] - curve[i][1]
        if drop > max_drop:
            max_drop = drop
            drop_elapsed = curve[i][0]

    if drop_elapsed is None:
        return None

    # Map elapsed_ratio to absolute time (need total duration)
    total_duration = timeline[-1]["end"] if timeline else 0
    if total_duration == 0:
        return None

    drop_time = drop_elapsed * total_duration

    # Find which beat this time falls in
    for segment in timeline:
        if segment["start"] <= drop_time <= segment["end"]:
            return segment["name"]

    return None


def engagement_rate(metrics: dict) -> float:
    views = metrics.get("views", 0)
    if views == 0:
        return 0.0
    interactions = (
        metrics.get("likes", 0) +
        metrics.get("shares", 0) +
        metrics.get("comments", 0)
    )
    return (interactions / views) * 100


def subscriber_conversion(metrics: dict) -> float:
    views = metrics.get("views", 0)
    if views == 0:
        return 0.0
    return (metrics.get("subscribersGained", 0) / views) * 100


def diagnose_video(case_id: str, metrics: dict, curve: list) -> dict:
    avg_pct = metrics.get("averageViewPercentage", 0.0)

    if avg_pct >= 70:
        status = "strong"
    elif avg_pct >= 50:
        status = "mediocre"
    else:
        status = "weak"

    timeline = load_timeline(case_id)
    hook_drop = compute_hook_drop(curve)
    drop_beat = find_drop_beat(curve, timeline)
    eng_rate = engagement_rate(metrics)
    sub_conv = subscriber_conversion(metrics)

    notes = []
    if hook_drop > 25:
        notes.append(f"Hook drop: {hook_drop:.0f}% retention lost in first 10% — hook formula needs review")
    if avg_pct < 30:
        notes.append("Avg view % below 30% — likely hook failure, consider re-upload with alternate title")
    if eng_rate >= 4:
        notes.append(f"Engagement rate {eng_rate:.1f}% — strong reaction signal")
    if sub_conv >= 0.5:
        notes.append(f"Sub conversion {sub_conv:.2f}% — above benchmark")

    return {
        "case_id": case_id,
        "views": metrics.get("views", 0),
        "avg_pct": avg_pct,
        "status": status,
        "hook_drop_pct": hook_drop,
        "drop_beat": drop_beat,
        "engagement_rate": eng_rate,
        "sub_conversion": sub_conv,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def render_report(diagnoses: list[dict], report_meta: dict) -> str:
    today = date.today().isoformat()
    lines = [
        f"# Retention & Quality Iteration Report — {today}",
        "",
        f"Analytics window: **{report_meta.get('window', {}).get('start', '?')} → "
        f"{report_meta.get('window', {}).get('end', '?')}**",
        "",
    ]

    if not diagnoses:
        lines += [
            "## No videos with sufficient data",
            "",
            "All posted videos have fewer than the minimum view threshold.",
            "Re-run this script after videos have been live 48–72 hours and accumulated views.",
        ]
        return "\n".join(lines)

    # Categorize
    strong = [d for d in diagnoses if d["status"] == "strong"]
    mediocre = [d for d in diagnoses if d["status"] == "mediocre"]
    weak = [d for d in diagnoses if d["status"] == "weak"]

    lines += [
        "## Summary",
        "",
        f"- **{len(diagnoses)} videos** with enough data",
        f"- **Strong** (≥70% avg retention): {len(strong)}",
        f"- **Mediocre** (50–70%): {len(mediocre)}",
        f"- **Weak** (<50%): {len(weak)}",
        "",
    ]

    # Cross-video signal
    hook_drops = [d for d in diagnoses if d["hook_drop_pct"] > 25]
    if hook_drops:
        lines += [
            f"**Cross-video signal:** {len(hook_drops)}/{len(diagnoses)} videos have hook drops >25% "
            f"— hook formula is the primary issue to address.",
            "",
        ]

    def render_section(title: str, items: list[dict]) -> list[str]:
        if not items:
            return []
        out = [f"## {title}", ""]
        for d in sorted(items, key=lambda x: x["avg_pct"]):
            out += [
                f"### {d['case_id']}",
                "",
                f"| Metric | Value |",
                f"|---|---|",
                f"| Avg view % | **{d['avg_pct']:.1f}%** |",
                f"| Views | {d['views']:,} |",
                f"| Hook drop (first 10%) | {d['hook_drop_pct']:.0f}% |",
                f"| Cliff beat | {d['drop_beat'] or '—'} |",
                f"| Engagement rate | {d['engagement_rate']:.2f}% |",
                f"| Sub conversion | {d['sub_conversion']:.3f}% |",
                "",
            ]
            if d["notes"]:
                out.append("**Read:**")
                for note in d["notes"]:
                    out.append(f"- {note}")
                out.append("")
        return out

    lines += render_section("Weak videos (<50% retention)", weak)
    lines += render_section("Mediocre videos (50–70%)", mediocre)
    lines += render_section("Strong videos (≥70%)", strong)

    # Action items
    lines += ["## Action items", ""]
    if weak:
        case_list = ", ".join(d["case_id"] for d in weak)
        lines.append(f"- **Re-upload candidates:** {case_list} — try alternate titles from `output/scripts/title_alternatives.md`")
    if hook_drops:
        lines.append("- **Hook revision:** Pass this report to `suggest_improvements.py` for concrete writer_prompt.md diffs")
    if not (weak or hook_drops):
        lines.append("- No urgent action items — content is performing well")

    lines += [
        "",
        "---",
        "",
        "Run `python scripts/suggest_improvements.py` to get Claude's specific writer-prompt fix recommendations.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose video retention and generate iteration report.")
    parser.add_argument("--report", metavar="YYYY-MM-DD", help="Specific report date to load")
    parser.add_argument("--threshold", type=float, default=50.0, help="Weak retention threshold (default 50.0)")
    parser.add_argument("--min-views", type=int, default=100, help="Minimum views to include (default 100)")
    args = parser.parse_args()

    try:
        report_path, report = load_latest_report(args.report)
    except FileNotFoundError as e:
        import sys
        sys.exit(f"ERROR: {e}")

    print(f"── Quality Loop ──")
    print(f"  Report: {report_path.name}")

    videos = report.get("videos", {})
    print(f"  Videos in report: {len(videos)}")

    diagnoses = []
    skipped = []
    for case_id, data in videos.items():
        metrics = data.get("metrics", {})
        views = metrics.get("views", 0)
        if views < args.min_views:
            skipped.append(case_id)
            continue
        curve = data.get("retention_curve", [])
        diagnoses.append(diagnose_video(case_id, metrics, curve))

    if skipped:
        print(f"  Skipped (< {args.min_views} views): {', '.join(skipped)}")

    print(f"  Diagnosed: {len(diagnoses)} videos")

    report_md = render_report(diagnoses, report)

    today = date.today().isoformat()
    out_path = ANALYTICS_DIR / f"iteration_report_{today}.md"
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report_md)
    print(f"  ✓ Wrote {out_path.relative_to(PROJECT_ROOT)}")

    if not diagnoses:
        print("\n  No videos with enough data yet — re-run after 48–72h.")
    else:
        weak_count = sum(1 for d in diagnoses if d["status"] == "weak")
        print(f"\n  {weak_count}/{len(diagnoses)} weak videos. See {out_path.name} for details.")
        print("  Next: python scripts/suggest_improvements.py")


if __name__ == "__main__":
    main()
