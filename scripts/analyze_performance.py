#!/usr/bin/env python3
"""Pull YouTube Analytics for every posted TrueCrime Short and write a
markdown report Justin can review (in Cowork or directly).

Run from Claude Code on the Mac — this script needs network access that the
Cowork sandbox doesn't have.

Usage:
    python scripts/analyze_performance.py            # all posted cases
    python scripts/analyze_performance.py --case 04  # one case only
    python scripts/analyze_performance.py --days 7   # restrict to last 7 days

Prerequisites (one-time):
  1. Enable "YouTube Analytics API" in Google Cloud Console
     (APIs & Services → Library → search "YouTube Analytics API" → Enable)
  2. Re-run `python scripts/youtube_oauth_setup.py` to grant the new
     yt-analytics.readonly scope (the SCOPES list already includes it)

Outputs:
    output/analytics/report_YYYY-MM-DD.md   human-readable digest
    output/analytics/report_YYYY-MM-DD.json raw data dump for downstream work
"""

from __future__ import annotations
import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _atomic import atomic_write_text  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOKEN_PATH = PROJECT_ROOT / "token.json"
POSTED_PATH = PROJECT_ROOT / "output" / "videos" / "_posted.json"
GAME_POSTED_PATH = PROJECT_ROOT / "output" / "game_videos" / "_posted.json"
SCRIPTS_DIR = PROJECT_ROOT / "output" / "scripts"
ANALYTICS_DIR = PROJECT_ROOT / "output" / "analytics"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube",
          "https://www.googleapis.com/auth/yt-analytics.readonly"]


# ---------------------------------------------------------------------------
# Auth + loading
# ---------------------------------------------------------------------------

def load_credentials() -> Credentials:
    if not TOKEN_PATH.exists():
        sys.exit(
            f"[FATAL] No token.json at {TOKEN_PATH}.\n"
            "        Run: python scripts/youtube_oauth_setup.py"
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds.has_scopes(["https://www.googleapis.com/auth/yt-analytics.readonly"]):
        sys.exit(
            "[FATAL] token.json doesn't have the yt-analytics.readonly scope.\n"
            "        Re-run: python scripts/youtube_oauth_setup.py\n"
            "        (and make sure YouTube Analytics API is enabled in Google Cloud)"
        )
    if not creds.valid:
        if not creds.refresh_token:
            sys.exit(
                "[FATAL] token.json has no refresh_token.\n"
                "        Re-run: python scripts/youtube_oauth_setup.py"
            )
        try:
            creds.refresh(Request())
        except RefreshError as e:
            sys.exit(
                f"[FATAL] OAuth refresh failed: {e}\n"
                "        Re-run: python scripts/youtube_oauth_setup.py"
            )
        atomic_write_text(TOKEN_PATH, creds.to_json())
    return creds


def load_posted(path: Path = POSTED_PATH) -> dict:
    if not path.exists():
        sys.exit(
            f"[FATAL] No posted videos found at {path}.\n"
            "        Upload at least one video first (or backfill manually-uploaded videos)."
        )
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Analytics queries
# ---------------------------------------------------------------------------

CORE_METRICS = [
    "views",
    "estimatedMinutesWatched",
    "averageViewDuration",
    "averageViewPercentage",
    "subscribersGained",
    "subscribersLost",
    "likes",
    "dislikes",
    "shares",
    "comments",
]


def query_video_metrics(yta, video_id: str, start_date: str, end_date: str) -> dict:
    """Aggregate metrics for a single video over a date range."""
    try:
        resp = yta.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics=",".join(CORE_METRICS),
            filters=f"video=={video_id}",
        ).execute()
    except HttpError as e:
        return {"_error": str(e)}

    rows = resp.get("rows") or []
    if not rows:
        return {"_no_data": True}
    headers = [h["name"] for h in resp["columnHeaders"]]
    return dict(zip(headers, rows[0]))


def query_retention_curve(yta, video_id: str, start_date: str, end_date: str) -> list[tuple[float, float]]:
    """Return list of (elapsedRatio, audienceWatchRatio) tuples."""
    try:
        resp = yta.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="audienceWatchRatio",
            dimensions="elapsedVideoTimeRatio",
            filters=f"video=={video_id};audienceType==ORGANIC",
        ).execute()
    except HttpError:
        return []
    return [(r[0], r[1]) for r in resp.get("rows", [])]


# ---------------------------------------------------------------------------
# Channel-level rollup
# ---------------------------------------------------------------------------

def query_channel_rollup(yta, start_date: str, end_date: str) -> dict:
    try:
        resp = yta.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics=",".join(CORE_METRICS),
        ).execute()
    except HttpError as e:
        return {"_error": str(e)}
    rows = resp.get("rows") or []
    if not rows:
        return {"_no_data": True}
    headers = [h["name"] for h in resp["columnHeaders"]]
    return dict(zip(headers, rows[0]))


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def ascii_retention_bar(curve: list[tuple[float, float]], width: int = 40) -> str:
    """Render a tiny ASCII bar chart for the retention curve."""
    if not curve:
        return "(no retention data yet)"
    lines = []
    for elapsed_ratio, watch_ratio in curve:
        # elapsed 0.0 = start, 1.0 = end
        # watch_ratio is the fraction of viewers still watching at that point
        filled = int(round(watch_ratio * width))
        bar = "█" * filled + "·" * (width - filled)
        lines.append(f"  {elapsed_ratio * 100:5.1f}%  {bar} {watch_ratio * 100:5.1f}%")
    return "\n".join(lines)


def video_section(case_id: str, info: dict, metrics: dict, curve: list, today: date) -> str:
    pub_date = info.get("scheduled_publish", "")
    try:
        pub_dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
        days_live = (today - pub_dt.date()).days
        live_str = f"{days_live} day(s) live (published {pub_dt.date().isoformat()})"
    except Exception:
        live_str = f"published: {pub_date}"

    out = [f"### {case_id}",
           f"- **Watch:** {info.get('watch_url','(none)')}",
           f"- **{live_str}**",
           ""]

    if "_no_data" in metrics:
        out.append("_No analytics data yet — YouTube needs ~48-72h after publish for numbers to stabilize._")
        out.append("")
        return "\n".join(out)
    if "_error" in metrics:
        out.append(f"_Error fetching metrics:_ `{metrics['_error']}`")
        out.append("")
        return "\n".join(out)

    views = int(metrics.get("views", 0))
    watch_min = float(metrics.get("estimatedMinutesWatched", 0))
    avg_dur = float(metrics.get("averageViewDuration", 0))
    avg_pct = float(metrics.get("averageViewPercentage", 0))
    subs_gained = int(metrics.get("subscribersGained", 0))
    subs_lost = int(metrics.get("subscribersLost", 0))
    likes = int(metrics.get("likes", 0))
    dislikes = int(metrics.get("dislikes", 0))
    shares = int(metrics.get("shares", 0))
    comments = int(metrics.get("comments", 0))

    like_ratio = (likes / (likes + dislikes) * 100) if (likes + dislikes) else 0
    engagement = ((likes + shares + comments) / views * 100) if views else 0

    # Highlight a few headline numbers
    out += [
        f"| Metric | Value |",
        f"|---|---|",
        f"| Views | **{views:,}** |",
        f"| Watch time | {watch_min:.1f} min total |",
        f"| Avg view duration | {avg_dur:.1f}s |",
        f"| Avg view % (retention through) | **{avg_pct:.1f}%** |",
        f"| Subscribers gained / lost | +{subs_gained} / -{subs_lost} |",
        f"| Likes / Dislikes | {likes} / {dislikes} ({like_ratio:.0f}% positive) |",
        f"| Shares / Comments | {shares} / {comments} |",
        f"| Engagement rate | {engagement:.2f}% |",
        "",
    ]

    # Add retention curve
    out.append("**Audience retention curve:**")
    out.append("```")
    out.append(ascii_retention_bar(curve))
    out.append("```")

    # Quick interpretation
    interp = interpret(avg_pct, engagement, subs_gained, views, curve)
    if interp:
        out.append("**Read:**")
        for line in interp:
            out.append(f"- {line}")

    out.append("")
    return "\n".join(out)


def interpret(avg_pct: float, engagement: float, subs_gained: int, views: int, curve: list) -> list[str]:
    """Plain-language commentary based on simple thresholds.
    Refine over time as we learn what's normal for this channel."""
    notes = []
    if views < 100:
        notes.append("Too early to draw conclusions — needs more views.")
        return notes

    if avg_pct >= 70:
        notes.append("Excellent retention — viewers watch most of the video.")
    elif avg_pct >= 50:
        notes.append("Solid retention. Format is working.")
    elif avg_pct >= 30:
        notes.append("Mediocre retention. Check the retention curve for the drop-off second.")
    else:
        notes.append("Weak retention. Likely a hook or pacing problem in the first 5 seconds.")

    if curve and len(curve) > 3:
        # Look for a big drop in first 10% of video
        first_window = [r for e, r in curve if e <= 0.10]
        if first_window:
            initial = first_window[0]
            after = first_window[-1]
            if initial - after > 0.30:
                notes.append(
                    f"Sharp early drop-off: lost {(initial-after)*100:.0f}% of viewers in the first "
                    "10% of the video. The hook isn't holding."
                )

    if engagement >= 4:
        notes.append(f"High engagement ({engagement:.1f}%) — viewers are reacting + commenting.")
    elif engagement < 1:
        notes.append(f"Low engagement ({engagement:.2f}%) — passive views, little interaction.")

    if subs_gained > 0 and views > 0:
        sub_rate = subs_gained / views * 100
        if sub_rate >= 0.5:
            notes.append(f"Strong subscriber conversion: {sub_rate:.2f}% of viewers subscribed.")
        elif sub_rate < 0.05:
            notes.append("Few viewers converting to subs — channel identity may not be clear from this video alone.")

    return notes


def channel_section(rollup: dict, span_days: int) -> str:
    if "_no_data" in rollup:
        return "## Channel rollup\n\n_No channel-level data yet._\n"
    if "_error" in rollup:
        return f"## Channel rollup\n\n_Error:_ `{rollup['_error']}`\n"

    views = int(rollup.get("views", 0))
    watch_min = float(rollup.get("estimatedMinutesWatched", 0))
    avg_dur = float(rollup.get("averageViewDuration", 0))
    subs_net = int(rollup.get("subscribersGained", 0)) - int(rollup.get("subscribersLost", 0))

    return (
        f"## Channel rollup (last {span_days} days)\n\n"
        f"- **Total views:** {views:,}\n"
        f"- **Watch time:** {watch_min:.0f} minutes ({watch_min/60:.1f} hours)\n"
        f"- **Avg view duration across channel:** {avg_dur:.1f}s\n"
        f"- **Net subscribers:** {'+' if subs_net >= 0 else ''}{subs_net}\n\n"
    )


# ---------------------------------------------------------------------------
# Voice leaderboard (game videos only)
# ---------------------------------------------------------------------------

def _lookup_voice(case_id: str) -> tuple[str, str]:
    """Return (voice_id, voice_name) from game_config.json, or ('unknown', 'Unknown')."""
    config = SCRIPTS_DIR / case_id / "game_config.json"
    if config.exists():
        try:
            cfg = json.loads(config.read_text())
            vid = cfg.get("voice_id", "")
            vname = cfg.get("voice_name", "")
            if vid:
                return vid, vname or vid[:8]
        except (json.JSONDecodeError, OSError):
            pass
    return "unknown", "Unknown"


def voice_leaderboard_section(voice_data: dict[str, list[float]]) -> str:
    """voice_data: {voice_name: [avg_view_pct, ...]}. Returns markdown section."""
    if not voice_data:
        return ""

    MIN_VIDEOS = 3
    lines = ["## Voice Leaderboard", "",
             "| Voice | Videos | Avg view % | Avg views |",
             "|---|---|---|---|"]

    entries = []
    for vname, pcts in sorted(voice_data.items()):
        n = len(pcts)
        avg_pct = sum(p for p, _ in pcts) / n if pcts else 0.0
        avg_views = sum(v for _, v in pcts) / n if pcts else 0
        note = "" if n >= MIN_VIDEOS else " _(< 3 videos — not enough data)_"
        entries.append((avg_pct, vname, n, avg_pct, avg_views, note))

    for _, vname, n, avg_pct, avg_views, note in sorted(entries, reverse=True):
        lines.append(f"| {vname}{note} | {n} | {avg_pct:.1f}% | {avg_views:,.0f} |")

    lines += ["", "_Need ≥ 3 videos per voice for reliable comparisons._",
              "_Switch all new videos to a voice once it leads by 15+ avg view % with ≥5 videos._", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Pull YouTube Analytics for posted shorts.")
    parser.add_argument("--case", type=str, default=None,
                        help="Single case to analyze (e.g. '04'). Default: all posted.")
    parser.add_argument("--days", type=int, default=30,
                        help="Lookback window in days (default 30).")
    parser.add_argument("--game", action="store_true",
                        help="Analyze game videos (output/game_videos/_posted.json) instead of truecrime")
    args = parser.parse_args()

    today = date.today()
    start = (today - timedelta(days=args.days)).isoformat()
    end = today.isoformat()

    creds = load_credentials()
    yt_analytics = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)

    posted_path = GAME_POSTED_PATH if args.game else POSTED_PATH
    posted = load_posted(posted_path)
    if args.case:
        match = [k for k in posted if k == args.case or k.startswith(args.case)]
        if not match:
            sys.exit(f"[FATAL] No posted case matches {args.case!r}. Available: {list(posted)}")
        posted = {k: posted[k] for k in match}

    label = "game" if args.game else "truecrime"
    print(f"Pulling analytics for {len(posted)} {label} video(s), window {start} → {end}…\n")

    # Channel rollup
    rollup = query_channel_rollup(yt_analytics, start, end)

    # Per-video — also collect voice data for the leaderboard (game mode only)
    sections = []
    voice_data: dict[str, list[tuple[float, float]]] = {}
    raw_dump = {"generated_at": datetime.now(timezone.utc).isoformat(),
                "window": {"start": start, "end": end},
                "channel_rollup": rollup,
                "videos": {}}
    for case_id, info in sorted(posted.items()):
        video_id = info["video_id"]
        print(f"  • {case_id}  ({video_id})")
        metrics = query_video_metrics(yt_analytics, video_id, start, end)
        curve = query_retention_curve(yt_analytics, video_id, start, end)
        raw_dump["videos"][case_id] = {"metrics": metrics, "retention_curve": curve, **info}
        sections.append(video_section(case_id, info, metrics, curve, today))

        # Collect voice data when we have real numbers
        if args.game and "_no_data" not in metrics and "_error" not in metrics:
            _, vname = _lookup_voice(case_id)
            avg_pct = float(metrics.get("averageViewPercentage", 0))
            views = float(metrics.get("views", 0))
            voice_data.setdefault(vname, []).append((avg_pct, views))

    # Write report
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "_game" if args.game else ""
    md_path = ANALYTICS_DIR / f"report_{today.isoformat()}{suffix}.md"
    json_path = ANALYTICS_DIR / f"report_{today.isoformat()}{suffix}.json"

    md = [f"# Analytics Report — {today.isoformat()} ({label})",
          "",
          f"Window: **{start} → {end}** ({args.days} days)",
          "",
          channel_section(rollup, args.days),
          "## Per-video",
          ""]
    md.extend(sections)

    if args.game and voice_data:
        md.append("---")
        md.append("")
        md.append(voice_leaderboard_section(voice_data))

    md.append("---")
    md.append("")
    md.append("## How to read this report")
    md.append("")
    md.append("- **Avg view %** is the most predictive metric for shorts. Above 70% = excellent, below 30% = hook problem.")
    md.append("- **The retention curve** shows where viewers dropped off. A sharp dip in the first 10% means the hook didn't land. A flat curve means people watched to the end.")
    md.append("- **Subscriber conversion** of 0.5%+ is strong for a faceless / fact-based channel.")
    md.append("- **Engagement rate** of 4%+ indicates the content provokes reaction.")
    md.append("")
    md.append("Bring this report into Cowork and ask Claude to recommend writer-prompt or visual-template tweaks based on what's working / failing.")

    atomic_write_text(md_path, "\n".join(md))
    atomic_write_text(json_path, json.dumps(raw_dump, indent=2, default=str))

    print(f"\n✓ Wrote {md_path.relative_to(PROJECT_ROOT)}")
    print(f"✓ Wrote {json_path.relative_to(PROJECT_ROOT)}")
    print(f"\nOpen the .md in Cowork (or `open {md_path}` to view in macOS) and share with Claude for analysis.")


if __name__ == "__main__":
    main()
