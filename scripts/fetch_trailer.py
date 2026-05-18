#!/usr/bin/env python3
"""Download a game trailer from Steam CDN or YouTube (yt-dlp fallback).

Usage:
    python scripts/fetch_trailer.py --steam 2322010 --game-id GG_01_elden_ring
    python scripts/fetch_trailer.py --youtube https://youtu.be/XYZ --game-id GG_01_elden_ring
    python scripts/fetch_trailer.py --steam 2322010 --game-id GG_01_elden_ring --dry-run

Strategy:
    1. Try Steam API (free, no rate limit, official .mp4 link)
    2. Fall back to yt-dlp if Steam has no trailer or --youtube is specified

Output:
    output/scripts/<game_id>/trailer_raw.mp4
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "output" / "scripts"

STEAM_API = "https://store.steampowered.com/api/appdetails"
STEAM_CDN_TIMEOUT = 120  # seconds for large trailer download


# ---------------------------------------------------------------------------
# Steam fetcher
# ---------------------------------------------------------------------------

def _get_with_retry(url: str, *, params: dict | None = None, timeout: int = 15,
                    max_attempts: int = 3) -> requests.Response:
    """GET with exponential backoff on 5xx. Re-raises non-transient errors immediately."""
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            if resp.status_code < 500:
                resp.raise_for_status()
                return resp
            last_exc = requests.HTTPError(f"{resp.status_code} from {url}")
        except (requests.ConnectionError, requests.Timeout) as e:
            last_exc = e
        wait = 2 ** attempt
        print(f"  Steam API attempt {attempt+1}/{max_attempts} failed; retrying in {wait}s…", file=sys.stderr)
        time.sleep(wait)
    raise last_exc if last_exc else RuntimeError("Steam API retry exhausted")


def fetch_steam_trailer(appid: str, game_id: str, dry_run: bool = False) -> Path:
    """Download the highest-quality MP4 trailer from Steam CDN."""
    print(f"  Querying Steam API for appid={appid}…")
    resp = _get_with_retry(STEAM_API, params={"appids": appid, "cc": "us", "l": "en"}, timeout=15)
    data = resp.json()

    app_data = data.get(str(appid), {})
    if not app_data.get("success"):
        raise ValueError(
            f"Steam API returned success=false for appid={appid}.\n"
            f"Check the app ID at store.steampowered.com/app/{appid}/"
        )

    details = app_data.get("data", {})
    game_name = details.get("name", "Unknown Game")
    movies = details.get("movies", [])

    if not movies:
        raise ValueError(
            f"'{game_name}' (appid={appid}) has no trailers on Steam.\n"
            "Use --youtube to provide a trailer URL instead."
        )

    # Pick the highest quality mp4 from the first trailer
    movie = movies[0]
    mp4_sources = movie.get("mp4", {})
    # Prefer 'max' quality, fall back to '480'
    trailer_url = mp4_sources.get("max") or mp4_sources.get("480")

    if not trailer_url:
        # Try webm as last resort
        webm_sources = movie.get("webm", {})
        trailer_url = webm_sources.get("max") or webm_sources.get("480")

    if not trailer_url:
        raise ValueError(
            f"No downloadable trailer URL found for '{game_name}' (appid={appid}).\n"
            "Steam may serve HLS-only trailers for this title. Use --youtube instead."
        )

    print(f"  Game:    {game_name}")
    print(f"  Trailer: {movie.get('name', 'Trailer')}")
    print(f"  URL:     {trailer_url}")

    if dry_run:
        print("  [dry-run] Would download trailer. No file written.")
        return SCRIPTS_DIR / game_id / "trailer_raw.mp4"

    out_dir = SCRIPTS_DIR / game_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "trailer_raw.mp4"

    print(f"  Downloading…")
    _download_with_progress(trailer_url, out_path)
    return out_path


def _download_with_progress(url: str, dest: Path) -> None:
    """Stream-download to dest.part, then os.replace to dest on success.

    Prevents the failure mode where a network drop leaves a truncated
    trailer_raw.mp4 — on next run the existence check skips re-download
    and the pipeline produces broken clips.
    """
    part = dest.with_suffix(dest.suffix + ".part")
    try:
        with requests.get(url, stream=True, timeout=STEAM_CDN_TIMEOUT) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(part, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = int(downloaded / total * 100)
                        print(f"\r    {pct}% ({downloaded // (1024*1024)} MB / {total // (1024*1024)} MB)", end="", flush=True)
        print()  # newline after progress

        # Verify expected length if content-length was provided
        if total and downloaded < total:
            raise RuntimeError(f"Truncated download: {downloaded} of {total} bytes")
        os.replace(part, dest)
    except Exception:
        # Leave the .part behind for debugging but don't promote
        raise


# ---------------------------------------------------------------------------
# yt-dlp fetcher
# ---------------------------------------------------------------------------

def fetch_youtube_trailer(url: str, game_id: str, dry_run: bool = False) -> Path:
    """Download trailer from YouTube using yt-dlp."""
    try:
        import yt_dlp
    except ImportError:
        sys.exit(
            "ERROR: yt-dlp is not installed.\n"
            "Run: pip install yt-dlp"
        )

    out_dir = SCRIPTS_DIR / game_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_template = str(out_dir / "trailer_raw.%(ext)s")

    ydl_opts = {
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]",
        "outtmpl": out_template,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }

    if dry_run:
        print(f"  [dry-run] Would download from: {url}")
        print(f"  [dry-run] Output would be: {out_dir / 'trailer_raw.mp4'}")
        return out_dir / "trailer_raw.mp4"

    print(f"  Downloading via yt-dlp: {url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "Unknown")
        duration = info.get("duration", 0)
        print(f"  Downloaded: '{title}' ({duration}s)")

    # yt-dlp may write .mp4 or .mkv depending on format availability
    out_path = out_dir / "trailer_raw.mp4"
    if not out_path.exists():
        # Check for other extensions
        alternatives = list(out_dir.glob("trailer_raw.*"))
        if alternatives:
            alt = alternatives[0]
            alt.rename(out_path)
        else:
            raise FileNotFoundError(f"yt-dlp completed but no trailer_raw.* found in {out_dir}")

    return out_path


# ---------------------------------------------------------------------------
# Duration check
# ---------------------------------------------------------------------------

def check_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        return 0.0
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch a game trailer from Steam or YouTube.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--steam", metavar="APPID", help="Steam App ID (numeric)")
    src.add_argument("--youtube", metavar="URL", help="YouTube trailer URL")
    parser.add_argument("--game-id", required=True, metavar="ID",
                        help="Game ID for output directory (e.g. GG_01_elden_ring)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done, no download")
    args = parser.parse_args()

    print(f"── Fetch Trailer: {args.game_id} ──")

    try:
        if args.steam:
            out_path = fetch_steam_trailer(args.steam, args.game_id, args.dry_run)
        else:
            out_path = fetch_youtube_trailer(args.youtube, args.game_id, args.dry_run)
    except Exception as e:
        # If Steam fails and a YouTube URL wasn't provided, surface clearly
        sys.exit(f"ERROR: {e}")

    if not args.dry_run and out_path.exists():
        size_mb = out_path.stat().st_size / (1024 * 1024)
        duration = check_duration(out_path)
        print(f"  ✓ Saved:    {out_path.relative_to(PROJECT_ROOT)}")
        print(f"  ✓ Size:     {size_mb:.1f} MB")
        if duration:
            print(f"  ✓ Duration: {duration:.1f}s")
        print(f"\n  Next: python scripts/select_clips.py --game-id {args.game_id} --auto")


if __name__ == "__main__":
    main()
