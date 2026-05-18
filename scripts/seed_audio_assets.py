#!/usr/bin/env python3
"""Seed assets/music/ and assets/sfx/ with FFmpeg-synthesized placeholders.

These are usable as real background audio (genuine ambient pads and whoosh
sweeps generated procedurally), and good enough for testing the audio
mixing pipeline. Replace with curated tracks from YouTube Audio Library /
Pixabay Music / freesound.org when you want a more specific musical identity.

Generates:
  assets/music/games/ambient_games_01.mp3        (60s upbeat synth pad)
  assets/music/movies/ambient_movies_01.mp3      (60s cinematic orchestral-ish)
  assets/music/cases/ambient_cases_01.mp3        (60s minor-key tension drone)
  assets/music/mysteries/ambient_mysteries_01.mp3 (60s dark ambient drone)
  assets/music/mythology/ambient_mythology_01.mp3 (60s epic chord pad)
  assets/music/finance/ambient_finance_01.mp3    (60s neutral lo-fi)
  assets/sfx/whoosh_01.wav                        (0.4s filtered noise sweep)
  assets/sfx/whoosh_02.wav                        (0.4s pitched whoosh)
  assets/sfx/sting_short.wav                      (0.2s short tone burst)

Usage:
    python scripts/seed_audio_assets.py            # idempotent — skips existing
    python scripts/seed_audio_assets.py --force    # regenerate everything
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MUSIC_DIR = PROJECT_ROOT / "assets" / "music"
SFX_DIR = PROJECT_ROOT / "assets" / "sfx"


def _run(cmd: list[str], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        sys.exit(f"ERROR generating {target}:\n{result.stderr[-400:]}")


# ---------------------------------------------------------------------------
# Music generation — additive synthesis via FFmpeg sine + filters
# ---------------------------------------------------------------------------

def gen_music(name: str, vertical: str, freqs: list[float], duration: int = 60,
              filter_chain: str = "") -> None:
    """Mix N sine waves into a chord, optionally filter, output as 60s MP3."""
    out = MUSIC_DIR / vertical / f"{name}.mp3"
    if out.exists():
        print(f"  exists: {out.relative_to(PROJECT_ROOT)}")
        return

    # Build N sine inputs at low amplitude
    inputs = []
    mix_labels = []
    for i, f in enumerate(freqs):
        inputs += ["-f", "lavfi", "-t", str(duration),
                   "-i", f"sine=frequency={f}:sample_rate=44100"]
        mix_labels.append(f"[{i}:a]")

    # Filter graph: mix sines, set volume low, optionally chain extra filters
    filter_complex = (
        "".join(mix_labels)
        + f"amix=inputs={len(freqs)}:duration=longest:normalize=0,volume=0.18"
        + (f",{filter_chain}" if filter_chain else "")
        + "[out]"
    )

    cmd = ["ffmpeg", "-y", *inputs,
           "-filter_complex", filter_complex,
           "-map", "[out]",
           "-c:a", "libmp3lame", "-b:a", "128k",
           str(out)]
    _run(cmd, out)
    print(f"  ✓ {out.relative_to(PROJECT_ROOT)}")


# ---------------------------------------------------------------------------
# SFX generation
# ---------------------------------------------------------------------------

def gen_whoosh(name: str, low_freq: float = 200, high_freq: float = 1800,
               duration: float = 0.4) -> None:
    """Filtered white-noise whoosh — frequency sweep + envelope."""
    out = SFX_DIR / f"{name}.wav"
    if out.exists():
        print(f"  exists: {out.relative_to(PROJECT_ROOT)}")
        return

    # White noise → bandpass with sweep → fade in/out
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-t", f"{duration:.2f}",
        "-i", "anoisesrc=color=pink:amplitude=0.5",
        "-af",
        (f"highpass=f={low_freq},lowpass=f={high_freq},"
         f"afade=t=in:d=0.05,afade=t=out:d=0.15:st={duration-0.15:.2f},"
         f"volume=0.7"),
        "-c:a", "pcm_s16le", "-ar", "44100",
        str(out),
    ]
    _run(cmd, out)
    print(f"  ✓ {out.relative_to(PROJECT_ROOT)}")


def gen_sting(name: str, freq: float = 880, duration: float = 0.2) -> None:
    """Short tonal sting — a quick high-pitched burst."""
    out = SFX_DIR / f"{name}.wav"
    if out.exists():
        print(f"  exists: {out.relative_to(PROJECT_ROOT)}")
        return
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-t", f"{duration:.2f}",
        "-i", f"sine=frequency={freq}:sample_rate=44100",
        "-af",
        f"afade=t=in:d=0.01,afade=t=out:d=0.1:st={duration-0.1:.2f},volume=0.5",
        "-c:a", "pcm_s16le", "-ar", "44100",
        str(out),
    ]
    _run(cmd, out)
    print(f"  ✓ {out.relative_to(PROJECT_ROOT)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Regenerate even if files exist")
    args = parser.parse_args()

    if args.force:
        for d in (MUSIC_DIR, SFX_DIR):
            for f in d.rglob("*"):
                if f.is_file() and f.suffix in (".mp3", ".wav"):
                    f.unlink()
                    print(f"  removed: {f.relative_to(PROJECT_ROOT)}")

    print("Music — synthesized chord pads per vertical:")
    # Frequencies are chord roots. C major = 261.63, G major-ish, A minor, etc.
    # We're going for *general mood* not specific compositions.

    # Games / Top X: bright upbeat — major chord (C E G + high A for brightness)
    gen_music("ambient_games_01", "games",
              freqs=[261.63, 329.63, 392.00, 523.25],  # C major + high C
              filter_chain="tremolo=f=4:d=0.15")

    # Movies: cinematic orchestral-ish — C minor with octaves
    gen_music("ambient_movies_01", "movies",
              freqs=[130.81, 196.00, 261.63, 311.13],  # C2/G2/C3/Eb3
              filter_chain="aecho=0.8:0.7:60|120:0.4|0.3")

    # Cases: tension drone — low minor 2nd interval, dissonant
    gen_music("ambient_cases_01", "cases",
              freqs=[146.83, 155.56, 220.00],  # D + Eb (minor 2nd) + A
              filter_chain="lowpass=f=2000,aecho=0.6:0.7:100|200:0.3|0.2")

    # Mysteries: ambient drone, eerie
    gen_music("ambient_mysteries_01", "mysteries",
              freqs=[110.00, 116.54, 174.61, 220.00],  # A/Bb/F/A — dissonant
              filter_chain="lowpass=f=1500,aecho=0.7:0.7:150|300:0.4|0.3")

    # Mythology: epic chord pad — F major with high register
    gen_music("ambient_mythology_01", "mythology",
              freqs=[174.61, 261.63, 349.23, 440.00],  # F3/C4/F4/A4
              filter_chain="tremolo=f=2:d=0.1")

    # Finance: neutral lo-fi — simple A minor 7
    gen_music("ambient_finance_01", "finance",
              freqs=[220.00, 261.63, 329.63, 523.25],  # A/C/E/high C
              filter_chain="lowpass=f=3500")

    print("\nSFX — synthesized transition cues:")
    gen_whoosh("whoosh_01", low_freq=300, high_freq=2200, duration=0.4)
    gen_whoosh("whoosh_02", low_freq=200, high_freq=1500, duration=0.35)
    gen_sting("sting_short", freq=880, duration=0.18)

    print("\n✓ Audio assets seeded.")
    print("  These are placeholder tracks — replace with curated music from")
    print("  YouTube Audio Library (https://studio.youtube.com/channel/UC/music) or")
    print("  Pixabay Music (https://pixabay.com/music/) when you want a more")
    print("  distinctive sound. The mixer auto-picks any *.mp3 or *.wav from")
    print("  the matching assets/music/<vertical>/ folder.")


if __name__ == "__main__":
    main()
