#!/usr/bin/env python3
"""Autonomous game research — finds trending/new games and creates game_queue entries.

Queries Steam's popular upcoming + new releases, scores candidates with Claude,
and auto-creates game_queue/GG_NN_<slug>.md files ready for the pipeline.

Usage:
    python scripts/research_games.py                    # find + score top 5
    python scripts/research_games.py --count 10         # find more candidates
    python scripts/research_games.py --dry-run          # score without writing files

Output:
    game_queue/GG_NN_<slug>.md for each approved candidate
    game_queue/_INDEX.md updated

Prerequisites:
    ANTHROPIC_API_KEY set in .env or environment
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GAME_QUEUE_DIR = PROJECT_ROOT / "game_queue"
INDEX_PATH = GAME_QUEUE_DIR / "_INDEX.md"

STEAM_SEARCH_URL = "https://store.steampowered.com/api/featuredcategories"
STEAM_APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"
STEAM_NEW_RELEASES = "https://store.steampowered.com/api/featured"

# For app list we use the public storefront API
STEAM_POPULAR_UPCOMING = "https://store.steampowered.com/search/results/?filter=popularcomingsoon&json=1&count=20"
STEAM_TOP_SELLERS = "https://store.steampowered.com/search/results/?filter=topsellers&json=1&count=20"
STEAM_NEW_RELEASES_URL = "https://store.steampowered.com/search/results/?filter=newreleases&json=1&count=20"

HEADERS = {"Accept-Language": "en-US,en;q=0.9"}


# ---------------------------------------------------------------------------
# Steam data fetching
# ---------------------------------------------------------------------------

def fetch_steam_list(url: str) -> list[dict]:
    """Fetch a list of games from a Steam storefront search endpoint."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])
    except Exception as e:
        print(f"  ⚠  Steam fetch failed: {e}", file=sys.stderr)
        return []


def fetch_app_details(appid: int) -> dict:
    """Fetch full app details for a single Steam App ID."""
    try:
        resp = requests.get(
            STEAM_APPDETAILS_URL,
            params={"appids": appid, "cc": "us", "l": "en"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        entry = data.get(str(appid), {})
        if entry.get("success"):
            return entry.get("data", {})
    except Exception:
        pass
    return {}


def collect_candidates(count: int = 20) -> list[dict]:
    """Pull candidates from Steam upcoming, new releases, and top sellers."""
    candidates = {}

    for label, url in [
        ("upcoming", STEAM_POPULAR_UPCOMING),
        ("new", STEAM_NEW_RELEASES_URL),
        ("sellers", STEAM_TOP_SELLERS),
    ]:
        items = fetch_steam_list(url)
        for item in items:
            appid = item.get("id") or item.get("appid")
            if not appid:
                continue
            appid = int(appid)
            if appid not in candidates:
                candidates[appid] = {
                    "appid": appid,
                    "name": item.get("name", ""),
                    "source": label,
                }

    # Deduplicate and limit
    results = list(candidates.values())[:count]
    return results


def enrich_with_details(candidates: list[dict]) -> list[dict]:
    """Add genre, description, and trailer availability to each candidate."""
    enriched = []
    for c in candidates:
        time.sleep(0.3)  # be polite to Steam API
        details = fetch_app_details(c["appid"])
        if not details:
            continue

        # Filter: games only, not DLC or software
        if details.get("type") not in ("game", "early access"):
            app_type = details.get("type", "unknown")
            if app_type not in ("game",):
                continue

        genres = [g.get("description", "") for g in details.get("genres", [])]
        has_trailer = bool(details.get("movies"))

        c.update({
            "name": details.get("name", c["name"]),
            "short_description": details.get("short_description", ""),
            "genres": genres,
            "release_date": details.get("release_date", {}).get("date", "TBD"),
            "developers": details.get("developers", []),
            "publishers": details.get("publishers", []),
            "price": details.get("price_overview", {}).get("final_formatted", "Unknown"),
            "platforms": [k for k, v in details.get("platforms", {}).items() if v],
            "has_trailer": has_trailer,
            "header_image": details.get("header_image", ""),
        })
        enriched.append(c)

    return enriched


# ---------------------------------------------------------------------------
# Claude scoring
# ---------------------------------------------------------------------------

SCORING_PROMPT = """You are a YouTube Shorts content strategist for a gaming channel.
Evaluate each game candidate for its potential as a 40-50 second YouTube Short.

Score each game 1-10 on these criteria:
1. Hook strength — is there one counterintuitive or visually striking fact that stops a scroll?
2. Visual quality — will the trailer footage look compelling portrait-cropped to 9:16?
3. Audience breadth — is the genre/franchise big enough to drive views on a new channel?
4. Explainability — can the core concept be communicated clearly in 120-140 words?
5. Timing — is this just launched, about to launch, or trending right now?

For each game, output a JSON object with:
{
  "name": "game name",
  "score": 7,
  "hook": "one sentence — the most striking/counterintuitive thing about this game",
  "four_beat_arc": {
    "what_is_it": "one sentence premise",
    "gameplay_loop": "what you do moment-to-moment",
    "standout": "the one thing separating it from everything in its genre",
    "cta": "platform + release date action"
  },
  "youtube_trailer_search": "search query to find the official trailer on YouTube",
  "skip_reason": null
}

If a game scores below 5 or is clearly unsuitable (DLC, asset flip, adult-only), set "skip_reason" to a brief explanation and omit the other fields.

Respond with a JSON array only. No markdown, no explanation."""


def score_with_claude(candidates: list[dict], api_key: str) -> list[dict]:
    """Use Claude to score and generate hooks + arcs for each candidate."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    # Build candidate list for Claude
    candidate_text = json.dumps([{
        "name": c["name"],
        "genres": c.get("genres", []),
        "short_description": c.get("short_description", ""),
        "release_date": c.get("release_date", "TBD"),
        "developers": c.get("developers", []),
        "platforms": c.get("platforms", []),
        "source": c.get("source", ""),
    } for c in candidates], indent=2)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=SCORING_PROMPT,
        messages=[{"role": "user", "content": f"Score these Steam game candidates:\n\n{candidate_text}"}],
    )

    raw = response.content[0].text.strip()
    # Strip any accidental markdown fences
    raw = re.sub(r"^```[^\n]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)

    try:
        scored = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ⚠  Claude returned invalid JSON: {e}", file=sys.stderr)
        print(f"  Raw output: {raw[:500]}", file=sys.stderr)
        return []

    # Merge scored data back with candidate metadata
    scored_map = {s["name"]: s for s in scored if isinstance(s, dict)}
    results = []
    for c in candidates:
        s = scored_map.get(c["name"])
        if not s:
            continue
        if s.get("skip_reason"):
            continue
        score = s.get("score", 0)
        if score < 5:
            continue
        results.append({**c, **s})

    # Sort by score descending
    results.sort(key=lambda x: -x.get("score", 0))
    return results


# ---------------------------------------------------------------------------
# Queue entry creation
# ---------------------------------------------------------------------------

def next_queue_number() -> int:
    """Find the next available GG_NN number."""
    existing = list(GAME_QUEUE_DIR.glob("GG_[0-9][0-9]_*.md"))
    if not existing:
        return 1
    nums = []
    for p in existing:
        m = re.match(r"GG_(\d+)_", p.name)
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1 if nums else 1


def slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9\s]", "", slug)
    slug = re.sub(r"\s+", "_", slug.strip())
    return slug[:40]


def write_queue_entry(candidate: dict, queue_num: int) -> Path:
    """Write a game_queue/GG_NN_<slug>.md file."""
    arc = candidate.get("four_beat_arc", {})
    slug = slugify(candidate["name"])
    game_id = f"GG_{queue_num:02d}_{slug}"
    filename = GAME_QUEUE_DIR / f"{game_id}.md"

    platforms_str = " / ".join(p.title() for p in candidate.get("platforms", ["PC"]))
    developers = ", ".join(candidate.get("developers", ["Unknown"]))
    publishers = ", ".join(candidate.get("publishers", [developers]))

    youtube_search = candidate.get("youtube_trailer_search", f"{candidate['name']} official trailer")

    content = f"""# {game_id} — {candidate['name']}

**Status:** QUEUED
**Score:** {candidate.get('score', 0)}/10
**Platform(s):** {platforms_str}
**Steam App ID:** {candidate['appid']}
**YouTube Trailer URL:** search: {youtube_search}
**Developer:** {developers}
**Publisher:** {publishers}
**Genre:** {', '.join(candidate.get('genres', ['Unknown']))}
**Release:** {candidate.get('release_date', 'TBD')}
**ESRB/PEGI:** TBD

## Hook
{candidate.get('hook', '')}

## 4-beat arc

- **What is it:** {arc.get('what_is_it', '')}
- **Gameplay loop:** {arc.get('gameplay_loop', '')}
- **Standout:** {arc.get('standout', '')}
- **CTA:** {arc.get('cta', '')}

## Visual notes
- Auto-researched candidate — review trailer before clip selection
- Portrait crop: prefer action/gameplay sequences, avoid developer talking heads
"""

    filename.write_text(content)
    return filename


def update_index(entries: list[tuple[str, dict]]) -> None:
    """Append new entries to game_queue/_INDEX.md."""
    content = INDEX_PATH.read_text()
    new_rows = []
    for game_id, c in entries:
        name = c["name"]
        status = "QUEUED"
        release = c.get("release_date", "TBD")
        platform = "/".join(p[:2].upper() for p in c.get("platforms", ["PC"])[:2])
        score = f"{c.get('score', 0)}/10"
        source = c.get("source", "")
        new_rows.append(f"| {game_id} | {name} | {status} | {release} | {platform} | {score} | Auto-researched ({source}) |")

    # Append rows before the closing content
    new_rows_text = "\n".join(new_rows)
    # Insert before the "## How to add" section
    if "## How to add" in content:
        content = content.replace("## How to add", new_rows_text + "\n\n## How to add")
    else:
        content = content.rstrip() + "\n" + new_rows_text + "\n"

    INDEX_PATH.write_text(content)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Research trending games and create game_queue entries.")
    parser.add_argument("--count", type=int, default=20, help="Number of Steam candidates to fetch (default 20)")
    parser.add_argument("--top", type=int, default=3, help="Number of top-scored entries to write (default 3)")
    parser.add_argument("--dry-run", action="store_true", help="Score without writing queue files")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY not set.\nAdd it to .env or: export ANTHROPIC_API_KEY=your_key")

    print("── Game Research ──")
    print(f"  Fetching {args.count} Steam candidates…")
    candidates = collect_candidates(args.count)
    print(f"  Found {len(candidates)} candidates")

    print("  Fetching app details…")
    enriched = enrich_with_details(candidates)
    print(f"  Enriched {len(enriched)} games with details")
    games_with_trailers = [c for c in enriched if c.get("has_trailer")]
    print(f"  {len(games_with_trailers)} have trailers available")

    print(f"  Scoring with Claude…")
    scored = score_with_claude(enriched, api_key)
    print(f"  {len(scored)} games scored ≥5/10")

    top = scored[:args.top]
    print(f"\n  Top {len(top)} candidates:")
    for c in top:
        print(f"    [{c.get('score', 0)}/10] {c['name']} — {c.get('hook', '')[:80]}")

    if args.dry_run:
        print("\n  [dry-run] No files written.")
        return

    GAME_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for c in top:
        queue_num = next_queue_number()
        path = write_queue_entry(c, queue_num)
        game_id = path.stem
        written.append((game_id, c))
        print(f"  ✓ Wrote {path.relative_to(PROJECT_ROOT)}")

    if written:
        update_index(written)
        print(f"  ✓ Updated {INDEX_PATH.relative_to(PROJECT_ROOT)}")

    print(f"\n  Next: run the pipeline for any entry above")
    print(f"  python scripts/game_orchestrator.py --game-id <id>")


if __name__ == "__main__":
    main()
