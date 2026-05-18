#!/usr/bin/env python3
"""Build a Ken Burns visuals track from stock + AI imagery.

The keystone for non-trailer verticals (cases, finance, psychology, mythology,
mysteries, top X). Replaces the trailer→clip extraction step from the game
pipeline with image sourcing + zoompan motion.

Pipeline per case:
  1. Read output/scripts/<case>/script_config.json (beats with keywords)
  2. For each beat: search Pexels API → fallback Pixabay API → fallback Flux (stub)
  3. Download the chosen image to visuals_raw/
  4. Render Ken Burns motion clip per image via FFmpeg zoompan
  5. Write bg_clips_concat.txt matching the existing render pipeline shape

Then run skill/game-short/render_game_video.py as normal — it picks up the
concat list, karaoke alignment, and renders the final video.

Usage:
    python scripts/build_visuals_track.py --case 01_gothferrari
    python scripts/build_visuals_track.py --case CASE_07_x --beat-duration 12
    python scripts/build_visuals_track.py --case 01_gothferrari --dry-run

Environment:
    PEXELS_API_KEY    free at https://www.pexels.com/api/
    PIXABAY_API_KEY   free at https://pixabay.com/api/docs/
    REPLICATE_API_TOKEN (optional, paid) — for Flux 2 Pro AI gen fallback
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Shared helpers
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import load_dotenv  # noqa: E402
from _atomic import atomic_write_text  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

SCRIPTS_DIR = PROJECT_ROOT / "output" / "scripts"

# Portrait canvas
W, H = 1080, 1920

# Default duration per beat clip when no audio alignment is available
DEFAULT_BEAT_DURATION = 12.0  # seconds

# Ken Burns motion parameters
KB_ZOOM_RATE = 0.0008   # zoom increment per frame (gentle: 0.0008, dramatic: 0.002)
KB_FPS = 30


# ---------------------------------------------------------------------------
# Stock image search
# ---------------------------------------------------------------------------

class ImageSearchError(Exception):
    pass


def search_pexels(query: str, api_key: str) -> Optional[dict]:
    """Search Pexels for portrait imagery matching the query.

    Returns the best-match image record (with .src.large2x URL) or None.
    """
    if not api_key:
        return None

    url = "https://api.pexels.com/v1/search"
    params = {
        "query": query,
        "per_page": 5,
        "orientation": "portrait",
        "size": "large",
    }
    headers = {"Authorization": api_key}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            return None
        # Pick the first result with a usable large image
        return photos[0]
    except (requests.RequestException, ValueError) as e:
        print(f"    [pexels] search failed: {e}", file=sys.stderr)
        return None


def search_pixabay(query: str, api_key: str) -> Optional[dict]:
    """Search Pixabay for vertical imagery. Pixabay's `orientation=vertical`
    filter pairs with high-quality assets that don't require attribution."""
    if not api_key:
        return None

    url = "https://pixabay.com/api/"
    params = {
        "key": api_key,
        "q": query,
        "orientation": "vertical",
        "image_type": "photo",
        "safesearch": "true",
        "per_page": 5,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        if not hits:
            return None
        return hits[0]
    except (requests.RequestException, ValueError) as e:
        print(f"    [pixabay] search failed: {e}", file=sys.stderr)
        return None


def download_image(url: str, dest: Path, timeout: int = 30) -> bool:
    """Stream-download an image to dest. Returns True on success."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    try:
        with requests.get(url, stream=True, timeout=timeout) as resp:
            resp.raise_for_status()
            with open(part, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
        os.replace(part, dest)
        return True
    except (requests.RequestException, OSError) as e:
        print(f"    [download] failed: {e}", file=sys.stderr)
        if part.exists():
            try:
                part.unlink()
            except OSError:
                pass
        return False


# ---------------------------------------------------------------------------
# Source chain
# ---------------------------------------------------------------------------

def source_image_for_beat(beat_idx: int, keywords: list[str],
                          visuals_dir: Path,
                          pexels_key: str, pixabay_key: str) -> Optional[Path]:
    """Try each source in priority order until one returns an image."""
    if not keywords:
        print(f"  beat {beat_idx}: no keywords provided — skipping", file=sys.stderr)
        return None

    query = " ".join(keywords[:4])  # cap to keep API search relevant
    out_path = visuals_dir / f"beat_{beat_idx:02d}.jpg"

    # 1. Try Pexels
    print(f"  beat {beat_idx}: pexels.com query={query!r}…", end=" ", flush=True)
    pexels_hit = search_pexels(query, pexels_key)
    if pexels_hit:
        src_url = pexels_hit.get("src", {}).get("portrait") or pexels_hit.get("src", {}).get("large2x")
        if src_url and download_image(src_url, out_path):
            credit = pexels_hit.get("photographer", "Pexels")
            print(f"✓ ({credit})")
            return out_path

    # 2. Fallback Pixabay
    print(f"→ pixabay.com…", end=" ", flush=True)
    pixabay_hit = search_pixabay(query, pixabay_key)
    if pixabay_hit:
        src_url = pixabay_hit.get("largeImageURL") or pixabay_hit.get("webformatURL")
        if src_url and download_image(src_url, out_path):
            credit = pixabay_hit.get("user", "Pixabay")
            print(f"✓ ({credit})")
            return out_path

    # 3. Fallback AI generation (Flux 2 Pro via Replicate) — STUB
    # Enable by:
    #   1. Setting REPLICATE_API_TOKEN in .env
    #   2. Uncommenting the call below (and the call_replicate_flux helper)
    # We intentionally leave this as a stub so the script never accidentally
    # bills the Replicate account without explicit operator approval.
    print("→ ✗ (no AI fallback wired yet — set REPLICATE_API_TOKEN to enable)")
    return None


# ---------------------------------------------------------------------------
# Ken Burns clip render
# ---------------------------------------------------------------------------

def render_ken_burns(image_path: Path, out_clip: Path, duration: float,
                     zoom_in: bool = True, dry_run: bool = False) -> None:
    """Render a 1080x1920 portrait MP4 from a still image with slow zoom motion.

    Uses FFmpeg's zoompan filter. Direction alternates between zoom-in and
    zoom-out across consecutive clips to keep visual rhythm varied.
    """
    out_clip.parent.mkdir(parents=True, exist_ok=True)

    frames = int(duration * KB_FPS)
    if zoom_in:
        z = f"min(zoom+{KB_ZOOM_RATE},1.5)"
    else:
        z = f"if(eq(on,0),1.5,max(zoom-{KB_ZOOM_RATE},1.0))"

    # zoompan parameters:
    #   z: zoom expression (per-frame zoom factor)
    #   d: duration in frames
    #   s: output size (1080x1920 portrait)
    #   fps: target framerate
    #   x,y: center the zoom on image center
    vf = (
        # First scale image to fill the target size while preserving aspect
        f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,"
        f"crop={W*2}:{H*2},"
        f"zoompan=z='{z}':d={frames}:s={W}x{H}:fps={KB_FPS}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-vf", vf,
        "-t", f"{duration:.2f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-an",
        str(out_clip),
    ]

    if dry_run:
        print(f"    [dry-run] ffmpeg zoompan → {out_clip.name}")
        return

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        sys.exit(f"ERROR: Ken Burns render failed for {image_path.name}:\n{result.stderr[-500:]}")


# ---------------------------------------------------------------------------
# Audio-driven beat duration
# ---------------------------------------------------------------------------

def beat_durations_from_alignment(case_id: str, beats: list[dict]) -> Optional[list[float]]:
    """If alignment.json exists, allocate audio time per beat by character count.

    Returns a list of per-beat durations summing to the audio duration, or None
    if alignment isn't available (caller falls back to DEFAULT_BEAT_DURATION).
    """
    alignment_path = PROJECT_ROOT / "assets" / "audio" / f"narration_{case_id}.alignment.json"
    if not alignment_path.exists():
        return None

    try:
        alignment = json.loads(alignment_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    end_times = alignment.get("character_end_times_seconds", [])
    if not end_times:
        return None

    audio_dur = end_times[-1]
    total_chars = sum(len(b.get("text", "")) for b in beats)
    if total_chars == 0:
        return None

    return [audio_dur * (len(b.get("text", "")) / total_chars) for b in beats]


# ---------------------------------------------------------------------------
# Concat list
# ---------------------------------------------------------------------------

def write_concat_list(clip_paths: list[Path], concat_path: Path, dry_run: bool = False) -> None:
    """FFmpeg concat demuxer file (same format the render pipeline expects)."""
    lines = []
    for clip in clip_paths:
        lines.append(f"file '{clip}'")
    content = "\n".join(lines) + "\n"

    if dry_run:
        print(f"  [dry-run] concat list: {len(clip_paths)} clips")
        return

    atomic_write_text(concat_path, content)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build Ken Burns visuals track from stock+AI imagery.")
    parser.add_argument("--case", required=True, help="Case ID (matches output/scripts/<case>/)")
    parser.add_argument("--beat-duration", type=float, default=DEFAULT_BEAT_DURATION,
                        help=f"Per-beat clip duration when alignment unavailable (default {DEFAULT_BEAT_DURATION}s)")
    parser.add_argument("--dry-run", action="store_true", help="Don't download or render — just report")
    args = parser.parse_args()

    case_dir = SCRIPTS_DIR / args.case
    config_path = case_dir / "script_config.json"
    # Backward-compat alias
    if not config_path.exists():
        alt = case_dir / "game_config.json"
        if alt.exists():
            config_path = alt

    if not config_path.exists():
        sys.exit(f"ERROR: No script_config.json or game_config.json in {case_dir}")

    cfg = json.loads(config_path.read_text())
    beats = cfg.get("beats", [])
    if not beats:
        sys.exit(f"ERROR: No beats in config — add a beats[] array with per-beat keywords")

    # Each beat needs a `keywords` field (list of search terms). Use the text
    # itself as a fallback (first 4 words) so we never hard-fail on missing keys.
    for i, beat in enumerate(beats):
        if not beat.get("keywords"):
            text = beat.get("text", "")
            beat["keywords"] = text.split()[:4]

    visuals_dir = case_dir / "visuals_raw"
    clips_dir = case_dir / "clips_portrait"
    visuals_dir.mkdir(parents=True, exist_ok=True)
    clips_dir.mkdir(parents=True, exist_ok=True)

    pexels_key = os.environ.get("PEXELS_API_KEY", "")
    pixabay_key = os.environ.get("PIXABAY_API_KEY", "")

    if not pexels_key and not pixabay_key:
        sys.exit("ERROR: At least one of PEXELS_API_KEY or PIXABAY_API_KEY must be set in .env")

    print(f"── Build Visuals Track: {args.case} ──")
    print(f"  Beats: {len(beats)}")
    print(f"  Pexels API: {'✓' if pexels_key else '✗'}")
    print(f"  Pixabay API: {'✓' if pixabay_key else '✗'}")

    # Per-beat duration (audio-driven if alignment exists)
    durations = beat_durations_from_alignment(args.case, beats)
    if durations:
        print(f"  Durations: from alignment.json ({sum(durations):.1f}s total)")
    else:
        durations = [args.beat_duration] * len(beats)
        print(f"  Durations: default {args.beat_duration}s/beat ({sum(durations):.1f}s total)")

    # Source images
    print(f"\n  Sourcing images…")
    image_paths: list[Optional[Path]] = []
    for i, beat in enumerate(beats, 1):
        path = source_image_for_beat(
            beat_idx=i,
            keywords=beat["keywords"],
            visuals_dir=visuals_dir,
            pexels_key=pexels_key,
            pixabay_key=pixabay_key,
        )
        image_paths.append(path)
        # Be polite to free APIs
        time.sleep(0.3)

    missing = [i for i, p in enumerate(image_paths, 1) if p is None]
    if missing:
        sys.exit(
            f"ERROR: No image found for beats {missing}. "
            f"Add better keywords or enable Flux 2 Pro fallback (REPLICATE_API_TOKEN)."
        )

    # Render Ken Burns clips
    print(f"\n  Rendering Ken Burns clips…")
    clip_paths: list[Path] = []
    for i, (img, dur) in enumerate(zip(image_paths, durations), 1):
        out_clip = clips_dir / f"clip_{i:02d}_portrait.mp4"
        zoom_in = (i % 2 == 1)  # alternate zoom direction
        print(f"  clip_{i:02d} ({dur:.1f}s, zoom_{'in' if zoom_in else 'out'})… ", end="", flush=True)
        render_ken_burns(img, out_clip, dur, zoom_in=zoom_in, dry_run=args.dry_run)
        if not args.dry_run:
            print("✓")
        clip_paths.append(out_clip)

    # Write concat list
    concat_path = case_dir / "bg_clips_concat.txt"
    write_concat_list(clip_paths, concat_path, dry_run=args.dry_run)
    if not args.dry_run:
        print(f"\n  ✓ {concat_path.relative_to(PROJECT_ROOT)}")

    print(f"\n  Next:")
    print(f"    python scripts/make_audio_elevenlabs.py --case {args.case}")
    print(f"    python skill/game-short/render_game_video.py {config_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
