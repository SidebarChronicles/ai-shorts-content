#!/usr/bin/env python3
"""Pull TikTok analytics for every cross-posted case via PostFast.

PostFast's `GET /social-posts/analytics` returns impressions, reach, likes,
comments, shares, and clicks per post — for TikTok as well as IG/FB/etc.
We already have the API key and channel UUID in `.env` for the upload path
(`scripts/post_via_scheduler.py`), so this just adds the read side.

What it does NOT cover (per docs/TIKTOK_ANALYTICS.md):
  - per-video retention curve / watch-through %  → no public TT API exposes this
  - follower count / profile metrics             → would need TikTok Display API

Usage:
    python3 scripts/analyze_tiktok_performance.py            # all TT-posted cases, 30d window
    python3 scripts/analyze_tiktok_performance.py --days 7   # last 7 days
    python3 scripts/analyze_tiktok_performance.py --case SY_01_S_lakecabin
    python3 scripts/analyze_tiktok_performance.py --check-auth

Outputs (mirror analyze_performance.py for YouTube):
    output/analytics/report_YYYY-MM-DD_tiktok.md
    output/analytics/report_YYYY-MM-DD_tiktok.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _atomic import atomic_write_text  # noqa: E402
from _env import load_dotenv  # noqa: E402

TRACKER_PATH = PROJECT_ROOT / "output" / "cross_post_status.json"
ANALYTICS_DIR = PROJECT_ROOT / "output" / "analytics"

DEFAULT_BASE_URL = "https://api.postfa.st"
REQUEST_TIMEOUT = 60

# How wide a window around tracker timestamp counts as "this post"
MATCH_SLACK_SECONDS = 300  # ±5 min

# How many chars of caption to compare for tie-breaks
CAPTION_PREFIX_CHARS = 80


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class Config:
    def __init__(self) -> None:
        load_dotenv()
        self.api_key = os.environ.get("POSTFAST_API_KEY", "").strip()
        self.tt_account = os.environ.get("POSTFAST_TIKTOK_CHANNEL_ID", "").strip()
        self.base_url = os.environ.get("POSTFAST_BASE_URL", DEFAULT_BASE_URL).rstrip("/")

    def assert_ready(self) -> None:
        missing = []
        if not self.api_key:
            missing.append("POSTFAST_API_KEY")
        if not self.tt_account:
            missing.append("POSTFAST_TIKTOK_CHANNEL_ID")
        if missing:
            sys.exit(
                f"[FATAL] Missing env var(s): {', '.join(missing)}\n"
                "        See docs/CROSS_POSTING.md or run:\n"
                "        python3 scripts/post_via_scheduler.py --check-auth"
            )


def _headers(cfg: Config) -> dict[str, str]:
    return {"pf-api-key": cfg.api_key, "Accept": "application/json"}


def _http_get_json(cfg: Config, path: str, params: dict | None = None) -> tuple[int, object]:
    url = f"{cfg.base_url}{path}"
    if params:
        url = f"{url}?{urlparse.urlencode(params)}"
    req = urlrequest.Request(url, method="GET", headers=_headers(cfg))
    try:
        with urlrequest.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            raw = resp.read().decode(errors="replace")
            status = resp.status
    except urlerror.HTTPError as e:
        raw = e.read().decode(errors="replace") if hasattr(e, "read") else ""
        return e.code, raw
    except urlerror.URLError as e:
        return 0, f"URLError: {e.reason}"
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, raw


# ---------------------------------------------------------------------------
# Tracker + PostFast fetch
# ---------------------------------------------------------------------------


def load_tracker() -> dict:
    if not TRACKER_PATH.exists():
        sys.exit(f"[FATAL] {TRACKER_PATH} not found. Nothing to analyze.")
    return json.loads(TRACKER_PATH.read_text())


def tt_posted_cases(tracker: dict, case_filter: str | None) -> dict:
    """Return tracker entries with a real TikTok publish timestamp (not None / not __skipped__)."""
    out = {}
    for case_id, info in tracker.items():
        tt = info.get("tiktok")
        if not isinstance(tt, str) or tt.startswith("__"):
            continue
        if case_filter and case_id != case_filter:
            continue
        out[case_id] = info
    return out


def fetch_postfast_analytics(cfg: Config, start: datetime, end: datetime) -> tuple[list, str | None]:
    """Returns (posts, error_msg). posts is [] on error."""
    params = {
        "startDate": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "endDate": end.strftime("%Y-%m-%dT%H:%M:%S.999Z"),
        "socialMediaIds": cfg.tt_account,
    }
    status, body = _http_get_json(cfg, "/social-posts/analytics", params)
    if status != 200:
        return [], f"HTTP {status}: {str(body)[:300]}"
    if isinstance(body, dict):
        data = body.get("data")
        if isinstance(data, list):
            return data, None
        return [], f"unexpected response shape: {str(body)[:200]}"
    if isinstance(body, list):
        return body, None
    return [], f"unexpected response type: {type(body).__name__}"


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def _parse_iso(s: str) -> datetime | None:
    if not isinstance(s, str) or not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _load_caption_prefix(case_id: str, videos_dir: str) -> str:
    path = PROJECT_ROOT / videos_dir / f"{case_id}.tt_caption.txt"
    if not path.exists():
        return ""
    try:
        return path.read_text().strip()[:CAPTION_PREFIX_CHARS]
    except OSError:
        return ""


def match_case_to_post(case_id: str, info: dict, posts: list) -> tuple[dict | None, str]:
    """Returns (matched_post, confidence).

    Strategy: posts within ±5 min of tracker timestamp. If multiple, tie-break
    by caption prefix match. Returns (None, 'no_match') if nothing close.
    """
    tracker_dt = _parse_iso(info.get("tiktok", ""))
    if tracker_dt is None:
        return None, "no_match"
    window = timedelta(seconds=MATCH_SLACK_SECONDS)

    candidates = []
    for p in posts:
        pub_dt = _parse_iso(p.get("publishedAt", ""))
        if pub_dt is None:
            continue
        if abs((pub_dt - tracker_dt).total_seconds()) <= window.total_seconds():
            candidates.append(p)

    if not candidates:
        return None, "no_match"
    if len(candidates) == 1:
        return candidates[0], "high"

    # Tie-break by caption prefix
    cap_prefix = _load_caption_prefix(case_id, info.get("videos_dir", ""))
    if cap_prefix:
        for c in candidates:
            content = (c.get("content") or "").strip()[:CAPTION_PREFIX_CHARS]
            if content and content == cap_prefix:
                return c, "high"

    # Couldn't disambiguate confidently — pick the closest by time, mark medium
    candidates.sort(key=lambda c: abs((_parse_iso(c["publishedAt"]) - tracker_dt).total_seconds()))
    return candidates[0], "medium"


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _metric_int(latest: dict | None, key: str) -> int | None:
    if not latest:
        return None
    val = latest.get(key)
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def render_case_row(case_id: str, info: dict, post: dict | None, confidence: str) -> str:
    if post is None:
        return f"| {case_id} | _no PostFast match yet_ | – | – | – | – | – | – |"

    latest = post.get("latestMetric")
    if not latest:
        return f"| {case_id} | {confidence} | _no metrics yet_ | – | – | – | – | – |"

    impressions = _metric_int(latest, "impressions")
    reach = _metric_int(latest, "reach")
    likes = _metric_int(latest, "likes")
    comments = _metric_int(latest, "comments")
    shares = _metric_int(latest, "shares")
    clicks = _metric_int(latest, "clicks")

    def f(v):
        return "–" if v is None else f"{v:,}"

    return (f"| {case_id} | {confidence} | {f(impressions)} | {f(reach)} | "
            f"{f(likes)} | {f(comments)} | {f(shares)} | {f(clicks)} |")


def render_report(
    window_start: datetime,
    window_end: datetime,
    matches: dict,
    unmatched_posts: list,
    cfg: Config,
) -> tuple[str, dict]:
    today = date.today().isoformat()

    # Rollup across matched + having metrics
    totals = {"impressions": 0, "reach": 0, "likes": 0, "comments": 0, "shares": 0, "clicks": 0}
    have_data = 0
    for _, m in matches.items():
        latest = (m.get("post") or {}).get("latestMetric")
        if not latest:
            continue
        have_data += 1
        for k in totals:
            v = _metric_int(latest, k)
            if v is not None:
                totals[k] += v

    md = [
        f"# TikTok Analytics Report — {today}",
        "",
        f"Window: **{window_start.date().isoformat()} → {window_end.date().isoformat()}** "
        f"({(window_end - window_start).days} days)",
        "",
        f"Source: PostFast `/social-posts/analytics` for socialMediaId `{cfg.tt_account}`",
        "",
        "## Channel rollup",
        "",
    ]
    if have_data == 0:
        md.append("_No TikTok metrics returned by PostFast for this window yet._")
        md.append("")
        md.append("Common reasons:")
        md.append("- Posts are too new (PostFast typically refreshes TT metrics every few hours).")
        md.append("- Workspace plan is Starter (limited analytics) — upgrade for full counts.")
        md.append("- TikTok itself hasn't populated metrics yet (can take ~24h after publish).")
    else:
        md += [
            f"- **Posts with metrics:** {have_data} / {len(matches)}",
            f"- **Impressions (views):** {totals['impressions']:,}",
            f"- **Reach:** {totals['reach']:,}",
            f"- **Likes:** {totals['likes']:,}",
            f"- **Comments:** {totals['comments']:,}",
            f"- **Shares:** {totals['shares']:,}",
            f"- **Clicks:** {totals['clicks']:,}",
        ]
    md += ["", "## Per-video", ""]
    md += [
        "| Case | Match | Impressions | Reach | Likes | Comments | Shares | Clicks |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for case_id, m in sorted(matches.items()):
        md.append(render_case_row(case_id, m["info"], m.get("post"), m["confidence"]))
    md.append("")

    if unmatched_posts:
        md += [
            "## Unmatched PostFast posts",
            "",
            "_These TT posts were returned by PostFast but didn't match any tracker case "
            "within ±5 minutes. Likely posted outside the autonomous pipeline (manual upload, "
            "deleted case, or pre-pipeline) — or the tracker timestamp drift is wider than expected._",
            "",
            "| publishedAt | platformPostId | content (first 60c) |",
            "|---|---|---|",
        ]
        for p in unmatched_posts[:20]:
            pub = p.get("publishedAt", "?")
            ppid = p.get("platformPostId") or "_unpublished_"
            content = (p.get("content") or "").strip().replace("\n", " ")[:60]
            md.append(f"| {pub} | `{ppid}` | {content} |")
        md.append("")

    md += [
        "## How to read this report",
        "",
        "- **Impressions** is TikTok's view count.",
        "- **Reach** is unique viewers; for short-form `reach ≈ impressions` for low-velocity videos.",
        "- **No retention %** — TikTok doesn't expose per-video retention via API. "
        "Manual watch-through % still lives in `output/cross_post_status.json` (`tiktok_retention_pct`).",
        "- **Match = medium / no_match:** PostFast couldn't be matched 1:1 by timestamp+caption. "
        "If frequent, consider backfilling `platformPostId` into the tracker on upload.",
        "",
    ]

    # JSON dump for downstream tools (e.g. /suggest-tweaks)
    raw = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": {"start": window_start.isoformat(), "end": window_end.isoformat()},
        "source": "postfast",
        "tiktok_social_media_id": cfg.tt_account,
        "totals": totals if have_data else None,
        "videos": {
            case_id: {
                "posted_at": m["info"].get("tiktok"),
                "videos_dir": m["info"].get("videos_dir"),
                "match_confidence": m["confidence"],
                "platform_post_id": (m.get("post") or {}).get("platformPostId"),
                "postfast_post_id": (m.get("post") or {}).get("id"),
                "metrics": (m.get("post") or {}).get("latestMetric"),
                "tiktok_retention_pct": m["info"].get("tiktok_retention_pct"),
            }
            for case_id, m in matches.items()
        },
        "unmatched_postfast_posts": unmatched_posts,
    }
    return "\n".join(md), raw


# ---------------------------------------------------------------------------
# Auth probe
# ---------------------------------------------------------------------------


def check_auth(cfg: Config) -> int:
    if not cfg.api_key:
        print("✗ POSTFAST_API_KEY missing from .env")
        return 1
    status, body = _http_get_json(cfg, "/social-media/my-social-accounts")
    if status != 200:
        print(f"✗ /social-media/my-social-accounts HTTP {status}: {str(body)[:200]}")
        return 1
    accounts = body if isinstance(body, list) else []
    tt = [a for a in accounts if a.get("platform") == "TIKTOK"]
    if not tt:
        print("✗ No TikTok account connected in PostFast.")
        return 1
    print(f"✓ API key valid. {len(tt)} TikTok account(s) connected:")
    for a in tt:
        uname = a.get("platformUsername") or a.get("displayName") or "?"
        sm_id = a.get("id", "?")
        match = " (matches POSTFAST_TIKTOK_CHANNEL_ID)" if sm_id == cfg.tt_account else ""
        print(f"   @{uname}  id={sm_id}{match}")
    # Quick smoke-test of the analytics endpoint
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    posts, err = fetch_postfast_analytics(cfg, start, end)
    if err:
        print(f"⚠ /social-posts/analytics probe failed: {err}")
        print("  This may indicate the workspace is on a tier without analytics access.")
        return 1
    print(f"✓ Analytics endpoint OK — {len(posts)} TT post(s) in last 7 days.")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=str, default=None,
                        help="Single case_id to analyze (e.g. SY_01_S_lakecabin). Default: all.")
    parser.add_argument("--days", type=int, default=30,
                        help="Lookback window in days (default 30).")
    parser.add_argument("--check-auth", action="store_true",
                        help="Probe API key + analytics endpoint, then exit.")
    args = parser.parse_args()

    cfg = Config()

    if args.check_auth:
        return check_auth(cfg)

    cfg.assert_ready()

    tracker = load_tracker()
    target_cases = tt_posted_cases(tracker, args.case)
    if not target_cases:
        if args.case:
            sys.exit(f"[FATAL] case {args.case!r} not in tracker or not TT-posted.")
        sys.exit("[FATAL] No TT-posted cases in tracker. Cross-post something first.")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)

    print(f"Pulling PostFast TikTok analytics: {start.date()} → {end.date()} "
          f"({len(target_cases)} tracked case(s))…")
    posts, err = fetch_postfast_analytics(cfg, start, end)
    if err:
        sys.exit(f"[FATAL] PostFast analytics fetch failed: {err}")

    print(f"  Got {len(posts)} TT post(s) from PostFast in window.")

    matches: dict[str, dict] = {}
    matched_postfast_ids: set[str] = set()
    for case_id, info in target_cases.items():
        post, confidence = match_case_to_post(case_id, info, posts)
        matches[case_id] = {"info": info, "post": post, "confidence": confidence}
        if post:
            matched_postfast_ids.add(post.get("id", ""))

    unmatched = [p for p in posts if p.get("id", "") not in matched_postfast_ids]

    md, raw = render_report(start, end, matches, unmatched, cfg)

    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    md_path = ANALYTICS_DIR / f"report_{today}_tiktok.md"
    json_path = ANALYTICS_DIR / f"report_{today}_tiktok.json"
    atomic_write_text(md_path, md)
    atomic_write_text(json_path, json.dumps(raw, indent=2, default=str))

    n_with_metrics = sum(
        1 for m in matches.values()
        if (m.get("post") or {}).get("latestMetric")
    )
    print(f"\n✓ Wrote {md_path.relative_to(PROJECT_ROOT)}")
    print(f"✓ Wrote {json_path.relative_to(PROJECT_ROOT)}")
    print(f"\n  Matched: {sum(1 for m in matches.values() if m.get('post'))}/{len(matches)} "
          f"tracked cases. With metrics: {n_with_metrics}.")
    if unmatched:
        print(f"  Unmatched PostFast posts (not tied to a tracker case): {len(unmatched)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
