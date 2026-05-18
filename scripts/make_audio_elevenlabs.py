#!/usr/bin/env python3
"""ElevenLabs TTS generator — replaces make_audio.sh for cases going forward.

Usage:
    python scripts/make_audio_elevenlabs.py --case 07
    python scripts/make_audio_elevenlabs.py --case 07 --dry-run
    python scripts/make_audio_elevenlabs.py --case 07 --voice-id <id>
    python scripts/make_audio_elevenlabs.py --case GG_01_elden_ring_dlc

Outputs:
    assets/audio/narration_<case>.mp3
    assets/audio/narration_<case>.alignment.json  (when alignment enabled)
    output/elevenlabs_usage.json  (updated monthly usage)

Config via environment variables (put in .env or export before running):
    ELEVENLABS_API_KEY        required
    ELEVENLABS_VOICE_ID       default: pNInz6obpgDQGcFmaJgB  (Adam)
    ELEVENLABS_MODEL          default: eleven_turbo_v2
    ELEVENLABS_MONTHLY_BUDGET default: 22.0  (USD)
    ELEVENLABS_ALIGNMENT      default: true  (fetch word-level timestamps)
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Auto-load .env into os.environ
_env_path = PROJECT_ROOT / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

AUDIO_DIR = PROJECT_ROOT / "assets" / "audio"
SCRIPTS_DIR = PROJECT_ROOT / "output" / "scripts"
USAGE_FILE = PROJECT_ROOT / "output" / "elevenlabs_usage.json"

DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # Adam — serious documentary male
DEFAULT_MODEL = "eleven_turbo_v2"
DEFAULT_BUDGET = 22.0

# Turbo v2 on Starter tier as of mid-2026 — ~$0.30 per 1k chars
COST_PER_CHAR = 0.30 / 1000


class BudgetExceeded(Exception):
    pass


# ---------------------------------------------------------------------------
# Usage tracking
# ---------------------------------------------------------------------------

def load_usage() -> dict:
    if USAGE_FILE.exists():
        return json.loads(USAGE_FILE.read_text())
    return {}


def save_usage(data: dict) -> None:
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps(data, indent=2))


def check_budget(chars_needed: int, budget: float) -> None:
    month_key = date.today().strftime("%Y-%m")
    current_usd = load_usage().get(month_key, {}).get("usd", 0.0)
    projected = current_usd + chars_needed * COST_PER_CHAR
    if projected > budget:
        raise BudgetExceeded(
            f"Would reach ${projected:.2f} / ${budget:.2f} monthly budget. "
            f"Set ELEVENLABS_MONTHLY_BUDGET higher or wait until next month."
        )


def record_usage(chars: int) -> None:
    month_key = date.today().strftime("%Y-%m")
    data = load_usage()
    entry = data.get(month_key, {"chars": 0, "usd": 0.0})
    entry["chars"] += chars
    entry["usd"] = round(entry["usd"] + chars * COST_PER_CHAR, 4)
    data[month_key] = entry
    save_usage(data)


# ---------------------------------------------------------------------------
# Text extraction from script.md
# ---------------------------------------------------------------------------

def extract_spoken_text(case_id: str) -> str:
    """Find and extract the spoken narration from game_config.json or script.md."""
    # Game pipeline: check game_config.json for spoken_text first
    config_path = SCRIPTS_DIR / case_id / "game_config.json"
    if config_path.exists():
        cfg = json.loads(config_path.read_text())
        text = cfg.get("spoken_text", "").strip()
        if text:
            return text

    # Truecrime pipeline: resolve partial case IDs like "07" to full slugs
    candidates = list(SCRIPTS_DIR.glob(f"{case_id}_*/script.md")) + \
                 list(SCRIPTS_DIR.glob(f"*{case_id}*/script.md")) + \
                 [SCRIPTS_DIR / case_id / "script.md"]

    script_path = None
    for c in candidates:
        if c.exists():
            script_path = c
            break

    if script_path is None:
        sys.exit(
            f"ERROR: Could not find script.md or game_config.json for case '{case_id}'.\n"
            f"Checked under: {SCRIPTS_DIR}\n"
            f"Run the truecrime-short skill to generate a script first, or use --text-file."
        )

    content = script_path.read_text()

    # Extract block between "## Script (spoken" and next "---" or "## Script (with"
    pattern = r"## Script \(spoken[^\n]*\)\n\n(.*?)(?=\n---|\n## Script \(with)"
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        sys.exit(
            f"ERROR: Could not find spoken script section in {script_path}.\n"
            "Expected a section starting with '## Script (spoken'."
        )

    # Strip blockquote markers (> ...) and blank lines
    raw = match.group(1).strip()
    lines = []
    for line in raw.splitlines():
        line = re.sub(r"^>\s?", "", line)  # strip leading "> "
        lines.append(line)

    text = "\n".join(lines).strip()

    # Remove any [[slnc N]] macOS say markers
    text = re.sub(r"\[\[slnc \d+\]\]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return text


# ---------------------------------------------------------------------------
# ElevenLabs API
# ---------------------------------------------------------------------------

def synthesize(
    text: str,
    out_mp3: Path,
    out_alignment: Path | None,
    voice_id: str,
    model_id: str,
    api_key: str,
    use_alignment: bool,
) -> None:
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    body = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
    }

    if use_alignment:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
        resp = requests.post(url, headers=headers, json=body, timeout=120)
        resp.raise_for_status()
        payload = resp.json()

        # Decode base64 audio
        audio_bytes = base64.b64decode(payload["audio_base64"])
        out_mp3.write_bytes(audio_bytes)

        # Save alignment sidecar
        if out_alignment:
            out_alignment.write_text(json.dumps(payload.get("alignment", {}), indent=2))
            print(f"  Alignment: {out_alignment.relative_to(PROJECT_ROOT)}")
    else:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        resp = requests.post(url, headers=headers, json=body, timeout=120, stream=True)
        resp.raise_for_status()
        with open(out_mp3, "wb") as f:
            for chunk in resp.iter_content(chunk_size=4096):
                f.write(chunk)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ElevenLabs TTS for a case narration.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--case", metavar="ID", help="Case ID or number (e.g. 07, GG_01_slug)")
    group.add_argument("--text-file", metavar="PATH", help="Path to a plain-text narration file")
    parser.add_argument("--voice-id", default=None, help="Override ElevenLabs voice ID")
    parser.add_argument("--out", metavar="PATH", default=None, help="Output .mp3 path (overrides default)")
    parser.add_argument("--dry-run", action="store_true", help="Estimate cost without calling the API")
    args = parser.parse_args()

    # Config from environment
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    voice_id = args.voice_id or os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
    model_id = os.environ.get("ELEVENLABS_MODEL", DEFAULT_MODEL)
    budget = float(os.environ.get("ELEVENLABS_MONTHLY_BUDGET", DEFAULT_BUDGET))
    use_alignment = os.environ.get("ELEVENLABS_ALIGNMENT", "true").lower() == "true"

    if not args.dry_run and not api_key:
        sys.exit(
            "ERROR: ELEVENLABS_API_KEY is not set.\n"
            "Add it to .env or: export ELEVENLABS_API_KEY=your_key_here"
        )

    # Resolve text
    if args.text_file:
        text_path = Path(args.text_file)
        if not text_path.exists():
            sys.exit(f"ERROR: Text file not found: {text_path}")
        text = text_path.read_text().strip()
        case_label = text_path.stem
    else:
        text = extract_spoken_text(args.case)
        case_label = args.case

    if not text:
        sys.exit("ERROR: Extracted text is empty.")

    chars = len(text)
    cost_estimate = chars * COST_PER_CHAR

    print(f"── ElevenLabs TTS: {case_label} ──")
    print(f"  Voice:   {voice_id}")
    print(f"  Model:   {model_id}")
    print(f"  Chars:   {chars:,}")
    print(f"  Cost:    ~${cost_estimate:.4f}  (estimate)")

    # Show current monthly usage
    month_key = date.today().strftime("%Y-%m")
    usage = load_usage().get(month_key, {"chars": 0, "usd": 0.0})
    print(f"  Budget:  ${usage['usd']:.2f} used / ${budget:.2f} this month")

    if args.dry_run:
        print("\n  [dry-run] No API call made.")
        return

    # Budget check
    check_budget(chars, budget)

    # Output paths
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    if args.out:
        out_mp3 = Path(args.out)
    else:
        # Normalize case label: "07" → "narration_07", "GG_01_slug" → "narration_GG_01_slug"
        out_mp3 = AUDIO_DIR / f"narration_{case_label}.mp3"

    out_alignment = None
    if use_alignment:
        out_alignment = out_mp3.with_suffix(".alignment.json")

    print(f"\n  Synthesizing…")
    synthesize(text, out_mp3, out_alignment, voice_id, model_id, api_key, use_alignment)

    record_usage(chars)

    # Update usage display
    updated = load_usage().get(month_key, {"chars": 0, "usd": 0.0})

    print(f"  ✓ Audio:   {out_mp3.relative_to(PROJECT_ROOT)}")
    print(f"  ✓ Budget:  ${updated['usd']:.4f} / ${budget:.2f} used this month")

    # Quick duration check via ffprobe if available
    try:
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(out_mp3)],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            duration = float(result.stdout.strip())
            print(f"  ✓ Duration: {duration:.1f}s")
            if duration < 40 or duration > 65:
                print(f"  ⚠  Duration outside 40–65s target — review the script length.")
    except Exception:
        pass  # ffprobe not available or failed — not critical


if __name__ == "__main__":
    main()
