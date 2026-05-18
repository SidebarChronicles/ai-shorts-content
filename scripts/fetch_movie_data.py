#!/usr/bin/env python3
"""TMDB API wrapper — fetch movie metadata + official trailer URL.

Replaces the manual "find the movie on TMDB and copy the trailer link" step
for the movies vertical. Given a movie title or TMDB ID, returns:
  - Movie details (release date, runtime, MPAA rating, studio, plot)
  - Official trailer YouTube URL (best match: type=Trailer, official=true,
    site=YouTube; falls back to teaser if no trailer exists)

Usage:
    python scripts/fetch_movie_data.py --search "Wicked Part 2"
    python scripts/fetch_movie_data.py --tmdb-id 1107979
    python scripts/fetch_movie_data.py --search "Avatar 3" --json

Environment:
    TMDB_API_KEY (required) — get one free at themoviedb.org/settings/api
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

TMDB_BASE = "https://api.themoviedb.org/3"


class TMDBError(Exception):
    pass


# ---------------------------------------------------------------------------
# Core queries
# ---------------------------------------------------------------------------

def _get(path: str, api_key: str, **params) -> dict:
    """Authenticated TMDB v3 GET."""
    params["api_key"] = api_key
    url = f"{TMDB_BASE}{path}"
    resp = requests.get(url, params=params, timeout=15)
    if resp.status_code != 200:
        raise TMDBError(f"TMDB {path} returned {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def search_movie(query: str, api_key: str, year: Optional[int] = None) -> list[dict]:
    """Search movies by title. Returns a list of matches (most popular first)."""
    params = {"query": query, "include_adult": "false", "language": "en-US"}
    if year is not None:
        params["year"] = str(year)
    data = _get("/search/movie", api_key, **params)
    results = data.get("results", []) or []
    # Sort by popularity desc — TMDB already does this but be defensive
    results.sort(key=lambda r: r.get("popularity", 0), reverse=True)
    return results


def get_movie_details(tmdb_id: int, api_key: str) -> dict:
    """Full movie record incl. genres, production companies, release dates."""
    # append_to_response saves us a round-trip
    return _get(
        f"/movie/{tmdb_id}",
        api_key,
        append_to_response="videos,release_dates,credits",
        language="en-US",
    )


def find_official_trailer(movie: dict) -> Optional[dict]:
    """From a movie record (with videos appended), pick the best trailer.

    Priority:
      1. Official trailer on YouTube with type='Trailer'
      2. Official teaser on YouTube
      3. Any trailer on YouTube
      4. Any teaser on YouTube
    Returns the video dict or None.
    """
    videos = (movie.get("videos") or {}).get("results", []) or []
    yt = [v for v in videos if v.get("site") == "YouTube"]

    def pick(predicate):
        for v in yt:
            if predicate(v):
                return v
        return None

    return (
        pick(lambda v: v.get("official") and v.get("type") == "Trailer")
        or pick(lambda v: v.get("official") and v.get("type") == "Teaser")
        or pick(lambda v: v.get("type") == "Trailer")
        or pick(lambda v: v.get("type") == "Teaser")
    )


def extract_us_rating(movie: dict) -> Optional[str]:
    """Pull the US theatrical MPAA rating from release_dates."""
    rd = (movie.get("release_dates") or {}).get("results", []) or []
    for entry in rd:
        if entry.get("iso_3166_1") == "US":
            for r in entry.get("release_dates", []) or []:
                cert = r.get("certification", "")
                if cert:
                    return cert
    return None


def extract_us_release_date(movie: dict) -> Optional[str]:
    """Pull the earliest US theatrical (type=3) release date if available."""
    rd = (movie.get("release_dates") or {}).get("results", []) or []
    for entry in rd:
        if entry.get("iso_3166_1") == "US":
            for r in entry.get("release_dates", []) or []:
                # type 3 = Theatrical
                if r.get("type") == 3:
                    return (r.get("release_date") or "")[:10]
    # Fallback: top-level release_date
    return movie.get("release_date")


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def summarize_movie(movie: dict) -> dict:
    """Project a TMDB movie record into the fields we care about for queue entries."""
    trailer = find_official_trailer(movie)
    yt_url = None
    if trailer and trailer.get("key"):
        yt_url = f"https://www.youtube.com/watch?v={trailer['key']}"

    studios = [c["name"] for c in (movie.get("production_companies") or [])[:3]]
    genres = [g["name"] for g in (movie.get("genres") or [])]
    director = next(
        (m["name"] for m in (movie.get("credits") or {}).get("crew", []) if m.get("job") == "Director"),
        None,
    )
    main_cast = [c["name"] for c in (movie.get("credits") or {}).get("cast", [])[:3]]

    return {
        "tmdb_id": movie.get("id"),
        "title": movie.get("title"),
        "original_title": movie.get("original_title"),
        "release_date": extract_us_release_date(movie),
        "runtime": movie.get("runtime"),
        "mpaa": extract_us_rating(movie),
        "genres": genres,
        "studios": studios,
        "director": director,
        "main_cast": main_cast,
        "tagline": movie.get("tagline"),
        "overview": movie.get("overview"),
        "poster_path": movie.get("poster_path"),
        "youtube_trailer_url": yt_url,
        "trailer_name": (trailer or {}).get("name"),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--search", help="Movie title to search")
    group.add_argument("--tmdb-id", type=int, help="Direct TMDB movie ID")
    parser.add_argument("--year", type=int, help="Year hint for search")
    parser.add_argument("--json", action="store_true", help="Print full JSON (default: human summary)")
    args = parser.parse_args()

    api_key = os.environ.get("TMDB_API_KEY", "")
    if not api_key:
        sys.exit("ERROR: TMDB_API_KEY not set in .env. Get one at themoviedb.org/settings/api")

    if args.search:
        results = search_movie(args.search, api_key, year=args.year)
        if not results:
            sys.exit(f"No movies matched search {args.search!r}")
        tmdb_id = results[0]["id"]
        if not args.json:
            print(f"Picked top result: {results[0].get('title')} ({results[0].get('release_date','?')})")
            if len(results) > 1:
                others = ", ".join(f"{r.get('title','?')} ({r.get('release_date','?')[:4]})" for r in results[1:4])
                print(f"Other matches: {others}")
    else:
        tmdb_id = args.tmdb_id

    movie = get_movie_details(tmdb_id, api_key)
    summary = summarize_movie(movie)

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    print(f"\n── {summary['title']} ──")
    print(f"  TMDB ID:        {summary['tmdb_id']}")
    print(f"  Release:        {summary['release_date'] or '?'}")
    print(f"  Runtime:        {summary['runtime']} min" if summary['runtime'] else "  Runtime:        ?")
    print(f"  MPAA:           {summary['mpaa'] or '?'}")
    print(f"  Director:       {summary['director'] or '?'}")
    print(f"  Cast:           {', '.join(summary['main_cast']) or '?'}")
    print(f"  Studio(s):      {', '.join(summary['studios']) or '?'}")
    print(f"  Genre(s):       {', '.join(summary['genres']) or '?'}")
    print(f"  Trailer:        {summary['youtube_trailer_url'] or '(none found)'}")
    if summary['tagline']:
        print(f"  Tagline:        {summary['tagline']}")
    if summary['overview']:
        print(f"\n  Overview:       {summary['overview'][:300]}{'...' if len(summary['overview']) > 300 else ''}")


if __name__ == "__main__":
    main()
