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

# Pattern-interrupt cap: no single visual should hold longer than this.
# Long beats get split into N sub-clips with alternating Ken Burns motion.
MAX_CLIP_SECONDS = 4.0

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

def _try_flux(prompt: str | None, keywords: list[str], query: str,
              visuals_dir: Path, beat_idx: int, case_id: str | None) -> Optional[Path]:
    """Helper: attempt Flux generation. Returns path on success, None on any failure.

    Pulled out so the AI-first vs AI-fallback paths can share it.
    """
    if not os.environ.get("REPLICATE_API_TOKEN"):
        return None
    full_prompt = prompt or (
        f"{query}, cinematic, dramatic lighting, 9:16 portrait, "
        f"high quality photo realistic"
    )
    ai_out = visuals_dir / f"beat_{beat_idx:02d}.png"
    try:
        from replicate_flux import generate_flux_image, FluxError  # lazy
        print(f"→ flux 2 pro…", end=" ", flush=True)
        seed = (hash(case_id or "") % 1_000_000) + beat_idx if case_id else None
        result = generate_flux_image(full_prompt, ai_out, seed=seed, verbose=False)
        if result and result.exists():
            print(f"✓ (flux)")
            return result
    except (ImportError, FluxError) as e:
        print(f"\n    flux failed: {e}")
    return None


def source_image_for_beat(beat_idx: int, keywords: list[str],
                          visuals_dir: Path,
                          pexels_key: str, pixabay_key: str,
                          ai_fallback: bool = False,
                          ai_first: bool = False,
                          ai_prompt: str | None = None,
                          case_id: str | None = None) -> Optional[Path]:
    """Try each source in priority order until one returns an image.

    Args:
        ai_fallback: When True, falls back to Flux 2 Pro after Pexels+Pixabay miss.
                     Used for non-story verticals that opt into AI as a safety net.
        ai_first:    When True (story vertical), tries Flux FIRST. Stock APIs become
                     the fallback. Implies ai_fallback. Trades $0.03/image for
                     consistent narrative imagery that stock libraries can't supply.
        ai_prompt:   Full Flux prompt to use. If None, joins keywords with
                     "cinematic, dramatic lighting, 9:16".
        case_id:     Used for cache keying so identical prompts within a case don't re-bill.
    """
    if not keywords and not ai_prompt:
        print(f"  beat {beat_idx}: no keywords provided — skipping", file=sys.stderr)
        return None

    query = " ".join(keywords[:4]) if keywords else ""

    # ── AI-FIRST path (story vertical): Flux → Pexels → Pixabay ─────────────
    if ai_first:
        print(f"  beat {beat_idx}: ai-first…", end=" ", flush=True)
        result = _try_flux(ai_prompt, keywords, query, visuals_dir, beat_idx, case_id)
        if result:
            return result
        # Fall through to stock APIs if Flux missed (token absent, API down, etc)

    # ── Stock-first path (default): Pexels → Pixabay ────────────────────────
    out_path = visuals_dir / f"beat_{beat_idx:02d}.jpg"
    if query:
        if not ai_first:
            print(f"  beat {beat_idx}: pexels.com query={query!r}…", end=" ", flush=True)
        else:
            print(f"  → pexels.com query={query!r}…", end=" ", flush=True)
        pexels_hit = search_pexels(query, pexels_key)
        if pexels_hit:
            src_url = pexels_hit.get("src", {}).get("portrait") or pexels_hit.get("src", {}).get("large2x")
            if src_url and download_image(src_url, out_path):
                credit = pexels_hit.get("photographer", "Pexels")
                print(f"✓ ({credit})")
                return out_path

        print(f"→ pixabay.com…", end=" ", flush=True)
        pixabay_hit = search_pixabay(query, pixabay_key)
        if pixabay_hit:
            src_url = pixabay_hit.get("largeImageURL") or pixabay_hit.get("webformatURL")
            if src_url and download_image(src_url, out_path):
                credit = pixabay_hit.get("user", "Pixabay")
                print(f"✓ ({credit})")
                return out_path

    # ── Final fallback: Flux (if ai_fallback enabled and we haven't already tried it) ──
    if ai_fallback and not ai_first:
        result = _try_flux(ai_prompt, keywords, query, visuals_dir, beat_idx, case_id)
        if result:
            return result

    print(f"→ ✗ (no source succeeded)")
    return None


def maybe_generate_hero_video(beat_idx: int, beat_label: str,
                              prompt: str, visuals_dir: Path,
                              case_id: str | None = None,
                              seconds: int = 5) -> Optional[Path]:
    """For 'hero shot' beats (mid_anchor, payoff), generate a Pika video clip.

    Returns the path to the generated mp4, or None if Pika isn't available
    or fails. Caller should fall back to source_image_for_beat() if this
    returns None.

    Only the story vertical's mid_anchor and payoff beats trigger this in
    the current pipeline — see HERO_LABELS in build_track_for_case().
    """
    if not os.environ.get("REPLICATE_API_TOKEN"):
        return None
    try:
        from replicate_pika import generate_pika_clip, PikaError
    except ImportError:
        return None

    out_path = visuals_dir / f"beat_{beat_idx:02d}_hero.mp4"
    try:
        seed = (hash(case_id or "") % 1_000_000) + beat_idx if case_id else None
        print(f"  beat {beat_idx} [{beat_label}]: pika hero clip…", end=" ", flush=True)
        result = generate_pika_clip(prompt, out_path, seconds=seconds,
                                    seed=seed, verbose=False)
        if result and result.exists():
            print(f"✓ ({seconds}s, hero)")
            return result
    except PikaError as e:
        print(f"\n    pika failed: {e}")
    return None


# Beat labels that get Pika hero-shot treatment in AI-fallback mode.
# Only used when ai_fallback=True (story vertical).
HERO_LABELS = ("mid_anchor", "payoff")


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


def _normalize_pika_to_portrait(pika_path: Path, out_clip: Path, duration: float,
                                dry_run: bool = False) -> None:
    """Thin FFmpeg pass to align a Pika output with our portrait spec.

    Pika 2.0 outputs 9:16 1080p at 24fps. Our concat list expects:
      - 1080x1920
      - 30fps (cfr) — matches Ken Burns clips for clean concat
      - libx264 yuv420p, no audio
      - duration trimmed to the requested length

    Mismatched fps across concat segments has caused timestamp drift bugs
    before (TX_01 fix); always re-encode to a uniform fps here.
    """
    out_clip.parent.mkdir(parents=True, exist_ok=True)

    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},"
        f"fps={KB_FPS}"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", str(pika_path),
        "-vf", vf,
        "-t", f"{duration:.2f}",
        "-vsync", "cfr",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-an",
        str(out_clip),
    ]
    if dry_run:
        print(f"    [dry-run] ffmpeg pika-normalize → {out_clip.name}")
        return

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        sys.exit(f"ERROR: Pika normalize failed for {pika_path.name}:\n{result.stderr[-500:]}")


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

LOOP_TAIL_SECONDS = 0.5  # final tail = clip 1 → seamless replay


def write_concat_list(clip_paths: list[Path], concat_path: Path,
                      dry_run: bool = False, loop_back: bool = True) -> None:
    """FFmpeg concat demuxer file with optional loop-back tail.

    Without loop_back (legacy behavior): just lists each clip.

    With loop_back: shortens the final clip by LOOP_TAIL_SECONDS, then
    appends a 0.5s slice of clip 1 so the last frame matches the first
    frame. Boosts replay rate when YouTube auto-loops the Short.
    """
    if not loop_back or len(clip_paths) < 2:
        lines = [f"file '{c}'" for c in clip_paths]
        content = "\n".join(lines) + "\n"
        if dry_run:
            print(f"  [dry-run] concat list: {len(clip_paths)} clips")
            return
        atomic_write_text(concat_path, content)
        return

    # Probe durations so we can shorten the last clip + slot in a loop tail
    durations: list[float] = []
    for clip in clip_paths:
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(clip)],
                capture_output=True, text=True, timeout=15,
            )
            durations.append(float(r.stdout.strip()))
        except (subprocess.SubprocessError, ValueError):
            durations.append(0.0)

    lines: list[str] = []
    for i, (clip, dur) in enumerate(zip(clip_paths, durations)):
        lines.append(f"file '{clip}'")
        # All but the last clip use full duration; last clip is shortened by LOOP_TAIL_SECONDS
        if i == len(clip_paths) - 1:
            shortened = max(0.5, dur - LOOP_TAIL_SECONDS)
            lines.append(f"duration {shortened:.3f}")
        else:
            lines.append(f"duration {dur:.3f}")

    # Loop tail: 0.5s back to clip 1 so the visual ending matches the visual start
    first_clip = clip_paths[0]
    lines.append(f"file '{first_clip}'")
    lines.append(f"duration {LOOP_TAIL_SECONDS:.3f}")
    # FFmpeg concat trailing duplicate
    lines.append(f"file '{first_clip}'")

    content = "\n".join(lines) + "\n"
    if dry_run:
        print(f"  [dry-run] concat list: {len(clip_paths)} clips + 0.5s loop tail")
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
    parser.add_argument("--ai-fallback", action="store_true",
                        help="Enable Flux 2 Pro as a final fallback after Pexels+Pixabay miss. "
                             "Auto-enabled for story vertical (SY_*).")
    parser.add_argument("--ai-first", action="store_true",
                        help="Try Flux FIRST, falling back to stock APIs. Trades $0.03/image "
                             "for narrative imagery that stock can't supply. Auto-enabled for SY_*.")
    args = parser.parse_args()

    # Story vertical (SY_*) auto-enables AI-first: Flux generates narrative imagery
    # that stock libraries can't supply, plus Pika hero clips for mid_anchor/payoff.
    is_story = args.case.startswith("SY_")
    ai_first_enabled = args.ai_first or is_story
    ai_fallback_enabled = args.ai_fallback or is_story or ai_first_enabled

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

    # Source images (and Pika hero clips for story vertical mid_anchor/payoff)
    chain_label = "ai-first (flux → stock)" if ai_first_enabled else (
        "stock-first (pexels → pixabay → flux)" if ai_fallback_enabled else
        "stock-only (pexels → pixabay)"
    )
    print(f"\n  Sourcing visuals — chain: {chain_label}")
    image_paths: list[Optional[Path]] = []
    hero_clips: dict[int, Path] = {}  # beat_idx → pre-rendered video clip path
    for i, beat in enumerate(beats, 1):
        beat_label = beat.get("label", "")
        # For story-vertical hero beats: try Pika first (real video > Ken Burns still)
        if ai_fallback_enabled and beat_label in HERO_LABELS:
            visual_hint = beat.get("visual_style_hint", "")
            ai_prompt = (
                f"{beat.get('text', '')[:120]}, {visual_hint}, "
                f"9:16 portrait video, cinematic"
            ).strip(", ")
            hero_clip = maybe_generate_hero_video(
                beat_idx=i,
                beat_label=beat_label,
                prompt=ai_prompt,
                visuals_dir=visuals_dir,
                case_id=args.case,
                seconds=5,
            )
            if hero_clip:
                hero_clips[i] = hero_clip
                # Still source a still for the non-hero portion of the beat
                # (if the beat is longer than 5s, sub-clips after the hero use the still)

        # Build the Flux prompt for AI fallback when stock misses
        flux_prompt = None
        if ai_fallback_enabled:
            visual_hint = beat.get("visual_style_hint", "")
            palette = cfg.get("visual_palette", "")
            char_hint = cfg.get("character_continuity_hint", "")
            flux_prompt = (
                f"{beat.get('text', '')[:120]}, {visual_hint}, {palette}, "
                f"{'photorealistic' if cfg.get('subgenre') == 'reddit' else 'cinematic illustration'}, "
                f"9:16 portrait, single subject framing"
            ).strip(", ")

        path = source_image_for_beat(
            beat_idx=i,
            keywords=beat["keywords"],
            visuals_dir=visuals_dir,
            pexels_key=pexels_key,
            pixabay_key=pixabay_key,
            ai_fallback=ai_fallback_enabled,
            ai_first=ai_first_enabled,
            ai_prompt=flux_prompt,
            case_id=args.case,
        )
        image_paths.append(path)
        # Be polite to free APIs (skip when AI was the source)
        time.sleep(0.3)

    missing = [i for i, p in enumerate(image_paths, 1) if p is None]
    if missing:
        sys.exit(
            f"ERROR: No image found for beats {missing}. "
            f"Add better keywords or enable Flux 2 Pro fallback (REPLICATE_API_TOKEN)."
        )

    if hero_clips:
        print(f"  Pika hero clips: {len(hero_clips)} (beats {sorted(hero_clips.keys())})")

    # Render Ken Burns clips — split any beat >MAX_CLIP_SECONDS into sub-clips
    # for pattern-interrupt enforcement. Each sub-clip uses alternating zoom
    # direction so the same source image feels visually fresh across the beat.
    # Hero beats (mid_anchor, payoff with a Pika clip) use the Pika clip
    # directly for the first ≤5s, then optionally Ken Burns the still for any
    # remaining duration so beats longer than 5s still flow correctly.
    print(f"\n  Rendering visual clips (cap {MAX_CLIP_SECONDS}s per clip)…")
    clip_paths: list[Path] = []
    clip_seq = 0
    for beat_idx, (img, dur) in enumerate(zip(image_paths, durations), 1):
        hero_clip = hero_clips.get(beat_idx)
        # If hero clip exists and beat is ≤ Pika clip duration (~5s), use Pika alone
        if hero_clip and dur <= 5.5:
            clip_seq += 1
            out_clip = clips_dir / f"clip_{clip_seq:02d}_portrait.mp4"
            # Normalize the Pika clip to our portrait spec via a thin FFmpeg pass
            print(f"  clip_{clip_seq:02d} (beat{beat_idx} HERO PIKA {dur:.1f}s)… ",
                  end="", flush=True)
            _normalize_pika_to_portrait(hero_clip, out_clip, dur, dry_run=args.dry_run)
            if not args.dry_run:
                print("✓")
            clip_paths.append(out_clip)
            continue

        # If hero clip exists AND beat is longer than 5s: use Pika for first 5s,
        # Ken Burns the still for the rest (sub-divided per MAX_CLIP_SECONDS).
        if hero_clip:
            clip_seq += 1
            out_clip = clips_dir / f"clip_{clip_seq:02d}_portrait.mp4"
            print(f"  clip_{clip_seq:02d} (beat{beat_idx} HERO PIKA 5.0s)… ",
                  end="", flush=True)
            _normalize_pika_to_portrait(hero_clip, out_clip, 5.0, dry_run=args.dry_run)
            if not args.dry_run:
                print("✓")
            clip_paths.append(out_clip)
            remaining_dur = max(0.0, dur - 5.0)
            n_sub = max(1, int((remaining_dur + MAX_CLIP_SECONDS - 0.001) // MAX_CLIP_SECONDS))
            sub_dur = remaining_dur / n_sub if n_sub > 0 else 0
            for s in range(n_sub):
                clip_seq += 1
                out_clip = clips_dir / f"clip_{clip_seq:02d}_portrait.mp4"
                zoom_in = (clip_seq % 2 == 1)
                print(f"  clip_{clip_seq:02d} (beat{beat_idx} tail {s+1}/{n_sub}, "
                      f"{sub_dur:.1f}s)… ", end="", flush=True)
                render_ken_burns(img, out_clip, sub_dur, zoom_in=zoom_in, dry_run=args.dry_run)
                if not args.dry_run:
                    print("✓")
                clip_paths.append(out_clip)
            continue

        # Standard path: split into Ken Burns sub-clips
        n_sub = max(1, int((dur + MAX_CLIP_SECONDS - 0.001) // MAX_CLIP_SECONDS))
        sub_dur = dur / n_sub
        for s in range(n_sub):
            clip_seq += 1
            out_clip = clips_dir / f"clip_{clip_seq:02d}_portrait.mp4"
            zoom_in = (clip_seq % 2 == 1)
            label = (f"beat{beat_idx}" if n_sub == 1
                     else f"beat{beat_idx}/{s+1}of{n_sub}")
            print(f"  clip_{clip_seq:02d} ({label}, {sub_dur:.1f}s, "
                  f"zoom_{'in' if zoom_in else 'out'})… ", end="", flush=True)
            render_ken_burns(img, out_clip, sub_dur, zoom_in=zoom_in, dry_run=args.dry_run)
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
