#!/usr/bin/env python3
"""Pixverse v4.5 video clip wrapper for AI-generated hero shots (9:16 portrait, 5s).

NOTE: file is named `replicate_pika.py` for historical reasons (the original
plan targeted Pika 2.0). Pika isn't distributed on Replicate as of May 2026,
so this module uses Pixverse v4.5 instead — same role, same I/O shape, similar
quality profile. The exposed function `generate_pika_clip` stays for callers'
sake; internally it calls Pixverse.

Used for "hero shots" in narrative shorts — the single highest-impact scene
(typically the mid_anchor beat at second-30 and payoff beat). The rest of
the video uses Flux stills with Ken Burns motion; hero shots get real video.

Cost (May 2026, Pixverse v4.5): ~$0.40 per 5-second 720p 9:16 clip.

API: https://replicate.com/pixverse/pixverse-v4.5

Usage (CLI):
    python scripts/replicate_pika.py --prompt "wolf running through forest, cinematic" \\
                                      --out output/test.mp4

Usage (programmatic):
    from replicate_pika import generate_pika_clip
    path = generate_pika_clip(prompt="...", out_path=Path("..."),
                              seconds=5, reference_image=Path("hero_still.png"))

Environment:
    REPLICATE_API_TOKEN  — required, fund at https://replicate.com/account/billing
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import sys
import time
from pathlib import Path
from typing import Optional

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

REPLICATE_API_URL = "https://api.replicate.com/v1/predictions"
# Pixverse v4.5 — fast 9:16 video gen on Replicate (262k runs as of May 2026)
VIDEO_MODEL_SLUG = "pixverse/pixverse-v4.5"

# Default generation parameters
DEFAULT_DURATION_SECONDS = 5
DEFAULT_ASPECT = "9:16"
DEFAULT_QUALITY = "720p"   # Pixverse offers 540p/720p/1080p; 720p is the cost/quality sweet spot
DEFAULT_FPS = 24

CACHE_DIR = PROJECT_ROOT / "output" / "ai_cache" / "video"


class PikaError(RuntimeError):
    """Raised when video generation fails (kept for backward compat with the original module name)."""


def _cache_key(prompt: str, seed: int | None, seconds: int,
               reference_image_bytes: bytes | None) -> str:
    """Stable hash for prompt+config → caches the output video so repeat calls don't re-bill."""
    raw = f"{prompt}||{seed}||{seconds}s||{VIDEO_MODEL_SLUG}"
    if reference_image_bytes:
        raw += "||" + hashlib.sha256(reference_image_bytes).hexdigest()[:16]
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _cached_path(prompt: str, seed: int | None, seconds: int,
                 reference_image_bytes: bytes | None) -> Path:
    key = _cache_key(prompt, seed, seconds, reference_image_bytes)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{key}.mp4"


def _encode_reference_image(path: Path) -> str:
    """Convert a reference image to a data URL Pika can ingest."""
    if not path.exists():
        raise PikaError(f"reference image not found: {path}")
    mime = "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def generate_pika_clip(prompt: str,
                       out_path: Path,
                       seconds: int = DEFAULT_DURATION_SECONDS,
                       seed: int | None = None,
                       reference_image: Path | None = None,
                       use_cache: bool = True,
                       timeout_seconds: int = 300,
                       verbose: bool = False) -> Optional[Path]:
    """Generate a 9:16 1080p video clip via Pika 2.0, save to out_path, return out_path.

    Returns None if the API token is missing. Raises PikaError on hard
    infrastructure failures (timeouts, bad responses, etc).
    """
    api_token = os.environ.get("REPLICATE_API_TOKEN", "").strip()
    if not api_token:
        if verbose:
            print("  video: REPLICATE_API_TOKEN not set — skipping AI fallback")
        return None

    ref_bytes = reference_image.read_bytes() if reference_image and reference_image.exists() else None

    # Cache hit?
    if use_cache:
        cached = _cached_path(prompt, seed, seconds, ref_bytes)
        if cached.exists() and cached.stat().st_size > 10240:
            if verbose:
                print(f"  video: cache hit → {cached.relative_to(PROJECT_ROOT)}")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(cached.read_bytes())
            return out_path

    # Build the input payload — Pixverse v4.5 schema
    # (prompt, aspect_ratio, quality, duration, image, negative_prompt)
    pixverse_input = {
        "prompt": prompt,
        "negative_prompt": (
            # Cartoon / IP hallucinations (SY_01 yellow Pokemon bug)
            "cartoon, anime, pokemon, disney, pixar, video game character, "
            "plush toy, mascot, chibi, children's illustration, "
            # Subject-fabrication anti-prompts (narrative pronouns triggered these)
            "creature, monster, animal, person, character, mascot, figure, "
            "humanoid, face, eyes, fictional being, fantasy creature, "
            "anthropomorphic, sentient being, "
            # Tech artifact baseline
            "lowres, watermark, text overlay, low quality, deformed, extra limbs"
        ),
        "aspect_ratio": DEFAULT_ASPECT,
        "quality": DEFAULT_QUALITY,
        "duration": seconds,
    }
    if seed is not None:
        pixverse_input["seed"] = seed
    if reference_image:
        pixverse_input["image"] = _encode_reference_image(reference_image)

    headers = {
        "Authorization": f"Token {api_token}",
        "Content-Type": "application/json",
        "Prefer": f"wait={min(60, timeout_seconds)}",
    }
    # Pixverse on Replicate uses the model-name route, not raw version IDs
    create_url = f"https://api.replicate.com/v1/models/{VIDEO_MODEL_SLUG}/predictions"
    payload = {"input": pixverse_input}

    if verbose:
        print(f"  video: calling {VIDEO_MODEL_SLUG} ({DEFAULT_QUALITY} {DEFAULT_ASPECT} {seconds}s)…")

    try:
        r = requests.post(create_url, headers=headers, json=payload,
                          timeout=timeout_seconds)
    except requests.RequestException as e:
        raise PikaError(f"Replicate POST failed: {e}") from e

    if r.status_code not in (200, 201):
        body = r.text[:300] if r.text else ""
        raise PikaError(f"Replicate returned {r.status_code}: {body}")

    pred = r.json()
    pred_id = pred.get("id")
    status = pred.get("status")
    output = pred.get("output")

    # Poll until completed if not already done
    if status not in ("succeeded", "failed", "canceled") or not output:
        get_url = pred.get("urls", {}).get("get") or f"{REPLICATE_API_URL}/{pred_id}"
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            time.sleep(3)
            try:
                poll = requests.get(get_url, headers=headers, timeout=15)
            except requests.RequestException:
                continue
            if poll.status_code != 200:
                continue
            pred = poll.json()
            status = pred.get("status")
            output = pred.get("output")
            if status in ("succeeded", "failed", "canceled"):
                break
        else:
            raise PikaError(f"Pika generation timed out after {timeout_seconds}s (pred {pred_id})")

    if status != "succeeded" or not output:
        err = pred.get("error") or "no output"
        raise PikaError(f"Pika generation {status}: {err}")

    video_url = output[0] if isinstance(output, list) else output
    try:
        vid_response = requests.get(video_url, timeout=120, stream=True)
        vid_response.raise_for_status()
    except requests.RequestException as e:
        raise PikaError(f"Failed to download Pika output: {e}") from e

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        for chunk in vid_response.iter_content(chunk_size=65536):
            f.write(chunk)

    if use_cache:
        cached = _cached_path(prompt, seed, seconds, ref_bytes)
        cached.write_bytes(out_path.read_bytes())

    # Cost ledger — best-effort, never break a render
    try:
        from _cost_ledger import record_pika
        record_pika(seconds)
    except Exception:
        pass

    if verbose:
        size_mb = out_path.stat().st_size / (1024 * 1024)
        print(f"  video: ✓ {out_path.name} ({size_mb:.1f} MB)")

    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True, help="Video clip prompt")
    parser.add_argument("--out", required=True, type=Path, help="Output mp4 path")
    parser.add_argument("--seconds", type=int, default=DEFAULT_DURATION_SECONDS)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--reference-image", type=Path, default=None,
                        help="Optional image for image-to-video continuity")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    try:
        result = generate_pika_clip(
            prompt=args.prompt,
            out_path=args.out.resolve(),
            seconds=args.seconds,
            seed=args.seed,
            reference_image=args.reference_image.resolve() if args.reference_image else None,
            use_cache=not args.no_cache,
            verbose=True,
        )
    except PikaError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if result is None:
        print("ERROR: REPLICATE_API_TOKEN not set", file=sys.stderr)
        return 2
    print(str(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
