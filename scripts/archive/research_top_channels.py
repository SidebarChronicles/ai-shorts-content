#!/usr/bin/env python3
"""Pull top-performing true crime shorts from YouTube for competitive analysis.

Uses the existing YouTube Data API credentials (token.json) — no extra auth needed.
Runs 5 search queries, deduplicates results, fetches statistics, and writes a
ranked markdown report for use by suggest_improvements.py.

Usage:
    python scripts/research_top_channels.py
    python scripts/research_top_channels.py --max-results 20
    python scripts/research_top_channels.py --queries "true crime,crime shorts"

Quota cost: ~550 units out of 10,000/day (5 × search.list + statistics batch)

Output:
    output/analytics/competitive_intel_YYYY-MM-DD.md
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
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
ANALYTICS_DIR = PROJECT_ROOT / "output" / "analytics"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

DEFAULT_QUERIES = [
    "true crime shorts",
    "federal crime short",
    "DOJ conviction short",
    "white collar crime short",
    "crime sentencing short",
]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def load_credentials() -> Credentials:
    if not TOKEN_PATH.exists():
        sys.exit(
            "[FATAL] No token.json found.\n"
            "        Run: python scripts/youtube_oauth_setup.py"
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
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


# ---------------------------------------------------------------------------
# Search + statistics
# ---------------------------------------------------------------------------

def search_top_shorts(youtube, query: str, max_results: int = 10) -> list[dict]:
    """Return up to max_results short videos ordered by view count."""
    try:
        resp = youtube.search().list(
            q=query,
            type="video",
            videoDuration="short",
            order="viewCount",
            maxResults=max_results,
            part="snippet",
            relevanceLanguage="en",
            safeSearch="moderate",
        ).execute()
    except HttpError as e:
        print(f"  ⚠  Search failed for '{query}': {e}", file=sys.stderr)
        return []

    results = []
    for item in resp.get("items", []):
        snippet = item["snippet"]
        results.append({
            "video_id": item["id"]["videoId"],
            "title": snippet["title"],
            "channel_title": snippet["channelTitle"],
            "channel_id": snippet.get("channelId", ""),
            "published_at": snippet.get("publishedAt", "")[:10],
            "description_preview": snippet.get("description", "")[:200],
            "query": query,
        })
    return results


def fetch_statistics(youtube, video_ids: list[str]) -> dict[str, dict]:
    """Fetch view/like counts for a list of video IDs. Returns {video_id: stats}."""
    stats = {}
    # API accepts up to 50 IDs per call
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        try:
            resp = youtube.videos().list(
                id=",".join(batch),
                part="statistics",
            ).execute()
        except HttpError as e:
            print(f"  ⚠  Statistics fetch failed: {e}", file=sys.stderr)
            continue
        for item in resp.get("items", []):
            stats[item["id"]] = item.get("statistics", {})
    return stats


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def render_report(videos: list[dict], queries: list[str]) -> str:
    today = date.today().isoformat()
    lines = [
        f"# Competitive Intel — True Crime Shorts — {today}",
        "",
        f"Queries run: {', '.join(f'`{q}`' for q in queries)}",
        f"Unique videos analyzed: **{len(videos)}**",
        "",
        "---",
        "",
        "## Top performers (by view count)",
        "",
        "| Rank | Title | Channel | Views | Published |",
        "|---|---|---|---|---|",
    ]

    for i, v in enumerate(videos[:30], 1):
        views = v.get("views", 0)
        views_fmt = f"{views:,}" if views else "n/a"
        title = v["title"][:60] + ("…" if len(v["title"]) > 60 else "")
        lines.append(
            f"| {i} | {title} | {v['channel_title']} | {views_fmt} | {v['published_at']} |"
        )

    lines += [
        "",
        "## Title list for pattern analysis",
        "",
        "*(Pass this report to `suggest_improvements.py` for Claude's analysis.)*",
        "",
    ]

    # Extract top 25 titles for pattern analysis
    for i, v in enumerate(videos[:25], 1):
        lines.append(f"{i}. {v['title']}")

    lines += [
        "",
        "## Channel breakdown",
        "",
        "| Channel | Videos in top results | Highest views |",
        "|---|---|---|",
    ]

    channel_data: dict[str, dict] = {}
    for v in videos:
        cname = v["channel_title"]
        if cname not in channel_data:
            channel_data[cname] = {"count": 0, "max_views": 0}
        channel_data[cname]["count"] += 1
        channel_data[cname]["max_views"] = max(
            channel_data[cname]["max_views"], v.get("views", 0)
        )

    for cname, data in sorted(channel_data.items(), key=lambda x: -x[1]["max_views"])[:15]:
        max_views = f"{data['max_views']:,}" if data["max_views"] else "n/a"
        lines.append(f"| {cname} | {data['count']} | {max_views} |")

    lines += [
        "",
        "---",
        "",
        "Run `python scripts/suggest_improvements.py` to generate Claude's analysis and recommendations.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Pull competitive intel from top true crime shorts.")
    parser.add_argument("--max-results", type=int, default=10, help="Results per query (default 10)")
    parser.add_argument("--queries", type=str, default=None,
                        help="Comma-separated search queries (overrides defaults)")
    args = parser.parse_args()

    queries = [q.strip() for q in args.queries.split(",")] if args.queries else DEFAULT_QUERIES

    print("── Competitive Research ──")
    print(f"  Queries: {len(queries)}")

    creds = load_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    # Collect results, deduplicate by video_id
    seen_ids: set[str] = set()
    all_videos: list[dict] = []

    for query in queries:
        print(f"  Searching: '{query}'…")
        results = search_top_shorts(youtube, query, args.max_results)
        for r in results:
            if r["video_id"] not in seen_ids:
                seen_ids.add(r["video_id"])
                all_videos.append(r)

    print(f"  Unique videos: {len(all_videos)}")

    # Fetch statistics
    print("  Fetching statistics…")
    stats = fetch_statistics(youtube, [v["video_id"] for v in all_videos])

    for v in all_videos:
        s = stats.get(v["video_id"], {})
        v["views"] = int(s.get("viewCount", 0))
        v["likes"] = int(s.get("likeCount", 0))
        v["comments"] = int(s.get("commentCount", 0))

    # Sort by views descending
    all_videos.sort(key=lambda x: -x.get("views", 0))

    report_md = render_report(all_videos, queries)

    today = date.today().isoformat()
    out_path = ANALYTICS_DIR / f"competitive_intel_{today}.md"
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report_md)

    print(f"  ✓ Wrote {out_path.relative_to(PROJECT_ROOT)}")
    top = all_videos[0] if all_videos else None
    if top:
        print(f"  Top result: '{top['title'][:50]}' — {top.get('views', 0):,} views")


if __name__ == "__main__":
    main()
