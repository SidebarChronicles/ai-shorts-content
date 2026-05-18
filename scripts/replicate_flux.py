#!/usr/bin/env python3
"""Flux 2 Pro wrapper for AI-generated still images (9:16 portrait).

Used as the 3rd-tier fallback in build_visuals_track.py when Pexels +
Pixabay both miss. Also used directly by the story vertical for AI-
generated narrative scenes.

Cost (May 2026): ~$0.03 per 1024×1820 image on Replicate.
API: https://replicate.com/black-forest-labs/flux-2-pro

Usage (CLI):
    python scripts/replicate_flux.py --prompt "a wolf in dark forest, cinematic" \\
                                      --out output/test_flux.png

Usage (programmatic):
    from replicate_flux import generate_flux_image
    path = generate_flux_image(prompt="...", out_path=Path("..."), seed=42)

Environment:
    REPLICATE_API_TOKEN  — required, fund at https://replicate.com/account/billing
"""

from __future__ import annotations

import argparse
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

# Flux 2 Pro endpoint on Replicate
REPLICATE_API_URL = "https://api.replicate.com/v1/predictions"
FLUX_MODEL_VERSION = "black-forest-labs/flux-2-pro"  # latest as of May 2026

# Default generation parameters tuned for narrative Shorts (9:16 portrait)
DEFAULT_ASPECT = "9:16"
DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 1820
DEFAULT_STEPS = 28              # 28-32 is the sweet spot; higher = slower, marginal quality gain
DEFAULT_GUIDANCE = 3.5          # Flux's recommended; higher = more prompt-adherent but less creative
DEFAULT_OUTPUT_FORMAT = "png"   # PNG for Ken Burns compositing (lossless)

# Idempotency cache — keyed prompts produce repeatable outputs without re-billing
CACHE_DIR = PROJECT_ROOT / "output" / "ai_cache" / "flux"


class FluxError(RuntimeError):
    """Raised when Flux generation fails (HTTP error, timeout, no output)."""


def _cache_key(prompt: str, seed: int | None, width: int, height: int) -> str:
    """Stable hash for prompt+config → caches the output image so repeat calls don't re-bill."""
    raw = f"{prompt}||{seed}||{width}x{height}||{FLUX_MODEL_VERSION}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _cached_path(prompt: str, seed: int | None, width: int, height: int) -> Path:
    key = _cache_key(prompt, seed, width, height)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{key}.{DEFAULT_OUTPUT_FORMAT}"


def generate_flux_image(prompt: str,
                        out_path: Path,
                        seed: int | None = None,
                        width: int = DEFAULT_WIDTH,
                        height: int = DEFAULT_HEIGHT,
                        steps: int = DEFAULT_STEPS,
                        guidance: float = DEFAULT_GUIDANCE,
                        use_cache: bool = True,
                        timeout_seconds: int = 120,
                        verbose: bool = False) -> Optional[Path]:
    """Generate a single Flux 2 Pro image, save to out_path, return out_path.

    Returns None if the API token is missing or generation fails non-fatally
    (caller should fall back to Pexels/Pixabay rather than crash). Raises
    FluxError only on hard infrastructure failures (timeouts, bad responses).
    """
    api_token = os.environ.get("REPLICATE_API_TOKEN", "").strip()
    if not api_token:
        if verbose:
            print("  flux: REPLICATE_API_TOKEN not set — skipping AI fallback")
        return None

    # Cache hit?
    if use_cache:
        cached = _cached_path(prompt, seed, width, height)
        if cached.exists() and cached.stat().st_size > 1024:
            if verbose:
                print(f"  flux: cache hit → {cached.relative_to(PROJECT_ROOT)}")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(cached.read_bytes())
            return out_path

    # Default negative prompt — blocks cartoon/anime/game-character hallucinations
    # that ruin photo-real narrative shorts. Pokemon, Disney, plush, anime aesthetic
    # were all explicitly hallucinating in early smoke tests.
    negative = (
        "cartoon, anime, pokemon, disney, pixar, video game character, "
        "plush toy, mascot, chibi, children's illustration, mascot, lowres, "
        "watermark, text overlay, low quality, oversaturated, deformed, "
        "extra limbs, bad anatomy, blurry, jpeg artifacts"
    )

    # Build the input payload — Flux 2 Pro on Replicate accepts these fields
    flux_input = {
        "prompt": prompt,
        "negative_prompt": negative,
        "aspect_ratio": DEFAULT_ASPECT,
        "width": width,
        "height": height,
        "num_inference_steps": steps,
        "guidance_scale": guidance,
        "output_format": DEFAULT_OUTPUT_FORMAT,
        "safety_tolerance": 1,  # strict — block AI-character hallucinations
    }
    if seed is not None:
        flux_input["seed"] = seed

    headers = {
        "Authorization": f"Token {api_token}",
        "Content-Type": "application/json",
        "Prefer": "wait=60",  # Replicate caps Prefer header at 60s; we still poll up to timeout_seconds after
    }
    # Use the model-route (latest version of this slug). Cleaner than pinning
    # to a version id that may rotate.
    create_url = f"https://api.replicate.com/v1/models/{FLUX_MODEL_VERSION}/predictions"
    payload = {"input": flux_input}

    if verbose:
        print(f"  flux: calling {FLUX_MODEL_VERSION} ({width}x{height}, steps={steps})…")

    # Submit prediction
    try:
        r = requests.post(create_url, headers=headers, json=payload,
                          timeout=timeout_seconds)
    except requests.RequestException as e:
        raise FluxError(f"Replicate POST failed: {e}") from e

    if r.status_code not in (200, 201):
        body = r.text[:300] if r.text else ""
        raise FluxError(f"Replicate returned {r.status_code}: {body}")

    pred = r.json()
    pred_id = pred.get("id")
    status = pred.get("status")
    output = pred.get("output")

    # If the Prefer header gave us a sync response with output, we're done.
    # Otherwise poll until completed or failed.
    if status not in ("succeeded", "failed", "canceled") or not output:
        get_url = pred.get("urls", {}).get("get") or f"{REPLICATE_API_URL}/{pred_id}"
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            time.sleep(2)
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
            raise FluxError(f"Flux generation timed out after {timeout_seconds}s (pred {pred_id})")

    if status != "succeeded" or not output:
        err = pred.get("error") or "no output"
        raise FluxError(f"Flux generation {status}: {err}")

    # Output is either a string URL or a list of URLs
    image_url = output[0] if isinstance(output, list) else output
    try:
        img_response = requests.get(image_url, timeout=60, stream=True)
        img_response.raise_for_status()
    except requests.RequestException as e:
        raise FluxError(f"Failed to download Flux output: {e}") from e

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        for chunk in img_response.iter_content(chunk_size=8192):
            f.write(chunk)

    # Mirror to cache for idempotent reuse
    if use_cache:
        cached = _cached_path(prompt, seed, width, height)
        cached.write_bytes(out_path.read_bytes())

    if verbose:
        size_kb = out_path.stat().st_size // 1024
        print(f"  flux: ✓ {out_path.name} ({size_kb} KB)")

    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True, help="Image prompt")
    parser.add_argument("--out", required=True, type=Path, help="Output image path")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    parser.add_argument("--guidance", type=float, default=DEFAULT_GUIDANCE)
    parser.add_argument("--no-cache", action="store_true", help="Skip the idempotency cache")
    args = parser.parse_args()

    try:
        result = generate_flux_image(
            prompt=args.prompt,
            out_path=args.out.resolve(),
            seed=args.seed,
            width=args.width,
            height=args.height,
            steps=args.steps,
            guidance=args.guidance,
            use_cache=not args.no_cache,
            verbose=True,
        )
    except FluxError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if result is None:
        print("ERROR: REPLICATE_API_TOKEN not set or empty output", file=sys.stderr)
        return 2
    print(str(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
